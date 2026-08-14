from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.enums import Role, TransactionStatus
from app.models.mechanic import Mechanic
from app.models.transaction import Transaction, TransactionLaborLine
from app.models.user import User
from app.schemas.mechanic import (
    MechanicCreate,
    MechanicLaborBoardRead,
    MechanicLaborWorkRead,
    MechanicProfileLaborLine,
    MechanicProfileRead,
    MechanicRead,
    MechanicUpdate,
)
from app.services.mechanic_labor import build_labor_board, build_labor_work

router = APIRouter(prefix="/mechanics", tags=["mechanics"])

ZERO = Decimal("0.00")


def _require_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )


@router.get("", response_model=list[MechanicRead])
def list_mechanics(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[Mechanic]:
    return list(db.scalars(select(Mechanic).order_by(Mechanic.full_name)).all())


@router.get("/labor-board", response_model=MechanicLaborBoardRead)
def get_mechanic_labor_board(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> MechanicLaborBoardRead:
    _require_date_range(start_date, end_date)
    return build_labor_board(
        db,
        branch_id=active_branch_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/unassigned/labor-work", response_model=MechanicLaborWorkRead)
def get_unassigned_labor_work(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> MechanicLaborWorkRead:
    _require_date_range(start_date, end_date)
    return build_labor_work(
        db,
        branch_id=active_branch_id,
        start_date=start_date,
        end_date=end_date,
        unassigned_only=True,
    )


@router.get("/{mechanic_id}/labor-work", response_model=MechanicLaborWorkRead)
def get_mechanic_labor_work(
    mechanic_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> MechanicLaborWorkRead:
    _require_date_range(start_date, end_date)
    mechanic = db.get(Mechanic, mechanic_id)
    if mechanic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mechanic not found")
    return build_labor_work(
        db,
        mechanic=mechanic,
        branch_id=active_branch_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{mechanic_id}", response_model=MechanicRead)
def get_mechanic(
    mechanic_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> Mechanic:
    mechanic = db.get(Mechanic, mechanic_id)
    if mechanic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mechanic not found")
    return mechanic


@router.get("/{mechanic_id}/profile", response_model=MechanicProfileRead)
def get_mechanic_profile(
    mechanic_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> MechanicProfileRead:
    mechanic = db.get(Mechanic, mechanic_id)
    if mechanic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mechanic not found")

    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

    lines = list(
        db.scalars(
            select(TransactionLaborLine)
            .options(selectinload(TransactionLaborLine.transaction))
            .join(Transaction, Transaction.id == TransactionLaborLine.transaction_id)
            .where(
                TransactionLaborLine.mechanic_id == mechanic_id,
                Transaction.status == TransactionStatus.PAID,
                Transaction.branch_id == active_branch_id,
                Transaction.paid_at.is_not(None),
                Transaction.paid_at >= start_dt,
                Transaction.paid_at <= end_dt,
            )
            .order_by(Transaction.paid_at.desc())
        ).all()
    )

    labor_sales = sum((line.actual_price for line in lines), start=ZERO)
    commission_total = sum(
        (line.mechanic_payout_amount or ZERO for line in lines), start=ZERO
    )
    job_count = len({line.transaction_id for line in lines})

    recent_lines: list[MechanicProfileLaborLine] = []
    for line in lines[:40]:
        tx = line.transaction
        recent_lines.append(
            MechanicProfileLaborLine(
                id=line.id,
                transaction_id=line.transaction_id,
                document_number=tx.document_number if tx else None,
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
        )

    return MechanicProfileRead(
        id=mechanic.id,
        full_name=mechanic.full_name,
        nickname=mechanic.nickname,
        default_commission_rate=mechanic.default_commission_rate,
        is_active=mechanic.is_active,
        start_date=start_date,
        end_date=end_date,
        job_count=job_count,
        labor_sales=labor_sales,
        commission_total=commission_total,
        recent_lines=recent_lines,
    )


@router.post("", response_model=MechanicRead, status_code=status.HTTP_201_CREATED)
def create_mechanic(
    body: MechanicCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> Mechanic:
    mechanic = Mechanic(**body.model_dump())
    db.add(mechanic)
    db.commit()
    db.refresh(mechanic)
    return mechanic


@router.patch("/{mechanic_id}", response_model=MechanicRead)
def update_mechanic(
    mechanic_id: UUID,
    body: MechanicUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> Mechanic:
    mechanic = db.get(Mechanic, mechanic_id)
    if mechanic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mechanic not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(mechanic, key, value)
    db.commit()
    db.refresh(mechanic)
    return mechanic
