"""multi-branch foundation

Revision ID: 0004_branches
Revises: 0003_product_brand
Create Date: 2026-08-05 01:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_branches"
down_revision: Union[str, None] = "0003_product_brand"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_branches_code"), "branches", ["code"], unique=True)

    # Seed Main branch
    op.execute(
        sa.text(
            """
            INSERT INTO branches (id, code, name, address, phone, is_active)
            VALUES (
              '11111111-1111-1111-1111-111111111111',
              'MAIN',
              'Main',
              NULL,
              NULL,
              true
            )
            """
        )
    )

    op.create_table(
        "branch_stocks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("stock_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_stock_threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "product_id", name="uq_branch_stock_branch_product"),
    )
    op.create_index(op.f("ix_branch_stocks_branch_id"), "branch_stocks", ["branch_id"])
    op.create_index(op.f("ix_branch_stocks_product_id"), "branch_stocks", ["product_id"])

    op.create_table(
        "branch_prices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "product_id", name="uq_branch_price_branch_product"),
    )
    op.create_index(op.f("ix_branch_prices_branch_id"), "branch_prices", ["branch_id"])
    op.create_index(op.f("ix_branch_prices_product_id"), "branch_prices", ["product_id"])

    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_number", sa.String(length=40), nullable=False),
        sa.Column("from_branch_id", sa.UUID(), nullable=False),
        sa.Column("to_branch_id", sa.UUID(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["from_branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_number"),
    )
    op.create_index(op.f("ix_stock_transfers_document_number"), "stock_transfers", ["document_number"])
    op.create_index(op.f("ix_stock_transfers_from_branch_id"), "stock_transfers", ["from_branch_id"])
    op.create_index(op.f("ix_stock_transfers_to_branch_id"), "stock_transfers", ["to_branch_id"])

    op.create_table(
        "stock_transfer_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transfer_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["transfer_id"], ["stock_transfers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stock_transfer_lines_transfer_id"),
        "stock_transfer_lines",
        ["transfer_id"],
    )

    # Backfill branch stock from products
    op.execute(
        sa.text(
            """
            INSERT INTO branch_stocks (id, branch_id, product_id, stock_qty, min_stock_threshold)
            SELECT gen_random_uuid(),
                   '11111111-1111-1111-1111-111111111111',
                   p.id,
                   p.stock_qty,
                   p.min_stock_threshold
            FROM products p
            """
        )
    )

    # Users.branch_id
    op.add_column("users", sa.Column("branch_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE users
            SET branch_id = '11111111-1111-1111-1111-111111111111'
            WHERE branch_id IS NULL
            """
        )
    )
    op.alter_column("users", "branch_id", nullable=False)
    op.create_foreign_key(
        "fk_users_branch_id",
        "users",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_users_branch_id"), "users", ["branch_id"])

    # Transactions.branch_id
    op.add_column("transactions", sa.Column("branch_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE transactions
            SET branch_id = '11111111-1111-1111-1111-111111111111'
            WHERE branch_id IS NULL
            """
        )
    )
    op.alter_column("transactions", "branch_id", nullable=False)
    op.create_foreign_key(
        "fk_transactions_branch_id",
        "transactions",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_transactions_branch_id"), "transactions", ["branch_id"])

    # Shifts.branch_id
    op.add_column("cashier_shifts", sa.Column("branch_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE cashier_shifts
            SET branch_id = '11111111-1111-1111-1111-111111111111'
            WHERE branch_id IS NULL
            """
        )
    )
    op.alter_column("cashier_shifts", "branch_id", nullable=False)
    op.create_foreign_key(
        "fk_cashier_shifts_branch_id",
        "cashier_shifts",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_cashier_shifts_branch_id"), "cashier_shifts", ["branch_id"])

    # Stock adjustments.branch_id
    op.add_column("stock_adjustments", sa.Column("branch_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE stock_adjustments
            SET branch_id = '11111111-1111-1111-1111-111111111111'
            WHERE branch_id IS NULL
            """
        )
    )
    op.alter_column("stock_adjustments", "branch_id", nullable=False)
    op.create_foreign_key(
        "fk_stock_adjustments_branch_id",
        "stock_adjustments",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_stock_adjustments_branch_id"), "stock_adjustments", ["branch_id"])

    # Document sequences: add branch_id, rebuild unique constraint
    op.add_column("document_number_sequences", sa.Column("branch_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE document_number_sequences
            SET branch_id = '11111111-1111-1111-1111-111111111111'
            WHERE branch_id IS NULL
            """
        )
    )
    op.alter_column("document_number_sequences", "branch_id", nullable=False)
    op.drop_constraint(
        "uq_document_sequence_prefix_year",
        "document_number_sequences",
        type_="unique",
    )
    op.create_foreign_key(
        "fk_document_number_sequences_branch_id",
        "document_number_sequences",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_document_number_sequences_branch_id"),
        "document_number_sequences",
        ["branch_id"],
    )
    op.create_unique_constraint(
        "uq_document_sequence_branch_prefix_year",
        "document_number_sequences",
        ["branch_id", "prefix", "year"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_document_sequence_branch_prefix_year",
        "document_number_sequences",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_document_number_sequences_branch_id"),
        table_name="document_number_sequences",
    )
    op.drop_constraint(
        "fk_document_number_sequences_branch_id",
        "document_number_sequences",
        type_="foreignkey",
    )
    op.drop_column("document_number_sequences", "branch_id")
    op.create_unique_constraint(
        "uq_document_sequence_prefix_year",
        "document_number_sequences",
        ["prefix", "year"],
    )

    op.drop_constraint("fk_stock_adjustments_branch_id", "stock_adjustments", type_="foreignkey")
    op.drop_index(op.f("ix_stock_adjustments_branch_id"), table_name="stock_adjustments")
    op.drop_column("stock_adjustments", "branch_id")

    op.drop_constraint("fk_cashier_shifts_branch_id", "cashier_shifts", type_="foreignkey")
    op.drop_index(op.f("ix_cashier_shifts_branch_id"), table_name="cashier_shifts")
    op.drop_column("cashier_shifts", "branch_id")

    op.drop_constraint("fk_transactions_branch_id", "transactions", type_="foreignkey")
    op.drop_index(op.f("ix_transactions_branch_id"), table_name="transactions")
    op.drop_column("transactions", "branch_id")

    op.drop_constraint("fk_users_branch_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_branch_id"), table_name="users")
    op.drop_column("users", "branch_id")

    op.drop_table("stock_transfer_lines")
    op.drop_table("stock_transfers")
    op.drop_table("branch_prices")
    op.drop_table("branch_stocks")
    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.drop_table("branches")
