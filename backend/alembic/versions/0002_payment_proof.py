"""add payment proof_image_url

Revision ID: 0002_payment_proof
Revises: 0001_initial
Create Date: 2026-08-05 00:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_payment_proof"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("proof_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "proof_image_url")
