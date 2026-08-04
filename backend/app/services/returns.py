from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import (
    DocumentPrefix,
    ReturnStatus,
    ReturnType,
    StockAdjustmentType,
    TransactionStatus,
)
from app.models.inventory import StockAdjustment
from app.models.product import Product
from app.models.return_void import ReturnVoid, ReturnVoidLaborLine, ReturnVoidPartLine
from app.models.transaction import Transaction, TransactionLaborLine, TransactionPartLine
from app.models.user import User
from app.schemas.return_void import ReturnVoidCreate
from app.services.document_numbers import mint_document_number
from app.services.stock import get_or_create_branch_stock


def _returned_part_qty(db: Session, part_line_id: UUID) -> int:
    rows = db.scalars(
        select(ReturnVoidPartLine).where(
            ReturnVoidPartLine.original_part_line_id == part_line_id
        )
    ).all()
    return sum(r.quantity for r in rows)


def _labor_already_refunded(db: Session, labor_line_id: UUID) -> bool:
    existing = db.scalar(
        select(ReturnVoidLaborLine.id)
        .where(ReturnVoidLaborLine.original_labor_line_id == labor_line_id)
        .limit(1)
    )
    return existing is not None


def refundable_snapshot(db: Session, transaction: Transaction) -> dict:
    """Remaining returnable quantities / labor for a PAID transaction."""
    parts = []
    for line in transaction.part_lines:
        returned = _returned_part_qty(db, line.id)
        remaining = max(0, line.quantity - returned)
        parts.append(
            {
                "part_line_id": line.id,
                "product_id": line.product_id,
                "product_name": line.product.name if line.product else None,
                "barcode": line.product.barcode if line.product else None,
                "original_qty": line.quantity,
                "returned_qty": returned,
                "remaining_qty": remaining,
                "unit_price": line.actual_selling_price,
                "cost_price": line.cost_price_snapshot,
            }
        )

    labor = []
    for line in transaction.labor_lines:
        refunded = _labor_already_refunded(db, line.id)
        labor.append(
            {
                "labor_line_id": line.id,
                "service_name": line.service_name,
                "mechanic_id": line.mechanic_id,
                "actual_price": line.actual_price,
                "mechanic_payout_amount": line.mechanic_payout_amount or Decimal("0.00"),
                "already_refunded": refunded,
            }
        )

    return {
        "transaction_id": transaction.id,
        "document_number": transaction.document_number,
        "status": transaction.status,
        "branch_id": transaction.branch_id,
        "part_lines": parts,
        "labor_lines": labor,
    }


