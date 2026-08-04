from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PaymentMethod


class PaymentCreateBody(BaseModel):
    """Payment payload without transaction_id (set by path / parent create)."""

    payment_method: PaymentMethod
    amount: Decimal = Field(gt=0)
    amount_tendered: Decimal | None = Field(default=None, ge=0)
    change_due: Decimal | None = Field(default=None, ge=0)
    reference_no: str | None = Field(default=None, max_length=100)
    proof_image_url: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_method_fields(self) -> "PaymentCreateBody":
        if self.payment_method == PaymentMethod.CASH:
            if self.amount_tendered is None:
                raise ValueError("amount_tendered is required for CASH payments")
            if self.amount_tendered < self.amount:
                raise ValueError("amount_tendered must be >= amount for CASH payments")
            if self.change_due is None:
                self.change_due = self.amount_tendered - self.amount
        if self.payment_method == PaymentMethod.GCASH:
            if not (self.reference_no and self.reference_no.strip()):
                raise ValueError("reference_no is required for GCASH payments")
            if not (self.proof_image_url and self.proof_image_url.strip()):
                raise ValueError("proof_image_url is required for GCASH payments")
        return self


class PaymentCreate(PaymentCreateBody):
    transaction_id: UUID


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    payment_method: PaymentMethod
    amount: Decimal
    amount_tendered: Decimal | None
    change_due: Decimal | None
    received_by_id: UUID
    paid_at: datetime
    reference_no: str | None
    proof_image_url: str | None
    notes: str | None
    created_at: datetime
