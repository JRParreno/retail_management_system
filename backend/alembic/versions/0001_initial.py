"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-04 23:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", "CASHIER", name="role", native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "mechanics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("nickname", sa.String(length=80), nullable=False),
        sa.Column("default_commission_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "product_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "document_number_sequences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "prefix",
            sa.Enum("INV", "JO", "RV", name="document_prefix", native_enum=False),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix", "year", name="uq_document_sequence_prefix_year"),
    )

    op.create_table(
        "cashier_shifts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cashier_id", sa.UUID(), nullable=False),
        sa.Column("opening_float", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("closing_cash_counted", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("expected_cash", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "status",
            sa.Enum("OPEN", "CLOSED", name="shift_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cashier_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cashier_shifts_cashier_id"), "cashier_shifts", ["cashier_id"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("cost_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("current_selling_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stock_qty", sa.Integer(), nullable=False),
        sa.Column("min_stock_threshold", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_barcode"), "products", ["barcode"], unique=True)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("LOW_STOCK", name="notification_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("DIRECT_SALE", "SERVICE_JOB", name="transaction_type", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "IN_PROGRESS",
                "DONE",
                "PAID",
                "CANCELLED",
                name="transaction_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("cashier_id", sa.UUID(), nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=True),
        sa.Column("customer_name", sa.String(length=150), nullable=True),
        sa.Column("customer_phone", sa.String(length=40), nullable=True),
        sa.Column("motorcycle_model", sa.String(length=120), nullable=True),
        sa.Column("plate_number", sa.String(length=32), nullable=True),
        sa.Column("motorcycle_color", sa.String(length=60), nullable=True),
        sa.Column("odometer_km", sa.Integer(), nullable=True),
        sa.Column("diagnosis_notes", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("estimated_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount_reason", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cashier_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shift_id"], ["cashier_shifts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_cashier_id"), "transactions", ["cashier_id"], unique=False)
    op.create_index(op.f("ix_transactions_document_number"), "transactions", ["document_number"], unique=True)
    op.create_index(op.f("ix_transactions_plate_number"), "transactions", ["plate_number"], unique=False)
    op.create_index(op.f("ix_transactions_status"), "transactions", ["status"], unique=False)

    op.create_table(
        "transaction_part_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("cost_price_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("original_selling_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("actual_selling_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("override_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transaction_part_lines_transaction_id"),
        "transaction_part_lines",
        ["transaction_id"],
        unique=False,
    )

    op.create_table(
        "transaction_labor_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("labor_fee", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("mechanic_id", sa.UUID(), nullable=True),
        sa.Column("mechanic_commission_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("mechanic_payout_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("original_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("actual_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("override_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mechanic_id"], ["mechanics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transaction_labor_lines_mechanic_id"),
        "transaction_labor_lines",
        ["mechanic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_labor_lines_transaction_id"),
        "transaction_labor_lines",
        ["transaction_id"],
        unique=False,
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum(
                "CASH",
                "GCASH",
                "BANK_TRANSFER",
                "CARD",
                "OTHER",
                name="payment_method",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amount_tendered", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("change_due", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("received_by_id", sa.UUID(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reference_no", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["received_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_transaction_id"), "payments", ["transaction_id"], unique=False)

    op.create_table(
        "return_voids",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_number", sa.String(length=32), nullable=False),
        sa.Column("original_transaction_id", sa.UUID(), nullable=False),
        sa.Column(
            "return_type",
            sa.Enum("VOID", "PARTIAL_RETURN", name="return_type", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("COMPLETED", name="return_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("processed_by_id", sa.UUID(), nullable=False),
        sa.Column("cashier_id", sa.UUID(), nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cashier_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["original_transaction_id"], ["transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["processed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shift_id"], ["cashier_shifts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_return_voids_document_number"),
        "return_voids",
        ["document_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_return_voids_original_transaction_id"),
        "return_voids",
        ["original_transaction_id"],
        unique=False,
    )

    op.create_table(
        "return_void_part_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("return_void_id", sa.UUID(), nullable=False),
        sa.Column("original_part_line_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("restock", sa.Boolean(), nullable=False),
        sa.Column("unit_refund_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cost_price_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["original_part_line_id"],
            ["transaction_part_lines.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["return_void_id"], ["return_voids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_return_void_part_lines_return_void_id"),
        "return_void_part_lines",
        ["return_void_id"],
        unique=False,
    )

    op.create_table(
        "return_void_labor_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("return_void_id", sa.UUID(), nullable=False),
        sa.Column("original_labor_line_id", sa.UUID(), nullable=True),
        sa.Column("mechanic_id", sa.UUID(), nullable=True),
        sa.Column("refund_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("commission_reversal_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["original_labor_line_id"],
            ["transaction_labor_lines.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["mechanic_id"], ["mechanics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["return_void_id"], ["return_voids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_return_void_labor_lines_return_void_id"),
        "return_void_labor_lines",
        ["return_void_id"],
        unique=False,
    )

    op.create_table(
        "stock_adjustments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column(
            "adjustment_type",
            sa.Enum(
                "IN",
                "OUT",
                "SET",
                "SALE",
                "RETURN",
                "REVERSAL",
                name="stock_adjustment_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("qty_before", sa.Integer(), nullable=False),
        sa.Column("qty_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("adjusted_by_id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column("return_void_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["adjusted_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["return_void_id"], ["return_voids.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stock_adjustments_product_id"),
        "stock_adjustments",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_adjustments_product_id"), table_name="stock_adjustments")
    op.drop_table("stock_adjustments")
    op.drop_index(op.f("ix_return_void_labor_lines_return_void_id"), table_name="return_void_labor_lines")
    op.drop_table("return_void_labor_lines")
    op.drop_index(op.f("ix_return_void_part_lines_return_void_id"), table_name="return_void_part_lines")
    op.drop_table("return_void_part_lines")
    op.drop_index(op.f("ix_return_voids_original_transaction_id"), table_name="return_voids")
    op.drop_index(op.f("ix_return_voids_document_number"), table_name="return_voids")
    op.drop_table("return_voids")
    op.drop_index(op.f("ix_payments_transaction_id"), table_name="payments")
    op.drop_table("payments")
    op.drop_index(op.f("ix_transaction_labor_lines_transaction_id"), table_name="transaction_labor_lines")
    op.drop_index(op.f("ix_transaction_labor_lines_mechanic_id"), table_name="transaction_labor_lines")
    op.drop_table("transaction_labor_lines")
    op.drop_index(op.f("ix_transaction_part_lines_transaction_id"), table_name="transaction_part_lines")
    op.drop_table("transaction_part_lines")
    op.drop_index(op.f("ix_transactions_status"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_plate_number"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_document_number"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_cashier_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_barcode"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_cashier_shifts_cashier_id"), table_name="cashier_shifts")
    op.drop_table("cashier_shifts")
    op.drop_table("document_number_sequences")
    op.drop_table("product_categories")
    op.drop_table("mechanics")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