def process_return_void(
    db: Session,
    *,
    body: ReturnVoidCreate,
    current_user: User,
    active_branch_id: UUID,
    shift_id: UUID | None,
) -> ReturnVoid:
    if not body.part_lines and not body.labor_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one part or labor line to refund",
        )

    transaction = db.scalar(
        select(Transaction)
        .where(Transaction.id == body.original_transaction_id)
        .options(
            selectinload(Transaction.part_lines).selectinload(TransactionPartLine.product),
            selectinload(Transaction.labor_lines),
            selectinload(Transaction.return_voids).selectinload(ReturnVoid.part_lines),
            selectinload(Transaction.return_voids).selectinload(ReturnVoid.labor_lines),
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

    part_by_id = {line.id: line for line in transaction.part_lines}
    labor_by_id = {line.id: line for line in transaction.labor_lines}

    # Validate parts
    for item in body.part_lines:
        if item.original_part_line_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="original_part_line_id is required for part refunds",
            )
        original = part_by_id.get(item.original_part_line_id)
        if original is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Part line does not belong to this transaction",
            )
        if item.product_id != original.product_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="product_id does not match original part line",
            )
        remaining = original.quantity - _returned_part_qty(db, original.id)
        if item.quantity > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot refund {item.quantity} of product; "
                    f"only {remaining} remaining"
                ),
            )

    # Validate labor
    for item in body.labor_lines:
        if item.original_labor_line_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="original_labor_line_id is required for labor refunds",
            )
        original = labor_by_id.get(item.original_labor_line_id)
        if original is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Labor line does not belong to this transaction",
            )
        if _labor_already_refunded(db, original.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Labor line already refunded: {original.service_name}",
            )
        if item.refund_amount > original.actual_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Labor refund cannot exceed original fee",
            )

    # Infer VOID vs PARTIAL if caller sent VOID but not everything remaining
    snapshot = refundable_snapshot(db, transaction)
    remaining_parts = sum(p["remaining_qty"] for p in snapshot["part_lines"])
    remaining_labor = sum(
        0 if L["already_refunded"] else 1 for L in snapshot["labor_lines"]
    )
    refunded_parts = sum(p.quantity for p in body.part_lines)
    refunded_labor = len(body.labor_lines)
    inferred_type = body.return_type
    if (
        refunded_parts == remaining_parts
        and refunded_labor == remaining_labor
        and (remaining_parts > 0 or remaining_labor > 0)
    ):
        inferred_type = ReturnType.VOID
    elif body.return_type == ReturnType.VOID and (
        refunded_parts < remaining_parts or refunded_labor < remaining_labor
    ):
        inferred_type = ReturnType.PARTIAL_RETURN

    document_number = mint_document_number(
        db, DocumentPrefix.RV, transaction.branch_id
    )
    # RV-BRANCH-YYYY-##### can exceed 32 chars for long codes
    if len(document_number) > 40:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document number too long",
        )

    rv = ReturnVoid(
        document_number=document_number,
        original_transaction_id=transaction.id,
        return_type=inferred_type,
        status=ReturnStatus.COMPLETED,
        reason=body.reason.strip(),
        processed_by_id=current_user.id,
        cashier_id=current_user.id,
        shift_id=body.shift_id or shift_id,
    )
    db.add(rv)
    db.flush()

    for item in body.part_lines:
        original = part_by_id[item.original_part_line_id]  # type: ignore[index]
        line = ReturnVoidPartLine(
            return_void_id=rv.id,
            original_part_line_id=original.id,
            product_id=original.product_id,
            quantity=item.quantity,
            restock=item.restock,
            unit_refund_amount=item.unit_refund_amount,
            cost_price_snapshot=item.cost_price_snapshot or original.cost_price_snapshot,
        )
        db.add(line)

        if item.restock:
            product = db.get(Product, original.product_id)
            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found for restock",
                )
            stock = get_or_create_branch_stock(
                db, branch_id=transaction.branch_id, product=product
            )
            qty_before = stock.stock_qty
            stock.stock_qty = qty_before + item.quantity
            product.stock_qty = product.stock_qty + item.quantity
            db.add(
                StockAdjustment(
                    product_id=product.id,
                    branch_id=transaction.branch_id,
                    adjustment_type=StockAdjustmentType.RETURN,
                    quantity_delta=item.quantity,
                    qty_before=qty_before,
                    qty_after=stock.stock_qty,
                    reason=f"Refund {document_number}",
                    adjusted_by_id=current_user.id,
                    transaction_id=transaction.id,
                    return_void_id=rv.id,
                )
            )

    for item in body.labor_lines:
        original = labor_by_id[item.original_labor_line_id]  # type: ignore[index]
        reversal = item.commission_reversal_amount
        if reversal == 0 and original.mechanic_payout_amount:
            # Pro-rate commission if partial labor refund
            if original.actual_price > 0:
                ratio = item.refund_amount / original.actual_price
                reversal = (original.mechanic_payout_amount * ratio).quantize(
                    Decimal("0.01")
                )
        db.add(
            ReturnVoidLaborLine(
                return_void_id=rv.id,
                original_labor_line_id=original.id,
                mechanic_id=item.mechanic_id or original.mechanic_id,
                refund_amount=item.refund_amount,
                commission_reversal_amount=reversal,
            )
        )

    db.commit()
    db.refresh(rv)
    return db.scalar(
        select(ReturnVoid)
        .where(ReturnVoid.id == rv.id)
        .options(
            selectinload(ReturnVoid.part_lines),
            selectinload(ReturnVoid.labor_lines),
        )
    )
