from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TransactionStatus
from app.models.mechanic import Mechanic
from app.models.transaction import Transaction, TransactionLaborLine
from app.schemas.commission import (
    CommissionComputationReport,
    MechanicCommissionComputation,
)

ZERO = Decimal("0.00")
LOCAL_TZ = ZoneInfo("Asia/Manila")


def local_day_bounds_utc(day: date | None = None) -> tuple[datetime, datetime]:
    local_now = datetime.now(LOCAL_TZ)
    target = day or local_now.date()
    start_local = datetime.combine(target, time.min, tzinfo=LOCAL_TZ)
    end_local = datetime.combine(target, time.max, tzinfo=LOCAL_TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _gross_payout(line: TransactionLaborLine) -> Decimal:
    if line.mechanic_payout_gross is not None:
        return line.mechanic_payout_gross
    if line.mechanic_payout_amount is not None and not line.commission_waived:
        return line.mechanic_payout_amount
    if line.mechanic_commission_rate is not None:
        return (line.actual_price * line.mechanic_commission_rate).quantize(
            Decimal("0.01")
        )
    return ZERO


def load_day_labor_lines(
    db: Session,
    *,
    branch_id: UUID,
    day: date | None = None,
) -> list[TransactionLaborLine]:
    start_dt, end_dt = local_day_bounds_utc(day)
    return list(
        db.scalars(
            select(TransactionLaborLine)
            .options(selectinload(TransactionLaborLine.transaction))
            .join(Transaction, Transaction.id == TransactionLaborLine.transaction_id)
            .where(
                Transaction.branch_id == branch_id,
                TransactionLaborLine.mechanic_id.is_not(None),
                Transaction.status.in_(
                    [TransactionStatus.DONE, TransactionStatus.PAID]
                ),
                TransactionLaborLine.created_at >= start_dt,
                TransactionLaborLine.created_at <= end_dt,
            )
            .order_by(TransactionLaborLine.created_at.asc())
        ).all()
    )


def suggest_first_mechanic_id(lines: list[TransactionLaborLine]) -> UUID | None:
    for line in lines:
        if line.mechanic_id is not None:
            return line.mechanic_id
    return None


def build_commission_computation(
    db: Session,
    lines: list[TransactionLaborLine],
    *,
    first_mechanic_id: UUID | None,
    policy_enabled: bool,
    day: date,
    applied: bool,
) -> CommissionComputationReport:
    buckets: dict[UUID, dict[str, object]] = {}
    for line in lines:
        if line.mechanic_id is None:
            continue
        mid = line.mechanic_id
        bucket = buckets.setdefault(
            mid,
            {
                "labor_sales": ZERO,
                "commission_gross": ZERO,
                "commission_waived": ZERO,
                "commission_net": ZERO,
                "line_count": 0,
            },
        )
        gross = _gross_payout(line)
        would_waive = (
            policy_enabled
            and first_mechanic_id is not None
            and mid == first_mechanic_id
            and (applied or not line.commission_waived or line.commission_waived)
        )
        # Net after policy: waived lines / first mechanic when previewing apply
        if line.commission_waived or (
            policy_enabled
            and first_mechanic_id == mid
            and not applied
        ):
            net = ZERO
            waived = gross
        else:
            net = line.mechanic_payout_amount or ZERO
            waived = ZERO

        bucket["labor_sales"] = bucket["labor_sales"] + line.actual_price  # type: ignore[operator]
        bucket["commission_gross"] = bucket["commission_gross"] + gross  # type: ignore[operator]
        bucket["commission_waived"] = bucket["commission_waived"] + waived  # type: ignore[operator]
        bucket["commission_net"] = bucket["commission_net"] + net  # type: ignore[operator]
        bucket["line_count"] = int(bucket["line_count"]) + 1
        _ = would_waive

    mechanics_map: dict[UUID, Mechanic] = {}
    if buckets:
        mechanics_map = {
            m.id: m
            for m in db.scalars(
                select(Mechanic).where(Mechanic.id.in_(list(buckets.keys())))
            ).all()
        }

    rows: list[MechanicCommissionComputation] = []
    for mid, totals in buckets.items():
        mech = mechanics_map.get(mid)
        is_first = first_mechanic_id == mid
        rows.append(
            MechanicCommissionComputation(
                mechanic_id=mid,
                nickname=mech.nickname if mech else "Unknown",
                labor_sales=totals["labor_sales"],  # type: ignore[arg-type]
                commission_gross=totals["commission_gross"],  # type: ignore[arg-type]
                commission_waived=totals["commission_waived"],  # type: ignore[arg-type]
                commission_net=totals["commission_net"],  # type: ignore[arg-type]
                line_count=int(totals["line_count"]),
                is_first_mechanic=is_first,
                commission_waived_for_policy=is_first
                and policy_enabled
                and Decimal(str(totals["commission_waived"])) > ZERO,
            )
        )

    rows.sort(key=lambda r: r.commission_gross, reverse=True)
    first_row = next((r for r in rows if r.is_first_mechanic), None)
    return CommissionComputationReport(
        day=day,
        policy_enabled=policy_enabled,
        applied=applied,
        first_mechanic_id=first_mechanic_id,
        first_mechanic_nickname=first_row.nickname if first_row else None,
        mechanics=rows,
        labor_sales_total=sum((r.labor_sales for r in rows), start=ZERO),
        commission_gross_total=sum((r.commission_gross for r in rows), start=ZERO),
        commission_waived_total=sum((r.commission_waived for r in rows), start=ZERO),
        commission_net_total=sum((r.commission_net for r in rows), start=ZERO),
    )


def apply_first_mechanic_waiver(
    db: Session,
    lines: list[TransactionLaborLine],
    first_mechanic_id: UUID,
) -> Decimal:
    waived_total = ZERO
    for line in lines:
        if line.mechanic_id != first_mechanic_id:
            continue
        if line.commission_waived:
            continue
        gross = _gross_payout(line)
        if line.mechanic_payout_gross is None and gross > ZERO:
            line.mechanic_payout_gross = gross
        waived_total += gross
        line.mechanic_payout_amount = ZERO
        line.commission_waived = True
    return waived_total
