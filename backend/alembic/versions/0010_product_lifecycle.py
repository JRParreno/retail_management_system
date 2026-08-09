"""product lifecycle soft delete

Revision ID: 0010_product_lifecycle
Revises: 0009_first_mechanic_commission
Create Date: 2026-08-09 17:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_product_lifecycle"
down_revision: Union[str, None] = "0009_first_mechanic_commission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_products_deleted_at",
        "products",
        ["deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_products_deleted_at", table_name="products")
    op.drop_column("products", "deleted_at")
