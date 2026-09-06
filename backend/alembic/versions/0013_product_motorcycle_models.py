"""product applicable motorcycle models

Revision ID: 0013_product_motorcycle_models
Revises: 0012_product_brands
Create Date: 2026-09-06 10:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_product_motorcycle_models"
down_revision: Union[str, None] = "0012_product_brands"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_motorcycle_models",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("motorcycle_model_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["motorcycle_model_id"],
            ["motorcycle_models.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_id", "motorcycle_model_id"),
    )
    op.create_index(
        "ix_product_motorcycle_models_motorcycle_model_id",
        "product_motorcycle_models",
        ["motorcycle_model_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_motorcycle_models_motorcycle_model_id",
        table_name="product_motorcycle_models",
    )
    op.drop_table("product_motorcycle_models")
