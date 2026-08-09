from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ShiftCloseTiming, ShiftStatus


class CashierShiftOpen(BaseModel):
    opening_float: Decimal = Field(default=Decimal("0.00"), ge=0)
    """Expected end time as HH:MM (local). Can be earlier or later than shop default."""
    scheduled_end_time: str | None = Field(default=None, min_length=5, max_length=5)


class CashierShiftClose(BaseModel):
    closing_cash_counted: Decimal = Field(default=Decimal("0.00"), ge=0)
    expected_cash: Decimal | None = Field(default=None, ge=0)
    close_timing: ShiftCloseTiming | None = None
    close_notes: str | None = None
    """When shop policy is on, waive first mechanic commission before closing."""
    apply_first_mechanic_waiver: bool = False
    first_mechanic_id: UUID | None = None


class CashierShiftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cashier_id: UUID
    opening_float: Decimal
    closing_cash_counted: Decimal | None
    expected_cash: Decimal | None
    status: ShiftStatus
    opened_at: datetime
    closed_at: datetime | None
    scheduled_end_at: datetime | None
    close_timing: str | None
    close_notes: str | None
    first_mechanic_id: UUID | None = None
