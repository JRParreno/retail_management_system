from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, noload, selectinload

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.enums import (
    DocumentPrefix,
    Role,
    ShiftStatus,
    TransactionStatus,
    TransactionType,
)
from app.models.mechanic import Mechanic
from app.models.payment import Payment
from app.models.product import Product
from app.models.shift import CashierShift
from app.models.transaction import (
    Transaction,
    TransactionLaborLine,
    TransactionPartLine,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.payment import PaymentCreateBody, PaymentRead
from app.schemas.transaction import (
    DirectSaleCreate,
    LaborLineInput,
    LaborLineRemoveBody,
    PartLineInput,
    PartLineRemoveBody,
    ServiceJobCreate,
    StatusUpdate,
    TransactionDetailRead,
    TransactionLaborLineRead,
    TransactionPartLineRead,
    TransactionRead,
    TransactionTotals,
)
from app.services.document_numbers import mint_document_number
from app.services.stock import effective_selling_price
from app.services.transactions import (
    ALLOWED_TRANSITIONS,
    apply_sale_stock_deduction,
    compute_transaction_totals,
    lock_labor_commission_snapshots,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _editable_statuses() -> set[TransactionStatus]:
    return {TransactionStatus.IN_PROGRESS, TransactionStatus.DONE}


def _current_open_shift_id(db: Session, cashier_id: UUID, branch_id: UUID) -> UUID | None:
    shift = db.scalar(
        select(CashierShift).where(
            CashierShift.cashier_id == cashier_id,
            CashierShift.branch_id == branch_id,
            CashierShift.status == ShiftStatus.OPEN,
        )
    )
    return shift.id if shift else None


def _load_transaction(db: Session, transaction_id: UUID) -> Transaction | None:
    return db.scalar(
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .options(
            selectinload(Transaction.part_lines),
            selectinload(Transaction.labor_lines),
            selectinload(Transaction.payments),
        )
    )


def _to_detail(transaction: Transaction) -> TransactionDetailRead:
    totals = TransactionTotals(**compute_transaction_totals(transaction))
    base = TransactionRead.model_validate(transaction)
    return TransactionDetailRead(
        **base.model_dump(),
        payments=[PaymentRead.model_validate(p) for p in transaction.payments],
        totals=totals,
    )


def _build_part_line(
    db: Session,
    transaction: Transaction,
    body: PartLineInput,
) -> TransactionPartLine:
    product = db.get(Product, body.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product {product.name} is inactive",
        )
    original = effective_selling_price(db, branch_id=transaction.branch_id, product=product)
    actual = body.actual_selling_price if body.actual_selling_price is not None else original
    if actual != original and not (body.override_reason and body.override_reason.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="override_reason is required when selling price is overridden",
        )
    return TransactionPartLine(
        transaction_id=transaction.id,
        product_id=product.id,
        quantity=body.quantity,
        cost_price_snapshot=product.cost_price,
        original_selling_price=original,
        actual_selling_price=actual,
        override_reason=body.override_reason,
    )


def _build_labor_line(
    db: Session,
    transaction_id: UUID,
    body: LaborLineInput,
) -> TransactionLaborLine:
    rate = body.mechanic_commission_rate
    if body.mechanic_id is not None:
        mechanic = db.get(Mechanic, body.mechanic_id)
        if mechanic is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mechanic not found",
            )
        if rate is None:
            rate = mechanic.default_commission_rate
    actual = body.actual_price if body.actual_price is not None else body.original_price
    return TransactionLaborLine(
        transaction_id=transaction_id,
        service_name=body.service_name,
        description=body.description,
        labor_fee=actual,
        mechanic_id=body.mechanic_id,
        mechanic_commission_rate=rate,
        original_price=body.original_price,
        actual_price=actual,
        override_reason=body.override_reason,
    )


def _create_payment(
    db: Session,
    transaction: Transaction,
    body: PaymentCreateBody,
    received_by_id: UUID,
) -> Payment:
    payment = Payment(
        transaction_id=transaction.id,
        payment_method=body.payment_method,
        amount=body.amount,
        amount_tendered=body.amount_tendered,
        change_due=body.change_due,
        received_by_id=received_by_id,
        reference_no=body.reference_no,
        proof_image_url=body.proof_image_url,
        notes=body.notes,
    )
    db.add(payment)
    db.flush()
    transaction.payments.append(payment)
    return payment


def _mark_paid_if_covered(
    db: Session,
    transaction: Transaction,
    adjusted_by_id: UUID,
) -> None:
    totals = compute_transaction_totals(transaction)
    if totals["paid_total"] < totals["net_total"]:
        return
    if transaction.status == TransactionStatus.PAID:
        return
    lock_labor_commission_snapshots(db, transaction)
    apply_sale_stock_deduction(db, transaction, adjusted_by_id)
    transaction.status = TransactionStatus.PAID
    transaction.paid_at = datetime.now(timezone.utc)
    if transaction.completed_at is None:
        transaction.completed_at = transaction.paid_at


@router.get("", response_model=PaginatedResponse[TransactionRead])
def list_transactions(
    status_filter: TransactionStatus | None = Query(default=None, alias="status"),
    transaction_type: TransactionType | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> PaginatedResponse[TransactionRead]:
    stmt = select(Transaction).where(Transaction.branch_id == active_branch_id).options(
        noload(Transaction.part_lines),
        noload(Transaction.labor_lines),
        noload(Transaction.payments),
    )
    count_stmt = (
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.branch_id == active_branch_id)
    )
    if status_filter is not None:
        stmt = stmt.where(Transaction.status == status_filter)
        count_stmt = count_stmt.where(Transaction.status == status_filter)
    if transaction_type is not None:
        stmt = stmt.where(Transaction.transaction_type == transaction_type)
        count_stmt = count_stmt.where(Transaction.transaction_type == transaction_type)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filt = or_(
            Transaction.document_number.ilike(pattern),
            Transaction.plate_number.ilike(pattern),
            Transaction.customer_name.ilike(pattern),
            Transaction.customer_phone.ilike(pattern),
        )
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Transaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/service-jobs",
    response_model=TransactionDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_service_job(
    body: ServiceJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> TransactionDetailRead:
    now = datetime.now(timezone.utc)
    document_number = mint_document_number(db, DocumentPrefix.JO, active_branch_id)
    transaction = Transaction(
        document_number=document_number,
        transaction_type=TransactionType.SERVICE_JOB,
        status=TransactionStatus.IN_PROGRESS,
        cashier_id=current_user.id,
        branch_id=active_branch_id,
        shift_id=_current_open_shift_id(db, current_user.id, active_branch_id),
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        motorcycle_model=body.motorcycle_model,
        plate_number=body.plate_number,
        motorcycle_color=body.motorcycle_color,
        odometer_km=body.odometer_km,
        diagnosis_notes=body.diagnosis_notes,
        internal_notes=body.internal_notes,
        estimated_total=body.estimated_total,
        started_at=now,
    )
    db.add(transaction)
    db.commit()
    transaction = _load_transaction(db, transaction.id)
    assert transaction is not None
    return _to_detail(transaction)


@router.post(
    "/direct-sales",
    response_model=TransactionDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_direct_sale(
    body: DirectSaleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> TransactionDetailRead:
    now = datetime.now(timezone.utc)
    document_number = mint_document_number(db, DocumentPrefix.INV, active_branch_id)
    transaction = Transaction(
        document_number=document_number,
        transaction_type=TransactionType.DIRECT_SALE,
        status=TransactionStatus.PAID,
        cashier_id=current_user.id,
        branch_id=active_branch_id,
        shift_id=_current_open_shift_id(db, current_user.id, active_branch_id),
        discount_amount=body.discount_amount,
        discount_reason=body.discount_reason,
        started_at=now,
        completed_at=now,
        paid_at=now,
    )
    db.add(transaction)
    db.flush()

    for line_in in body.part_lines:
        db.add(_build_part_line(db, transaction, line_in))
    db.flush()
    db.refresh(transaction)

    # Ensure part_lines/payments are visible for totals
    transaction = _load_transaction(db, transaction.id)
    assert transaction is not None

    _create_payment(db, transaction, body.payment, current_user.id)
    totals = compute_transaction_totals(transaction)
    if totals["paid_total"] < totals["net_total"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount does not cover net total",
        )

    try:
        apply_sale_stock_deduction(db, transaction, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.commit()
    transaction = _load_transaction(db, transaction.id)
    assert transaction is not None
    return _to_detail(transaction)


@router.get("/{transaction_id}", response_model=TransactionDetailRead)
def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> TransactionDetailRead:
    transaction = _load_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return _to_detail(transaction)


@router.post(
    "/{transaction_id}/part-lines",
    response_model=TransactionPartLineRead,
    status_code=status.HTTP_201_CREATED,
)
def add_part_line(
    transaction_id: UUID,
    body: PartLineInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> TransactionPartLine:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    if transaction.status not in _editable_statuses():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add lines to this transaction status",
        )
    line = _build_part_line(db, transaction, body)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.post(
    "/{transaction_id}/part-lines/{line_id}/remove",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_part_line(
    transaction_id: UUID,
    line_id: UUID,
    body: PartLineRemoveBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> None:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    if transaction.status not in _editable_statuses():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove lines from this transaction status",
        )

    line = db.get(TransactionPartLine, line_id)
    if line is None or line.transaction_id != transaction_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part line not found",
        )

    product = db.get(Product, line.product_id)
    product_label = product.name if product else str(line.product_id)
    reason = body.reason.strip()
    note = f"Removed part: {product_label} × {line.quantity} — {reason}"
    if transaction.internal_notes and transaction.internal_notes.strip():
        transaction.internal_notes = f"{transaction.internal_notes.strip()}\n{note}"
    else:
        transaction.internal_notes = note

    db.delete(line)
    db.commit()


@router.post(
    "/{transaction_id}/labor-lines/{line_id}/remove",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_labor_line(
    transaction_id: UUID,
    line_id: UUID,
    body: LaborLineRemoveBody,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> None:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    if transaction.status not in _editable_statuses():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove lines from this transaction status",
        )

    line = db.get(TransactionLaborLine, line_id)
    if line is None or line.transaction_id != transaction_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Labor line not found",
        )

    reason = body.reason.strip()
    note = f"Removed labor: {line.service_name} — {reason}"
    if transaction.internal_notes and transaction.internal_notes.strip():
        transaction.internal_notes = f"{transaction.internal_notes.strip()}\n{note}"
    else:
        transaction.internal_notes = note

    db.delete(line)
    db.commit()


@router.post(
    "/{transaction_id}/labor-lines",
    response_model=TransactionLaborLineRead,
    status_code=status.HTTP_201_CREATED,
)
def add_labor_line(
    transaction_id: UUID,
    body: LaborLineInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> TransactionLaborLine:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    if transaction.status not in _editable_statuses():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add lines to this transaction status",
        )
    line = _build_labor_line(db, transaction.id, body)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.patch("/{transaction_id}/status", response_model=TransactionDetailRead)
def update_status(
    transaction_id: UUID,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> TransactionDetailRead:
    transaction = _load_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    allowed = ALLOWED_TRANSITIONS.get(transaction.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot transition from {transaction.status.value} "
                f"to {body.status.value}"
            ),
        )

    now = datetime.now(timezone.utc)

    if body.status == TransactionStatus.DONE:
        lock_labor_commission_snapshots(db, transaction)
        transaction.completed_at = now
    elif body.status == TransactionStatus.IN_PROGRESS:
        transaction.completed_at = None
    elif body.status == TransactionStatus.PAID:
        totals = compute_transaction_totals(transaction)
        if totals["paid_total"] < totals["net_total"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark PAID until payments cover net total",
            )
        lock_labor_commission_snapshots(db, transaction)
        try:
            apply_sale_stock_deduction(db, transaction, current_user.id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        transaction.paid_at = now
        if transaction.completed_at is None:
            transaction.completed_at = now
    elif body.status == TransactionStatus.CANCELLED:
        pass

    transaction.status = body.status
    db.commit()
    transaction = _load_transaction(db, transaction_id)
    assert transaction is not None
    return _to_detail(transaction)


@router.post(
    "/{transaction_id}/payments",
    response_model=TransactionDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def add_payment(
    transaction_id: UUID,
    body: PaymentCreateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> TransactionDetailRead:
    transaction = _load_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    if transaction.status in {TransactionStatus.CANCELLED, TransactionStatus.PAID}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add payment to this transaction status",
        )

    totals = compute_transaction_totals(transaction)
    balance = totals["balance_due"]
    if body.amount > balance + Decimal("0.01"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount exceeds balance due ({balance})",
        )

    _create_payment(db, transaction, body, current_user.id)
    try:
        _mark_paid_if_covered(db, transaction, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.commit()
    transaction = _load_transaction(db, transaction_id)
    assert transaction is not None
    return _to_detail(transaction)
