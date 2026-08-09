"""cashier shift schedule times

Revision ID: 0008_cashier_shift_schedule
Revises: 0007_shop_settings
Create Date: 2026-08-09 16:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_cashier_shift_schedule"
down_revision: Union[str, None] = "0007_shop_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shop_settings",
        sa.Column(
            "cashier_shift_start",
            sa.String(length=5),
            nullable=False,
            server_default="08:00",
        ),
    )
    op.add_column(
        "shop_settings",
        sa.Column(
            "cashier_shift_end",
            sa.String(length=5),
            nullable=False,
            server_default="17:00",
        ),
    )
    op.add_column(
        "cashier_shifts",
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cashier_shifts",
        sa.Column("close_timing", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cashier_shifts", "close_timing")
    op.drop_column("cashier_shifts", "scheduled_end_at")
    op.drop_column("shop_settings", "cashier_shift_end")
    op.drop_column("shop_settings", "cashier_shift_start")
