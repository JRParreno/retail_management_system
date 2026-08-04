from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DocumentPrefix, ReturnStatus, ReturnType


class DocumentNumberSequenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prefix: DocumentPrefix
    year: int
    last_value: int


class ReturnVoidPartLineCreate(BaseModel):
    original_part_line_id: UUID | None = None
    product_id: UUID
    quantity: int = Field(ge=1)
    restock: bool = True
    unit_refund_amount: Decimal = Field(ge=0)
    cost_price_snapshot: Decimal = Field(default=Decimal("0.00"), ge=0)


class ReturnVoidLaborLineCreate(BaseModel):
    original_labor_line_id: UUID | None = None
    mechanic_id: UUID | None = None
    refund_amount: Decimal = Field(ge=0)
    commission_reversal_amount: Decimal = Field(default=Decimal("0.00"), ge=0)


class ReturnVoidCreate(BaseModel):
    original_transaction_id: UUID
    return_type: ReturnType = ReturnType.PARTIAL_RETURN
    reason: str = Field(min_length=1)
    shift_id: UUID | None = None
    part_lines: list[ReturnVoidPartLineCreate] = Field(default_factory=list)
    labor_lines: list[ReturnVoidLaborLineCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_lines(self) -> "ReturnVoidCreate":
        if not self.part_lines and not self.labor_lines:
            raise ValueError("At least one part or labor line is required")
        return self


class ReturnVoidPartLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    return_void_id: UUID
    original_part_line_id: UUID | None
    product_id: UUID
    quantity: int
    restock: bool
    unit_refund_amount: Decimal
    cost_price_snapshot: Decimal


class ReturnVoidLaborLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    return_void_id: UUID
    original_labor_line_id: UUID | None
    mechanic_id: UUID | None
    refund_amount: Decimal
    commission_reversal_amount: Decimal


class ReturnVoidRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_number: str
    original_transaction_id: UUID
    return_type: ReturnType
    status: ReturnStatus
    reason: str
    processed_by_id: UUID
    cashier_id: UUID
    shift_id: UUID | None
    created_at: datetime
    part_lines: list[ReturnVoidPartLineRead] = Field(default_factory=list)
    labor_lines: list[ReturnVoidLaborLineRead] = Field(default_factory=list)


class RefundablePartLine(BaseModel):
    part_line_id: UUID
    product_id: UUID
    product_name: str | None = None
    barcode: str | None = None
    original_qty: int
    returned_qty: int
    remaining_qty: int
    unit_price: Decimal
    cost_price: Decimal


class RefundableLaborLine(BaseModel):
    labor_line_id: UUID
    service_name: str
    mechanic_id: UUID | None
    actual_price: Decimal
    mechanic_payout_amount: Decimal
    already_refunded: bool


class RefundableSnapshot(BaseModel):
    transaction_id: UUID
    document_number: str
    status: str
    branch_id: UUID
    part_lines: list[RefundablePartLine]
    labor_lines: list[RefundableLaborLine]
