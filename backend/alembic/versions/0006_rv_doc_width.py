"""widen return_void document_number

Revision ID: 0006_rv_doc_width
Revises: 0005_widen_adj_type
Create Date: 2026-08-05 01:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_rv_doc_width"
down_revision: Union[str, None] = "0005_widen_adj_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "return_voids",
        "document_number",
        existing_type=sa.String(length=32),
        type_=sa.String(length=40),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "return_voids",
        "document_number",
        existing_type=sa.String(length=40),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
