from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.enums import Role, ShiftStatus
from app.models.shift import CashierShift
from app.models.user import User
from app.schemas.shift import CashierShiftClose, CashierShiftOpen, CashierShiftRead

router = APIRouter(prefix="/shifts", tags=["shifts"])


def _current_open_shift(db: Session, cashier_id: UUID, branch_id: UUID) -> CashierShift | None:
    return db.scalar(
        select(CashierShift).where(
            CashierShift.cashier_id == cashier_id,
            CashierShift.branch_id == branch_id,
            CashierShift.status == ShiftStatus.OPEN,
        )
    )


@router.get("/current", response_model=CashierShiftRead | None)
def get_current_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CashierShift | None:
    return _current_open_shift(db, current_user.id, active_branch_id)


@router.post("/open", response_model=CashierShiftRead, status_code=status.HTTP_201_CREATED)
def open_shift(
    body: CashierShiftOpen,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CashierShift:
    if _current_open_shift(db, current_user.id, active_branch_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an open shift",
        )
    shift = CashierShift(
        cashier_id=current_user.id,
        branch_id=active_branch_id,
        opening_float=body.opening_float,
        status=ShiftStatus.OPEN,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.post("/{shift_id}/close", response_model=CashierShiftRead)
def close_shift(
    shift_id: UUID,
    body: CashierShiftClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> CashierShift:
    shift = db.get(CashierShift, shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    if shift.cashier_id != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your shift")
    if shift.status != ShiftStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shift is already closed",
        )
    shift.closing_cash_counted = body.closing_cash_counted
    shift.expected_cash = body.expected_cash
    shift.close_notes = body.close_notes
    shift.status = ShiftStatus.CLOSED
    shift.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(shift)
    return shift
