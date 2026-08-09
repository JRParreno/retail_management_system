import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ShiftStatus


class CashierShift(Base):
    __tablename__ = "cashier_shifts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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
    opening_float: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    closing_cash_counted: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus, name="shift_status", native_enum=False),
        nullable=False,
        default=ShiftStatus.OPEN,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_timing: Mapped[str | None] = mapped_column(String(20), nullable=True)
    close_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_mechanic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mechanics.id", ondelete="SET NULL"),
        nullable=True,
    )

    cashier = relationship("User", back_populates="shifts")
    branch = relationship("Branch")
    first_mechanic = relationship("Mechanic", foreign_keys=[first_mechanic_id])
    transactions = relationship("Transaction", back_populates="shift")
    return_voids = relationship("ReturnVoid", back_populates="shift")
