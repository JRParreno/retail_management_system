"""Create or reset the default ADMIN user (and Main branch if missing).

Run from backend cwd:
  python -m app.scripts.seed_admin
"""

from app.scripts.seed_production import seed_production


def seed_admin(*, reset_password: bool = True) -> None:
    seed_production(reset_admin_password=reset_password)


if __name__ == "__main__":
    seed_admin(reset_password=True)
