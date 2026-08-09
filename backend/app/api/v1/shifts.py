from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_active_branch_id, get_current_user, require_role
from app.db.session import get_db
from app.models.enums import Role, ShiftCloseTiming, ShiftStatus
from app.models.mechanic import Mechanic
from app.models.shift import CashierShift
from app.models.user import User
from app.schemas.commission import (
    CommissionComputationReport,
    CommissionSettleBody,
    DailyZeroCommissionMechanic,
)
from app.schemas.shift import CashierShiftClose, CashierShiftOpen, CashierShiftRead
from app.services.commission_policy import (
    apply_first_mechanic_waiver,
    build_commission_computation,
    load_day_labor_lines,
)
from app.services.shop_settings import get_or_create_shop_settings

router = APIRouter(prefix="/shifts", tags=["shifts"])

LOCAL_TZ = ZoneInfo("Asia/Manila")


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def _combine_local_today(hhmm: str, *, now: datetime | None = None) -> datetime:
    local_now = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    t = _parse_hhmm(hhmm)
    return datetime(
        local_now.year,
        local_now.month,
        local_now.day,
        t.hour,
        t.minute,
        tzinfo=LOCAL_TZ,
    ).astimezone(timezone.utc)


def _suggest_close_timing(
    scheduled_end_at: datetime | None, closed_at: datetime
) -> ShiftCloseTiming:
    if scheduled_end_at is None:
        return ShiftCloseTiming.ON_TIME
    delta_min = (closed_at - scheduled_end_at).total_seconds() / 60
    if delta_min < -15:
        return ShiftCloseTiming.EARLY
    if delta_min > 15:
        return ShiftCloseTiming.EXTENDED
    return ShiftCloseTiming.ON_TIME


def _current_open_shift(db: Session, cashier_id: UUID, branch_id: UUID) -> CashierShift | None:
    return db.scalar(
        select(CashierShift).where(
            CashierShift.cashier_id == cashier_id,
            CashierShift.branch_id == branch_id,
            CashierShift.status == ShiftStatus.OPEN,
        )
    )


def _day_report(
    db: Session,
    *,
    branch_id: UUID,
    day: date,
    first_mechanic_id: UUID | None,
    policy_enabled: bool,
    applied: bool,
) -> CommissionComputationReport:
    lines = load_day_labor_lines(db, branch_id=branch_id, day=day)
    selected = first_mechanic_id
    applied_flag = bool(lines) and (
        applied
        or any(
            line.commission_waived and line.mechanic_id == selected
            for line in lines
        )
    )
    return build_commission_computation(
        db,
        lines,
        first_mechanic_id=selected,
        policy_enabled=policy_enabled,
        day=day,
        applied=applied_flag,
    )


@router.get("/current", response_model=CashierShiftRead | None)
def get_current_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CashierShift | None:
    return _current_open_shift(db, current_user.id, active_branch_id)


