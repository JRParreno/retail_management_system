from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TransactionStatus


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
    document_number: str | None = None
    service_name: str
    description: str | None = None
    original_price: Decimal
    actual_price: Decimal
    mechanic_commission_rate: Decimal | None
    mechanic_payout_amount: Decimal | None
    customer_name: str | None = None
    customer_phone: str | None = None
    motorcycle_model: str | None = None
    plate_number: str | None = None
    motorcycle_color: str | None = None
    created_at: datetime
    paid_at: datetime | None = None


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


class MechanicLaborBoardRow(BaseModel):
    mechanic_id: UUID | None = None
    full_name: str
    nickname: str
    is_active: bool
    job_count: int
    line_count: int
    labor_total: Decimal


class MechanicLaborBoardRead(BaseModel):
    start_date: date
    end_date: date
    mechanic_count: int
    job_count: int
    line_count: int
    labor_total: Decimal
    mechanics: list[MechanicLaborBoardRow] = Field(default_factory=list)


class MechanicLaborWorkLine(MechanicProfileLaborLine):
    transaction_status: TransactionStatus | None = None


class MechanicLaborWorkRead(BaseModel):
    mechanic_id: UUID | None = None
    full_name: str
    nickname: str
    is_active: bool
    start_date: date
    end_date: date
    job_count: int
    line_count: int
    labor_total: Decimal
    lines: list[MechanicLaborWorkLine] = Field(default_factory=list)
