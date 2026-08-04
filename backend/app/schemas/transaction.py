from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TransactionStatus, TransactionType
from app.schemas.payment import PaymentCreateBody, PaymentRead


class PartLineInput(BaseModel):
    """Part line where prices snapshot from product unless overridden."""

    product_id: UUID
    quantity: int = Field(ge=1)
    actual_selling_price: Decimal | None = Field(default=None, ge=0)
    override_reason: str | None = Field(default=None, max_length=255)


class LaborLineInput(BaseModel):
    """Labor line; commission rate copied from mechanic when omitted."""

    service_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    original_price: Decimal = Field(ge=0)
    actual_price: Decimal | None = Field(default=None, ge=0)
    override_reason: str | None = Field(default=None, max_length=255)
    mechanic_id: UUID | None = None
    mechanic_commission_rate: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def default_actual_and_override(self) -> "LaborLineInput":
        if self.actual_price is None:
            self.actual_price = self.original_price
        if self.actual_price != self.original_price and not (
            self.override_reason and self.override_reason.strip()
        ):
            raise ValueError("override_reason is required when labor price is overridden")
        return self


class TransactionPartLineCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1)
    cost_price_snapshot: Decimal = Field(ge=0)
    original_selling_price: Decimal = Field(ge=0)
    actual_selling_price: Decimal = Field(ge=0)
    override_reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def require_override_reason(self) -> "TransactionPartLineCreate":
        if (
            self.actual_selling_price != self.original_selling_price
            and not (self.override_reason and self.override_reason.strip())
        ):
            raise ValueError("override_reason is required when selling price is overridden")
        return self


class TransactionPartLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    product_id: UUID
    quantity: int
    cost_price_snapshot: Decimal
    original_selling_price: Decimal
    actual_selling_price: Decimal
    override_reason: str | None
    created_at: datetime


class TransactionLaborLineCreate(BaseModel):
    service_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    labor_fee: Decimal = Field(ge=0)
    mechanic_id: UUID | None = None
    mechanic_commission_rate: Decimal | None = Field(default=None, ge=0, le=1)
    mechanic_payout_amount: Decimal | None = Field(default=None, ge=0)
    original_price: Decimal = Field(ge=0)
    actual_price: Decimal = Field(ge=0)
    override_reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def require_override_reason(self) -> "TransactionLaborLineCreate":
        if self.actual_price != self.original_price and not (
            self.override_reason and self.override_reason.strip()
        ):
            raise ValueError("override_reason is required when labor price is overridden")
        return self


class TransactionLaborLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    service_name: str
    description: str | None
    labor_fee: Decimal
    mechanic_id: UUID | None
    mechanic_commission_rate: Decimal | None
    mechanic_payout_amount: Decimal | None
    original_price: Decimal
    actual_price: Decimal
    override_reason: str | None
    created_at: datetime


class TransactionCreate(BaseModel):
    transaction_type: TransactionType
    status: TransactionStatus
    shift_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=40)
    motorcycle_model: str | None = Field(default=None, max_length=120)
    plate_number: str | None = Field(default=None, max_length=32)
    motorcycle_color: str | None = Field(default=None, max_length=60)
    odometer_km: int | None = Field(default=None, ge=0)
    diagnosis_notes: str | None = None
    internal_notes: str | None = None
    estimated_total: Decimal | None = Field(default=None, ge=0)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount_reason: str | None = Field(default=None, max_length=255)
    part_lines: list[TransactionPartLineCreate] = Field(default_factory=list)
    labor_lines: list[TransactionLaborLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_service_job_and_discount(self) -> "TransactionCreate":
        if self.transaction_type == TransactionType.SERVICE_JOB:
            required = {
                "customer_name": self.customer_name,
                "customer_phone": self.customer_phone,
                "motorcycle_model": self.motorcycle_model,
                "plate_number": self.plate_number,
            }
            missing = [k for k, v in required.items() if not (v and str(v).strip())]
            if missing:
                raise ValueError(
                    f"SERVICE_JOB requires: {', '.join(missing)}"
                )
        if self.discount_amount > 0 and not (
            self.discount_reason and self.discount_reason.strip()
        ):
            raise ValueError("discount_reason is required when discount_amount > 0")
        return self


class TransactionUpdate(BaseModel):
    status: TransactionStatus | None = None
    customer_name: str | None = Field(default=None, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=40)
    motorcycle_model: str | None = Field(default=None, max_length=120)
    plate_number: str | None = Field(default=None, max_length=32)
    motorcycle_color: str | None = Field(default=None, max_length=60)
    odometer_km: int | None = Field(default=None, ge=0)
    diagnosis_notes: str | None = None
    internal_notes: str | None = None
    estimated_total: Decimal | None = Field(default=None, ge=0)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    discount_reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_discount(self) -> "TransactionUpdate":
        if (
            self.discount_amount is not None
            and self.discount_amount > 0
            and not (self.discount_reason and self.discount_reason.strip())
        ):
            raise ValueError("discount_reason is required when discount_amount > 0")
        return self


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_number: str
    transaction_type: TransactionType
    status: TransactionStatus
    cashier_id: UUID
    shift_id: UUID | None
    customer_name: str | None
    customer_phone: str | None
    motorcycle_model: str | None
    plate_number: str | None
    motorcycle_color: str | None
    odometer_km: int | None
    diagnosis_notes: str | None
    internal_notes: str | None
    estimated_total: Decimal | None
    discount_amount: Decimal
    discount_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime
    part_lines: list[TransactionPartLineRead] = Field(default_factory=list)
    labor_lines: list[TransactionLaborLineRead] = Field(default_factory=list)


class TransactionTotals(BaseModel):
    parts_total: Decimal
    labor_total: Decimal
    gross_total: Decimal
    discount_amount: Decimal
    net_total: Decimal
    paid_total: Decimal
    balance_due: Decimal


class TransactionDetailRead(TransactionRead):
    payments: list[PaymentRead] = Field(default_factory=list)
    totals: TransactionTotals


class ServiceJobCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=150)
    customer_phone: str = Field(min_length=1, max_length=40)
    motorcycle_model: str = Field(min_length=1, max_length=120)
    plate_number: str = Field(min_length=1, max_length=32)
    motorcycle_color: str | None = Field(default=None, max_length=60)
    odometer_km: int | None = Field(default=None, ge=0)
    diagnosis_notes: str | None = None
    internal_notes: str | None = None
    estimated_total: Decimal | None = Field(default=None, ge=0)


class DirectSaleCreate(BaseModel):
    part_lines: list[PartLineInput] = Field(min_length=1)
    payment: PaymentCreateBody
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    discount_reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_discount(self) -> "DirectSaleCreate":
        if self.discount_amount > 0 and not (
            self.discount_reason and self.discount_reason.strip()
        ):
            raise ValueError("discount_reason is required when discount_amount > 0")
        return self


class StatusUpdate(BaseModel):
    status: TransactionStatus
