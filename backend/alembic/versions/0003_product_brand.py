"""add product brand

Revision ID: 0003_product_brand
Revises: 0002_payment_proof
Create Date: 2026-08-05 00:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_product_brand"
down_revision: Union[str, None] = "0002_payment_proof"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("brand", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_products_brand"), "products", ["brand"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_brand"), table_name="products")
    op.drop_column("products", "brand")
