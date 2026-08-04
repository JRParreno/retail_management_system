"""widen stock_adjustments.adjustment_type to fit TRANSFER_OUT/TRANSFER_IN

Revision ID: 0005_widen_adj_type
Revises: 0004_branches
Create Date: 2026-08-05 01:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_widen_adj_type"
down_revision: Union[str, None] = "0004_branches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "stock_adjustments",
        "adjustment_type",
        existing_type=sa.String(length=8),
        type_=sa.String(length=20),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "stock_adjustments",
        "adjustment_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=8),
        existing_nullable=False,
    )
