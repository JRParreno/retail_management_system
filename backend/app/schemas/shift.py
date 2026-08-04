from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ShiftStatus


class CashierShiftOpen(BaseModel):
    opening_float: Decimal = Field(default=Decimal("0.00"), ge=0)


class CashierShiftClose(BaseModel):
    closing_cash_counted: Decimal = Field(ge=0)
    expected_cash: Decimal | None = Field(default=None, ge=0)
    close_notes: str | None = None


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
    close_notes: str | None
