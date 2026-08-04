import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TransactionStatus, TransactionType


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type", native_enum=False),
        nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status", native_enum=False),
        nullable=False,
        index=True,
    )
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cashier_shifts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # SERVICE_JOB identity fields (nullable for DIRECT_SALE)
    customer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    motorcycle_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    plate_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    motorcycle_color: Mapped[str | None] = mapped_column(String(60), nullable=True)
    odometer_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    diagnosis_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    estimated_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    discount_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cashier = relationship("User", back_populates="transactions", foreign_keys=[cashier_id])
    branch = relationship("Branch")
    shift = relationship("CashierShift", back_populates="transactions")
    part_lines = relationship(
        "TransactionPartLine",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    labor_lines = relationship(
        "TransactionLaborLine",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "Payment",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    stock_adjustments = relationship("StockAdjustment", back_populates="transaction")
    return_voids = relationship("ReturnVoid", back_populates="original_transaction")


class TransactionPartLine(Base):
    __tablename__ = "transaction_part_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    actual_selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    override_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaction = relationship("Transaction", back_populates="part_lines")
    product = relationship("Product", back_populates="part_lines")


class TransactionLaborLine(Base):
    __tablename__ = "transaction_labor_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    labor_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mechanic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mechanics.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # Snapshots locked at DONE/PAID (service layer)
    mechanic_commission_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    mechanic_payout_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    actual_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    override_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaction = relationship("Transaction", back_populates="labor_lines")
    mechanic = relationship("Mechanic", back_populates="labor_lines")
