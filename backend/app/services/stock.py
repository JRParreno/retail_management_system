from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import BranchPrice, BranchStock
from app.models.product import Product


def get_or_create_branch_stock(
    db: Session,
    *,
    branch_id: UUID,
    product: Product,
) -> BranchStock:
    stock = db.scalar(
        select(BranchStock).where(
            BranchStock.branch_id == branch_id,
            BranchStock.product_id == product.id,
        )
    )
    if stock is None:
        stock = BranchStock(
            branch_id=branch_id,
            product_id=product.id,
            stock_qty=0,
            min_stock_threshold=product.min_stock_threshold,
        )
        db.add(stock)
        db.flush()
    return stock


def effective_selling_price(
    db: Session,
    *,
    branch_id: UUID,
    product: Product,
) -> Decimal:
    override = db.scalar(
        select(BranchPrice).where(
            BranchPrice.branch_id == branch_id,
            BranchPrice.product_id == product.id,
        )
    )
    if override is not None:
        return override.selling_price
    return product.current_selling_price
