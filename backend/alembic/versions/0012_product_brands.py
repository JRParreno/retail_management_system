"""product brands catalog

Revision ID: 0012_product_brands
Revises: 0011_motorcycle_models
Create Date: 2026-08-11 23:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_product_brands"
down_revision: Union[str, None] = "0011_motorcycle_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_brands",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    # Backfill from existing product.brand values
    op.execute(
        sa.text(
            """
            INSERT INTO product_brands (id, name, created_at)
            SELECT gen_random_uuid(), b.brand, now()
            FROM (
              SELECT DISTINCT TRIM(brand) AS brand
              FROM products
              WHERE brand IS NOT NULL AND TRIM(brand) <> ''
            ) b
            ON CONFLICT (name) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("product_brands")
