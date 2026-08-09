"""shop settings branding

Revision ID: 0007_shop_settings
Revises: 0006_rv_doc_width
Create Date: 2026-08-09 12:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_shop_settings"
down_revision: Union[str, None] = "0006_rv_doc_width"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_name", sa.String(length=120), nullable=False),
        sa.Column("primary_color", sa.String(length=7), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO shop_settings (id, business_name, primary_color) "
            "VALUES (1, 'MotoShop RMS', '#C26A1A')"
        )
    )


def downgrade() -> None:
    op.drop_table("shop_settings")
