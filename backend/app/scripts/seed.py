"""Seed demo data. Run from backend cwd: python -m app.scripts.seed"""

from decimal import Decimal

from sqlalchemy import select

from app.core.deps import MAIN_BRANCH_ID
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.branch import Branch, BranchStock
from app.models.enums import Role
from app.models.mechanic import Mechanic
from app.models.product import Product, ProductCategory
from app.models.user import User


def _ensure_main_branch(db) -> Branch:
    branch = db.get(Branch, MAIN_BRANCH_ID)
    if branch is None:
        branch = db.scalar(select(Branch).where(Branch.code == "MAIN"))
    if branch is None:
        branch = Branch(id=MAIN_BRANCH_ID, code="MAIN", name="Main", is_active=True)
        db.add(branch)
        db.flush()
        print("Created branch: MAIN")
    return branch


def seed() -> None:
    db = SessionLocal()
    try:
        main_branch = _ensure_main_branch(db)

        admin = db.scalar(select(User).where(User.username == "admin"))
        if admin is None:
            db.add(
                User(
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    full_name="Shop Admin",
                    role=Role.ADMIN,
                    branch_id=main_branch.id,
                )
            )
            print("Created user: admin / admin123")
        else:
            print("User admin already exists")
            if admin.branch_id is None:
                admin.branch_id = main_branch.id
                print("Assigned admin to branch: MAIN")

        cashier = db.scalar(select(User).where(User.username == "cashier"))
        if cashier is None:
            db.add(
                User(
                    username="cashier",
                    hashed_password=get_password_hash("cashier123"),
                    full_name="Front Cashier",
                    role=Role.CASHIER,
                    branch_id=main_branch.id,
                )
            )
            print("Created user: cashier / cashier123")
        else:
            print("User cashier already exists")
            if cashier.branch_id is None:
                cashier.branch_id = main_branch.id
                print("Assigned cashier to branch: MAIN")

        mechanic_specs = [
            ("Juan Dela Cruz", "Juan", Decimal("0.1500")),
            ("Pedro Santos", "Ped", Decimal("0.1800")),
            ("Miguel Reyes", "Migz", Decimal("0.1200")),
        ]
        for full_name, nickname, rate in mechanic_specs:
            exists = db.scalar(select(Mechanic).where(Mechanic.nickname == nickname))
            if exists is None:
                db.add(
                    Mechanic(
                        full_name=full_name,
                        nickname=nickname,
                        default_commission_rate=rate,
                    )
                )
                print(f"Created mechanic: {nickname}")

        cat_parts = db.scalar(select(ProductCategory).where(ProductCategory.name == "Parts"))
        if cat_parts is None:
            cat_parts = ProductCategory(name="Parts")
            db.add(cat_parts)
            db.flush()
            print("Created category: Parts")

        cat_fluids = db.scalar(select(ProductCategory).where(ProductCategory.name == "Fluids"))
        if cat_fluids is None:
            cat_fluids = ProductCategory(name="Fluids")
            db.add(cat_fluids)
            db.flush()
            print("Created category: Fluids")

        products = [
            ("OIL-10W40-1L", "Motul 10W-40 1L", "Motul", Decimal("280.00"), Decimal("420.00"), 24, 5, cat_fluids.id),
            ("OIL-20W50-1L", "Castrol 20W-50 1L", "Castrol", Decimal("220.00"), Decimal("350.00"), 18, 4, cat_fluids.id),
            ("BRK-PAD-FS", "Brake Pad Front Set", "Brembo", Decimal("450.00"), Decimal("780.00"), 12, 3, cat_parts.id),
            ("CHAIN-428H", "Drive Chain 428H", "DID", Decimal("520.00"), Decimal("890.00"), 8, 2, cat_parts.id),
            ("SPARK-NGK-CR7", "NGK Spark Plug CR7HSA", "NGK", Decimal("95.00"), Decimal("180.00"), 40, 10, cat_parts.id),
            ("FILT-AIR-STD", "Air Filter Standard", "K&N", Decimal("120.00"), Decimal("250.00"), 15, 4, cat_parts.id),
            ("CABLE-THR", "Throttle Cable", "OEM", Decimal("85.00"), Decimal("160.00"), 20, 5, cat_parts.id),
            ("BULB-H4", "Headlight Bulb H4", "Philips", Decimal("60.00"), Decimal("120.00"), 30, 8, cat_parts.id),
        ]
        for barcode, name, brand, cost, sell, qty, thresh, cat_id in products:
            product = db.scalar(select(Product).where(Product.barcode == barcode))
            if product is None:
                product = Product(
                    barcode=barcode,
                    name=name,
                    brand=brand,
                    cost_price=cost,
                    current_selling_price=sell,
                    stock_qty=qty,
                    min_stock_threshold=thresh,
                    category_id=cat_id,
                )
                db.add(product)
                db.flush()
                print(f"Created product: {barcode}")
            elif not product.brand:
                product.brand = brand
                print(f"Updated brand for: {barcode} -> {brand}")

            branch_stock = db.scalar(
                select(BranchStock).where(
                    BranchStock.branch_id == main_branch.id,
                    BranchStock.product_id == product.id,
                )
            )
            if branch_stock is None:
                db.add(
                    BranchStock(
                        branch_id=main_branch.id,
                        product_id=product.id,
                        stock_qty=qty,
                        min_stock_threshold=thresh,
                    )
                )
                print(f"Created branch stock for {barcode} @ Main")

        from app.scripts.seed_motorcycle_models import seed_motorcycle_models

        db.commit()
        print("Demo seed items committed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    seed_motorcycle_models()
    print("Seed complete.")


if __name__ == "__main__":
    seed()
