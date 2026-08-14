from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TransactionStatus
from app.models.mechanic import Mechanic
from app.models.transaction import Transaction, TransactionLaborLine
from app.schemas.mechanic import (
    MechanicLaborBoardRead,
    MechanicLaborBoardRow,
    MechanicLaborWorkLine,
    MechanicLaborWorkRead,
)

ZERO = Decimal("0.00")
OPEN_STATUSES = (
    TransactionStatus.IN_PROGRESS,
    TransactionStatus.DONE,
    TransactionStatus.PAID,
)
UNASSIGNED_NICKNAME = "Unassigned"
UNASSIGNED_FULL_NAME = "Labor with no mechanic"


def _utc_range(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """Same UTC day window as production mechanic profile / reports."""
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt


def load_labor_lines_in_range(
    db: Session,
    *,
    branch_id: UUID,
    start_date: date,
    end_date: date,
    mechanic_id: UUID | None = None,
    unassigned_only: bool = False,
) -> list[TransactionLaborLine]:
    """Read existing labor lines only — never rewrite production tickets.

    Paid jobs use paid_at (matches existing mechanic profile).
    Open jobs have no paid_at, so created_at is used.
    """
    start_dt, end_dt = _utc_range(start_date, end_date)
    activity_at = func.coalesce(Transaction.paid_at, TransactionLaborLine.created_at)
    filters = [
        Transaction.branch_id == branch_id,
        Transaction.status.in_(OPEN_STATUSES),
        activity_at >= start_dt,
        activity_at <= end_dt,
    ]
    if unassigned_only:
        filters.append(TransactionLaborLine.mechanic_id.is_(None))
    elif mechanic_id is not None:
        filters.append(TransactionLaborLine.mechanic_id == mechanic_id)

    return list(
        db.scalars(
            select(TransactionLaborLine)
            .options(selectinload(TransactionLaborLine.transaction))
            .join(Transaction, Transaction.id == TransactionLaborLine.transaction_id)
            .where(*filters)
            .order_by(activity_at.desc(), TransactionLaborLine.created_at.desc())
        ).all()
    )


def to_work_line(line: TransactionLaborLine) -> MechanicLaborWorkLine:
    tx = line.transaction
    return MechanicLaborWorkLine(
        id=line.id,
        transaction_id=line.transaction_id,
        document_number=tx.document_number if tx else None,
        transaction_status=tx.status if tx else None,
        service_name=line.service_name,
        description=line.description,
        original_price=line.original_price,
        actual_price=line.actual_price,
        mechanic_commission_rate=line.mechanic_commission_rate,
        mechanic_payout_amount=line.mechanic_payout_amount,
        customer_name=tx.customer_name if tx else None,
        customer_phone=tx.customer_phone if tx else None,
        motorcycle_model=tx.motorcycle_model if tx else None,
        plate_number=tx.plate_number if tx else None,
        motorcycle_color=tx.motorcycle_color if tx else None,
        created_at=line.created_at,
        paid_at=tx.paid_at if tx else None,
    )


def _bucket_totals(lines: list[TransactionLaborLine]) -> dict[UUID | None, dict[str, Decimal | int | set[UUID]]]:
    buckets: dict[UUID | None, dict[str, Decimal | int | set[UUID]]] = {}
    for line in lines:
        bucket = buckets.setdefault(
            line.mechanic_id,
            {
                "labor_total": ZERO,
                "line_count": 0,
                "job_ids": set(),
            },
        )
        bucket["labor_total"] = bucket["labor_total"] + line.actual_price  # type: ignore[operator]
        bucket["line_count"] = int(bucket["line_count"]) + 1
        job_ids = bucket["job_ids"]
        assert isinstance(job_ids, set)
        job_ids.add(line.transaction_id)
    return buckets


def build_labor_board(
    db: Session,
    *,
    branch_id: UUID,
    start_date: date,
    end_date: date,
) -> MechanicLaborBoardRead:
    mechanics = list(db.scalars(select(Mechanic).order_by(Mechanic.full_name)).all())
    lines = load_labor_lines_in_range(
        db, branch_id=branch_id, start_date=start_date, end_date=end_date
    )
    buckets = _bucket_totals(lines)
    by_id = {mechanic.id: mechanic for mechanic in mechanics}

    rows: list[MechanicLaborBoardRow] = []
    for mechanic in mechanics:
        totals = buckets.get(mechanic.id)
        if totals is None and not mechanic.is_active:
            continue
        job_ids = totals["job_ids"] if totals else set()
        assert isinstance(job_ids, set)
        rows.append(
            MechanicLaborBoardRow(
                mechanic_id=mechanic.id,
                full_name=mechanic.full_name,
                nickname=mechanic.nickname,
                is_active=mechanic.is_active,
                job_count=len(job_ids),
                line_count=int(totals["line_count"]) if totals else 0,
                labor_total=totals["labor_total"] if totals else ZERO,  # type: ignore[arg-type]
            )
        )

    # Historical labor whose mechanic row is gone should still appear.
    for mechanic_id, totals in buckets.items():
        if mechanic_id is None or mechanic_id in by_id:
            continue
        job_ids = totals["job_ids"]
        assert isinstance(job_ids, set)
        rows.append(
            MechanicLaborBoardRow(
                mechanic_id=mechanic_id,
                full_name="Former mechanic",
                nickname="Former mechanic",
                is_active=False,
                job_count=len(job_ids),
                line_count=int(totals["line_count"]),
                labor_total=totals["labor_total"],  # type: ignore[arg-type]
            )
        )

    unassigned = buckets.get(None)
    if unassigned:
        job_ids = unassigned["job_ids"]
        assert isinstance(job_ids, set)
        rows.append(
            MechanicLaborBoardRow(
                mechanic_id=None,
                full_name=UNASSIGNED_FULL_NAME,
                nickname=UNASSIGNED_NICKNAME,
                is_active=True,
                job_count=len(job_ids),
                line_count=int(unassigned["line_count"]),
                labor_total=unassigned["labor_total"],  # type: ignore[arg-type]
            )
        )

    rows.sort(key=lambda row: (-row.labor_total, row.nickname.lower()))
    labor_total = sum((row.labor_total for row in rows), start=ZERO)
    unique_jobs = {line.transaction_id for line in lines}
    return MechanicLaborBoardRead(
        start_date=start_date,
        end_date=end_date,
        mechanic_count=len(rows),
        job_count=len(unique_jobs),
        line_count=sum(row.line_count for row in rows),
        labor_total=labor_total,
        mechanics=rows,
    )


def build_labor_work(
    db: Session,
    *,
    branch_id: UUID,
    start_date: date,
    end_date: date,
    mechanic: Mechanic | None = None,
    unassigned_only: bool = False,
) -> MechanicLaborWorkRead:
    lines = load_labor_lines_in_range(
        db,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
        mechanic_id=None if unassigned_only or mechanic is None else mechanic.id,
        unassigned_only=unassigned_only,
    )
    work_lines = [to_work_line(line) for line in lines]
    labor_total = sum((line.actual_price for line in lines), start=ZERO)
    job_count = len({line.transaction_id for line in lines})
    if unassigned_only or mechanic is None:
        return MechanicLaborWorkRead(
            mechanic_id=None,
            full_name=UNASSIGNED_FULL_NAME,
            nickname=UNASSIGNED_NICKNAME,
            is_active=True,
            start_date=start_date,
            end_date=end_date,
            job_count=job_count,
            line_count=len(work_lines),
            labor_total=labor_total,
            lines=work_lines,
        )
    return MechanicLaborWorkRead(
        mechanic_id=mechanic.id,
        full_name=mechanic.full_name,
        nickname=mechanic.nickname,
        is_active=mechanic.is_active,
        start_date=start_date,
        end_date=end_date,
        job_count=job_count,
        line_count=len(work_lines),
        labor_total=labor_total,
        lines=work_lines,
    )
