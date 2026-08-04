from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.enums import Role, ShiftStatus, TransactionStatus
from app.models.return_void import ReturnVoid
from app.models.shift import CashierShift
from app.models.transaction import Transaction, TransactionPartLine
from app.models.user import User
from app.schemas.return_void import (
    RefundableSnapshot,
    ReturnVoidCreate,
    ReturnVoidRead,
)
from app.services.returns import process_return_void, refundable_snapshot

router = APIRouter(prefix="/return-voids", tags=["return-voids"])


def _current_open_shift(
    db: Session, cashier_id: UUID, branch_id: UUID
) -> CashierShift | None:
    return db.scalar(
        select(CashierShift).where(
            CashierShift.cashier_id == cashier_id,
            CashierShift.branch_id == branch_id,
            CashierShift.status == ShiftStatus.OPEN,
        )
    )


@router.get("/refundable/{transaction_id}", response_model=RefundableSnapshot)
def get_refundable(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    active_branch_id: UUID = Depends(get_active_branch_id),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> RefundableSnapshot:
    transaction = db.scalar(
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .options(
            selectinload(Transaction.part_lines).selectinload(TransactionPartLine.product),
            selectinload(Transaction.labor_lines),
        )
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.branch_id != active_branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction belongs to a different branch",
        )
    if transaction.status != TransactionStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PAID transactions can be refunded",
        )
    return RefundableSnapshot.model_validate(refundable_snapshot(db, transaction))


@router.get("", response_model=list[ReturnVoidRead])
def list_return_voids(
    db: Session = Depends(get_db),
    active_branch_id: UUID = Depends(get_active_branch_id),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ReturnVoid]:
    stmt = (
        select(ReturnVoid)
        .join(Transaction, ReturnVoid.original_transaction_id == Transaction.id)
        .where(Transaction.branch_id == active_branch_id)
        .options(
            selectinload(ReturnVoid.part_lines),
            selectinload(ReturnVoid.labor_lines),
        )
        .order_by(ReturnVoid.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.get("/{return_void_id}", response_model=ReturnVoidRead)
def get_return_void(
    return_void_id: UUID,
    db: Session = Depends(get_db),
    active_branch_id: UUID = Depends(get_active_branch_id),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> ReturnVoid:
    rv = db.scalar(
        select(ReturnVoid)
        .where(ReturnVoid.id == return_void_id)
        .options(
            selectinload(ReturnVoid.part_lines),
            selectinload(ReturnVoid.labor_lines),
            selectinload(ReturnVoid.original_transaction),
        )
    )
    if rv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund not found")
    if rv.original_transaction.branch_id != active_branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund belongs to a different branch",
        )
    return rv


@router.post("", response_model=ReturnVoidRead, status_code=status.HTTP_201_CREATED)
def create_return_void(
    body: ReturnVoidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ReturnVoid:
    shift = _current_open_shift(db, current_user.id, active_branch_id)
    result = process_return_void(
        db,
        body=body,
        current_user=current_user,
        active_branch_id=active_branch_id,
        shift_id=shift.id if shift else None,
    )
    return result
