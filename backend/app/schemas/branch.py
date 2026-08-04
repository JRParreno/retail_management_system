from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BranchCreate(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=120)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    address: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BranchPriceUpsert(BaseModel):
    product_id: UUID
    selling_price: Decimal = Field(ge=0)


class BranchPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    product_id: UUID
    selling_price: Decimal
    updated_at: datetime


class StockTransferLineInput(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1)


class StockTransferCreate(BaseModel):
    from_branch_id: UUID
    to_branch_id: UUID
    notes: str | None = None
    lines: list[StockTransferLineInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_branches_differ(self) -> "StockTransferCreate":
        if self.from_branch_id == self.to_branch_id:
            raise ValueError("from_branch_id and to_branch_id must differ")
        return self


class StockTransferLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transfer_id: UUID
    product_id: UUID
    quantity: int


class StockTransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_number: str
    from_branch_id: UUID
    to_branch_id: UUID
    notes: str | None
    created_by_id: UUID
    created_at: datetime
    lines: list[StockTransferLineRead] = Field(default_factory=list)
