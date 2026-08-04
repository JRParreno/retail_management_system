from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MechanicCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    nickname: str = Field(min_length=1, max_length=80)
    default_commission_rate: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    is_active: bool = True


class MechanicUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    default_commission_rate: Decimal | None = Field(default=None, ge=0, le=1)
    is_active: bool | None = None


class MechanicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    nickname: str
    default_commission_rate: Decimal
    is_active: bool
    created_at: datetime


class MechanicProfileLaborLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    service_name: str
    original_price: Decimal
    actual_price: Decimal
    mechanic_commission_rate: Decimal | None
    mechanic_payout_amount: Decimal | None
    created_at: datetime


class MechanicProfileRead(BaseModel):
    id: UUID
    full_name: str
    nickname: str
    default_commission_rate: Decimal
    is_active: bool
    start_date: date
    end_date: date
    job_count: int
    labor_sales: Decimal
    commission_total: Decimal
    recent_lines: list[MechanicProfileLaborLine] = Field(default_factory=list)
