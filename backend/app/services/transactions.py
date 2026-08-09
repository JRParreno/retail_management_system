from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import NotificationType, StockAdjustmentType, TransactionStatus
from app.models.inventory import StockAdjustment
from app.models.mechanic import Mechanic
from app.models.notification import Notification
from app.models.product import Product
from app.models.transaction import Transaction
from app.services.stock import get_or_create_branch_stock


def stock_already_deducted(db: Session, transaction_id: UUID) -> bool:
    existing = db.scalar(
        select(StockAdjustment.id)
        .where(
            StockAdjustment.transaction_id == transaction_id,
            StockAdjustment.adjustment_type == StockAdjustmentType.SALE,
        )
        .limit(1)
    )
    return existing is not None


def apply_sale_stock_deduction(
    db: Session,
    transaction: Transaction,
    adjusted_by_id: UUID,
) -> None:
    """Decrement branch stock for all part lines when transaction becomes PAID."""
    if stock_already_deducted(db, transaction.id):
        return
    for line in transaction.part_lines:
        product = db.get(Product, line.product_id)
        if product is None:
            raise ValueError(f"Product {line.product_id} not found")
        stock = get_or_create_branch_stock(
            db, branch_id=transaction.branch_id, product=product
        )
        qty_before = stock.stock_qty
        if qty_before < line.quantity:
            raise ValueError(f"Insufficient stock for {product.name}")
        stock.stock_qty = qty_before - line.quantity
        # Keep catalog mirror in sync for Main convenience / legacy reads
        product.stock_qty = max(0, product.stock_qty - line.quantity)
        db.add(
            StockAdjustment(
                product_id=product.id,
                branch_id=transaction.branch_id,
                adjustment_type=StockAdjustmentType.SALE,
                quantity_delta=-line.quantity,
                qty_before=qty_before,
                qty_after=stock.stock_qty,
                reason=f"Sale {transaction.document_number}",
                adjusted_by_id=adjusted_by_id,
                transaction_id=transaction.id,
            )
        )
        if stock.stock_qty <= stock.min_stock_threshold:
            db.add(
                Notification(
                    type=NotificationType.LOW_STOCK,
                    title=f"Low stock: {product.name}",
                    message=(
                        f"{product.name} is at {stock.stock_qty} "
                        f"(threshold {stock.min_stock_threshold})."
                    ),
                    product_id=product.id,
                )
            )


def lock_labor_commission_snapshots(db: Session, transaction: Transaction) -> None:
    for line in transaction.labor_lines:
        if line.commission_waived:
            continue
        if line.mechanic_commission_rate is None and line.mechanic_id is not None:
            mechanic = db.get(Mechanic, line.mechanic_id)
            if mechanic is not None:
                line.mechanic_commission_rate = mechanic.default_commission_rate
        if line.mechanic_commission_rate is None:
            continue
        fee = line.actual_price
        line.labor_fee = fee
        payout = (fee * line.mechanic_commission_rate).quantize(Decimal("0.01"))
        line.mechanic_payout_amount = payout
        line.mechanic_payout_gross = payout


def compute_transaction_totals(transaction: Transaction) -> dict:
    zero = Decimal("0.00")
    parts = sum(
        (line.actual_selling_price * line.quantity for line in transaction.part_lines),
        start=zero,
    )
    labor = sum((line.actual_price for line in transaction.labor_lines), start=zero)
    gross = parts + labor
    discount = transaction.discount_amount or zero
    net = gross - discount
    paid = sum((p.amount for p in transaction.payments), start=zero)
    return {
        "parts_total": parts,
        "labor_total": labor,
        "gross_total": gross,
        "discount_amount": discount,
        "net_total": net,
        "paid_total": paid,
        "balance_due": net - paid,
    }


ALLOWED_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.IN_PROGRESS: {
        TransactionStatus.DONE,
        TransactionStatus.CANCELLED,
    },
    TransactionStatus.DONE: {
        TransactionStatus.IN_PROGRESS,
        TransactionStatus.PAID,
        TransactionStatus.CANCELLED,
    },
}
