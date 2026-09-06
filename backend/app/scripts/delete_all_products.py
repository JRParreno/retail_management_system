"""Hard-delete ALL products from the database (permanent).

Removes related rows that would otherwise block deletion (transaction part
lines, stock adjustments, transfers, returns), then deletes every product.
Branch stock/prices and motorcycle fitment cascade with the product.

This cannot be undone.

Run from the backend folder:

  python -m app.scripts.delete_all_products

You will be asked to type yes or no before anything is deleted.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models.branch import BranchPrice, BranchStock, StockTransferLine
from app.models.inventory import StockAdjustment
from app.models.notification import Notification
from app.models.product import Product
from app.models.return_void import ReturnVoidPartLine
from app.models.transaction import TransactionPartLine


def _count(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _prompt_yes_no(message: str) -> bool:
    while True:
        answer = input(f"{message} [yes/no]: ").strip().casefold()
        if answer in {"yes", "y"}:
            return True
        if answer in {"no", "n"}:
            return False
        print('Please type "yes" or "no".')


def run() -> None:
    db = SessionLocal()
    try:
        product_count = _count(db, Product)
        part_lines = _count(db, TransactionPartLine)
        adjustments = _count(db, StockAdjustment)
        transfer_lines = _count(db, StockTransferLine)
        return_lines = _count(db, ReturnVoidPartLine)
        branch_stocks = _count(db, BranchStock)
        branch_prices = _count(db, BranchPrice)

        print("Hard delete ALL products (permanent)")
        print("-" * 60)
        print(f"  Products:               {product_count}")
        print(f"  Branch stock rows:      {branch_stocks}")
        print(f"  Branch price rows:      {branch_prices}")
        print(f"  Transaction part lines: {part_lines}")
        print(f"  Stock adjustments:      {adjustments}")
        print(f"  Transfer lines:         {transfer_lines}")
        print(f"  Return/void part lines: {return_lines}")
        print("-" * 60)
        print(
            "WARNING: This permanently removes every product and clears "
            "linked sales/stock history rows that reference them."
        )

        if product_count == 0:
            print("No products to delete.")
            return

        if not _prompt_yes_no("Hard-delete ALL products now?"):
            print("Cancelled. No changes made.")
            return

        if not _prompt_yes_no("Are you sure? Type yes to confirm hard delete"):
            print("Cancelled. No changes made.")
            return

        # Clear RESTRICT FKs first so product rows can be removed.
        deleted_part_lines = db.execute(delete(TransactionPartLine)).rowcount or 0
        deleted_returns = db.execute(delete(ReturnVoidPartLine)).rowcount or 0
        deleted_adjustments = db.execute(delete(StockAdjustment)).rowcount or 0
        deleted_transfers = db.execute(delete(StockTransferLine)).rowcount or 0
        db.execute(
            update(Notification)
            .where(Notification.product_id.is_not(None))
            .values(product_id=None)
        )
        deleted_stocks = db.execute(delete(BranchStock)).rowcount or 0
        deleted_prices = db.execute(delete(BranchPrice)).rowcount or 0
        deleted_products = db.execute(delete(Product)).rowcount or 0

        db.commit()

        print("Hard delete complete.")
        print(f"  Products deleted:               {deleted_products}")
        print(f"  Branch stock rows deleted:      {deleted_stocks}")
        print(f"  Branch price rows deleted:      {deleted_prices}")
        print(f"  Transaction part lines deleted: {deleted_part_lines}")
        print(f"  Stock adjustments deleted:      {deleted_adjustments}")
        print(f"  Transfer lines deleted:         {deleted_transfers}")
        print(f"  Return/void part lines deleted: {deleted_returns}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
