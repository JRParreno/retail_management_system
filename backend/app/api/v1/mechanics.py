from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.enums import Role, TransactionStatus
from app.models.mechanic import Mechanic
from app.models.transaction import Transaction, TransactionLaborLine
from app.models.user import User
from app.schemas.mechanic import (
    MechanicCreate,
    MechanicProfileLaborLine,
    MechanicProfileRead,
    MechanicRead,
    MechanicUpdate,
)

router = APIRouter(prefix="/mechanics", tags=["mechanics"])

ZERO = Decimal("0.00")


@router.get("", response_model=list[MechanicRead])
def list_mechanics(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[Mechanic]:
    return list(db.scalars(select(Mechanic).order_by(Mechanic.full_name)).all())


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

    recent_lines = [
        MechanicProfileLaborLine.model_validate(line) for line in lines[:20]
    ]

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
