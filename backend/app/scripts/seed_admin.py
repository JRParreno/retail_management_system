"""Create or reset the default ADMIN user.

Run from backend cwd:
  python -m app.scripts.seed_admin
"""

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.enums import Role
from app.models.user import User

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_FULL_NAME = "Shop Admin"


def seed_admin(*, reset_password: bool = True) -> None:
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.username == ADMIN_USERNAME))
        if admin is None:
            db.add(
                User(
                    username=ADMIN_USERNAME,
                    hashed_password=get_password_hash(ADMIN_PASSWORD),
                    full_name=ADMIN_FULL_NAME,
                    role=Role.ADMIN,
                    is_active=True,
                )
            )
            db.commit()
            print(f"Created ADMIN: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
            return

        admin.role = Role.ADMIN
        admin.is_active = True
        admin.full_name = admin.full_name or ADMIN_FULL_NAME
        if reset_password:
            admin.hashed_password = get_password_hash(ADMIN_PASSWORD)
        db.commit()
        action = "Reset" if reset_password else "Updated"
        print(f"{action} ADMIN: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin(reset_password=True)