@router.get("/commission-report", response_model=CommissionComputationReport)
def commission_report_preview(
    day: date | None = Query(default=None),
    first_mechanic_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CommissionComputationReport:
    """Per-mechanic commission computation for the local shop day (preview)."""
    settings = get_or_create_shop_settings(db)
    target_day = day or datetime.now(LOCAL_TZ).date()
    open_shift = _current_open_shift(db, current_user.id, active_branch_id)
    selected_id = first_mechanic_id or (
        open_shift.first_mechanic_id if open_shift is not None else None
    )
    return _day_report(
        db,
        branch_id=active_branch_id,
        day=target_day,
        first_mechanic_id=selected_id,
        policy_enabled=settings.waive_first_mechanic_commission,
        applied=False,
    )


@router.post("/settle-commissions", response_model=CommissionComputationReport)
def settle_commissions(
    body: CommissionSettleBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CommissionComputationReport:
    """Apply first-mechanic commission waiver for the day (before closing shop/shift)."""
    settings = get_or_create_shop_settings(db)
    if not settings.waive_first_mechanic_commission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First-mechanic commission waiver is disabled in shop settings",
        )

    target_day = body.day or datetime.now(LOCAL_TZ).date()
    lines = load_day_labor_lines(db, branch_id=active_branch_id, day=target_day)
    open_shift = _current_open_shift(db, current_user.id, active_branch_id)
    first_id = body.first_mechanic_id or (
        open_shift.first_mechanic_id if open_shift is not None else None
    )
    if first_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select today's zero-commission mechanic before settling",
        )
    if not any(line.mechanic_id == first_id for line in lines):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected mechanic has no DONE or PAID labor today",
        )

    mechanic = db.get(Mechanic, first_id)
    if mechanic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mechanic not found")

    apply_first_mechanic_waiver(db, lines, first_id)

    if open_shift is not None:
        open_shift.first_mechanic_id = first_id

    db.commit()
    return _day_report(
        db,
        branch_id=active_branch_id,
        day=target_day,
        first_mechanic_id=first_id,
        policy_enabled=True,
        applied=True,
    )


@router.post(
    "/current/first-mechanic",
    response_model=CashierShiftRead,
)
def select_daily_zero_commission_mechanic(
    body: DailyZeroCommissionMechanic,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CashierShift:
    """Save today's selected zero-commission mechanic on the open shift."""
    shift = _current_open_shift(db, current_user.id, active_branch_id)
    if shift is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Open a cashier shift before selecting today's mechanic",
        )
    mechanic = db.get(Mechanic, body.mechanic_id)
    if mechanic is None or not mechanic.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select an active mechanic",
        )
    shift.first_mechanic_id = mechanic.id
    db.commit()
    db.refresh(shift)
    return shift


@router.post("/open", response_model=CashierShiftRead, status_code=status.HTTP_201_CREATED)
def open_shift(
    body: CashierShiftOpen,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> CashierShift:
    if _current_open_shift(db, current_user.id, active_branch_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an open shift",
        )

    settings = get_or_create_shop_settings(db)
    end_hhmm = (body.scheduled_end_time or settings.cashier_shift_end).strip()
    try:
        scheduled_end_at = _combine_local_today(end_hhmm)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scheduled_end_time must look like HH:MM",
        ) from exc

    now = datetime.now(timezone.utc)
    if scheduled_end_at <= now:
        scheduled_end_at = scheduled_end_at + timedelta(days=1)

    shift = CashierShift(
        cashier_id=current_user.id,
        branch_id=active_branch_id,
        opening_float=body.opening_float,
        status=ShiftStatus.OPEN,
        scheduled_end_at=scheduled_end_at,
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
    current_user: User = Depends(get_current_user),
    active_branch_id: UUID = Depends(get_active_branch_id),
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

    settings = get_or_create_shop_settings(db)
    if settings.waive_first_mechanic_commission:
        day = datetime.now(LOCAL_TZ).date()
        lines = load_day_labor_lines(db, branch_id=active_branch_id, day=day)
        if lines:
            first_id = body.first_mechanic_id or shift.first_mechanic_id
            if first_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Select today's zero-commission mechanic before "
                        "closing the shift"
                    ),
                )
            if not any(line.mechanic_id == first_id for line in lines):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected mechanic has no DONE or PAID labor today",
                )
            # Idempotent: previously settled lines are skipped.
            apply_first_mechanic_waiver(db, lines, first_id)
            shift.first_mechanic_id = first_id

    closed_at = datetime.now(timezone.utc)
    timing = body.close_timing or _suggest_close_timing(shift.scheduled_end_at, closed_at)

    shift.closing_cash_counted = body.closing_cash_counted
    shift.expected_cash = body.expected_cash
    shift.close_notes = body.close_notes
    shift.close_timing = timing.value
    shift.status = ShiftStatus.CLOSED
    shift.closed_at = closed_at
    db.commit()
    db.refresh(shift)
    return shift
