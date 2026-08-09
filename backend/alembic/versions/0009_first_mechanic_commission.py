"""first mechanic commission waiver policy

Revision ID: 0009_first_mechanic_commission
Revises: 0008_cashier_shift_schedule
Create Date: 2026-08-09 16:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_first_mechanic_commission"
down_revision: Union[str, None] = "0008_cashier_shift_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shop_settings",
        sa.Column(
            "waive_first_mechanic_commission",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "transaction_labor_lines",
        sa.Column(
            "commission_waived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "transaction_labor_lines",
        sa.Column(
            "mechanic_payout_gross",
            sa.Numeric(12, 2),
            nullable=True,
        ),
    )
    op.add_column(
        "cashier_shifts",
        sa.Column(
            "first_mechanic_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_cashier_shifts_first_mechanic_id",
        "cashier_shifts",
        "mechanics",
        ["first_mechanic_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cashier_shifts_first_mechanic_id",
        "cashier_shifts",
        type_="foreignkey",
    )
    op.drop_column("cashier_shifts", "first_mechanic_id")
    op.drop_column("transaction_labor_lines", "mechanic_payout_gross")
    op.drop_column("transaction_labor_lines", "commission_waived")
    op.drop_column("shop_settings", "waive_first_mechanic_commission")
