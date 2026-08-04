import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DocumentPrefix, ReturnStatus, ReturnType


class DocumentNumberSequence(Base):
    __tablename__ = "document_number_sequences"
    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "prefix",
            "year",
            name="uq_document_sequence_branch_prefix_year",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prefix: Mapped[DocumentPrefix] = mapped_column(
        Enum(DocumentPrefix, name="document_prefix", native_enum=False),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    branch = relationship("Branch")


class ReturnVoid(Base):
    __tablename__ = "return_voids"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_number: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False
    )
    original_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    return_type: Mapped[ReturnType] = mapped_column(
        Enum(ReturnType, name="return_type", native_enum=False),
        nullable=False,
    )
    status: Mapped[ReturnStatus] = mapped_column(
        Enum(ReturnStatus, name="return_status", native_enum=False),
        nullable=False,
        default=ReturnStatus.COMPLETED,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    processed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cashier_shifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    original_transaction = relationship("Transaction", back_populates="return_voids")
    processed_by = relationship(
        "User",
        back_populates="return_voids_processed",
        foreign_keys=[processed_by_id],
    )
    cashier = relationship("User", foreign_keys=[cashier_id])
    shift = relationship("CashierShift", back_populates="return_voids")
    part_lines = relationship(
        "ReturnVoidPartLine",
        back_populates="return_void",
        cascade="all, delete-orphan",
    )
    labor_lines = relationship(
        "ReturnVoidLaborLine",
        back_populates="return_void",
        cascade="all, delete-orphan",
    )
    stock_adjustments = relationship("StockAdjustment", back_populates="return_void")


class ReturnVoidPartLine(Base):
    __tablename__ = "return_void_part_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    return_void_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("return_voids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_part_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transaction_part_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    restock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    unit_refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    return_void = relationship("ReturnVoid", back_populates="part_lines")
    original_part_line = relationship("TransactionPartLine")
    product = relationship("Product")


class ReturnVoidLaborLine(Base):
    __tablename__ = "return_void_labor_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    return_void_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("return_voids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_labor_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transaction_labor_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    mechanic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mechanics.id", ondelete="RESTRICT"),
        nullable=True,
    )
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission_reversal_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    return_void = relationship("ReturnVoid", back_populates="labor_lines")
    original_labor_line = relationship("TransactionLaborLine")
    mechanic = relationship("Mechanic")
