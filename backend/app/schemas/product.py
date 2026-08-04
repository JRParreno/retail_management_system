from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class ProductCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime


class ProductCreate(BaseModel):
    barcode: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=100)
    image_url: str | None = None
    cost_price: Decimal = Field(ge=0)
    current_selling_price: Decimal = Field(ge=0)
    stock_qty: int = Field(default=0, ge=0)
    min_stock_threshold: int = Field(default=0, ge=0)
    category_id: UUID | None = None
    is_active: bool = True

    @field_validator("barcode")
    @classmethod
    def strip_barcode(cls, value: str) -> str:
        return value.strip()

    @field_validator("brand")
    @classmethod
    def strip_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProductUpdate(BaseModel):
    barcode: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=100)
    image_url: str | None = None
    cost_price: Decimal | None = Field(default=None, ge=0)
    current_selling_price: Decimal | None = Field(default=None, ge=0)
    min_stock_threshold: int | None = Field(default=None, ge=0)
    category_id: UUID | None = None
    is_active: bool | None = None
    stock_qty: int | None = Field(default=None, ge=0)

    @field_validator("barcode")
    @classmethod
    def strip_barcode(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("brand")
    @classmethod
    def strip_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    barcode: str
    name: str
    brand: str | None
    image_url: str | None
    cost_price: Decimal
    current_selling_price: Decimal
    stock_qty: int
    min_stock_threshold: int
    category_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
