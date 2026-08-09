"""motorcycle models catalog

Revision ID: 0011_motorcycle_models
Revises: 0010_product_lifecycle
Create Date: 2026-08-09 18:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_motorcycle_models"
down_revision: Union[str, None] = "0010_product_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "motorcycle_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand", "name", name="uq_motorcycle_models_brand_name"),
    )
    op.create_index("ix_motorcycle_models_brand", "motorcycle_models", ["brand"])
    op.create_index("ix_motorcycle_models_name", "motorcycle_models", ["name"])


def downgrade() -> None:
    op.drop_index("ix_motorcycle_models_name", table_name="motorcycle_models")
    op.drop_index("ix_motorcycle_models_brand", table_name="motorcycle_models")
    op.drop_table("motorcycle_models")
