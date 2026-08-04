from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StockAdjustmentType


class StockAdjustRequest(BaseModel):
    quantity_delta: int
    reason: str | None = Field(default=None, max_length=255)


class StockAdjustmentCreate(BaseModel):
    product_id: UUID
    adjustment_type: StockAdjustmentType
    quantity_delta: int
    reason: str | None = Field(default=None, max_length=255)
    transaction_id: UUID | None = None
    return_void_id: UUID | None = None


class StockAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    adjustment_type: StockAdjustmentType
    quantity_delta: int
    qty_before: int
    qty_after: int
    reason: str | None
    adjusted_by_id: UUID
    transaction_id: UUID | None
    return_void_id: UUID | None
    created_at: datetime
