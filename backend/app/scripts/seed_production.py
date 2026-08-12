"""Production bootstrap: Main branch + ADMIN + reference catalogs.

Seeds (idempotent — safe to re-run):
  - Main branch
  - Default ADMIN user
  - Product brands (scooter/parts catalog)
  - Motorcycle / scooter models

Does NOT seed demo products, mechanics, or cashier users.

Run from backend cwd:
  python -m app.scripts.seed_production
"""

from sqlalchemy import select

from app.core.deps import MAIN_BRANCH_ID
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.branch import Branch
from app.models.enums import Role
from app.models.user import User
from app.services.brands import list_brand_names, seed_default_brands

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_FULL_NAME = "Shop Admin"


def ensure_main_branch(db) -> Branch:
    branch = db.get(Branch, MAIN_BRANCH_ID)
    if branch is None:
        branch = db.scalar(select(Branch).where(Branch.code == "MAIN"))
    if branch is None:
        branch = Branch(
            id=MAIN_BRANCH_ID,
            code="MAIN",
            name="Main",
            is_active=True,
        )
        db.add(branch)
        db.flush()
        print("Created branch: MAIN")
    else:
        branch.is_active = True
        if not branch.name:
            branch.name = "Main"
    return branch


def seed_production(*, reset_admin_password: bool = True) -> None:
    """Create shop foundation + brand / motorcycle model catalogs."""
    db = SessionLocal()
    try:
        main_branch = ensure_main_branch(db)

        admin = db.scalar(select(User).where(User.username == ADMIN_USERNAME))
        if admin is None:
            db.add(
                User(
                    username=ADMIN_USERNAME,
                    hashed_password=get_password_hash(ADMIN_PASSWORD),
                    full_name=ADMIN_FULL_NAME,
                    role=Role.ADMIN,
                    branch_id=main_branch.id,
                    is_active=True,
                )
            )
            print(f"Created ADMIN: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
        else:
            admin.role = Role.ADMIN
            admin.is_active = True
            admin.full_name = admin.full_name or ADMIN_FULL_NAME
            admin.branch_id = main_branch.id
            if reset_admin_password:
                admin.hashed_password = get_password_hash(ADMIN_PASSWORD)
            print(
                f"{'Reset' if reset_admin_password else 'Updated'} ADMIN: "
                f"{ADMIN_USERNAME} / {ADMIN_PASSWORD}"
            )

        brand_created = seed_default_brands(db)
        brand_total = len(list_brand_names(db))
        if brand_created:
            print(f"Created {brand_created} product brand(s) (total {brand_total})")
        else:
            print(f"Product brands already seeded (total {brand_total})")

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    from app.scripts.seed_motorcycle_models import seed_motorcycle_models

    seed_motorcycle_models()
    print(
        "Production seed complete "
        "(Main branch + admin + brands + motorcycle/scooter models)."
    )


if __name__ == "__main__":
    seed_production(reset_admin_password=True)
