from pydantic import BaseModel, Field, field_validator

from app.models.shop_settings import (
    DEFAULT_BUSINESS_NAME,
    DEFAULT_CASHIER_SHIFT_END,
    DEFAULT_CASHIER_SHIFT_START,
    DEFAULT_PRIMARY_COLOR,
    HEX_COLOR_RE,
    TIME_HHMM_RE,
)


class ShopSettingsRead(BaseModel):
    business_name: str
    primary_color: str
    cashier_shift_start: str
    cashier_shift_end: str
    waive_first_mechanic_commission: bool

    model_config = {"from_attributes": True}


class ShopSettingsUpdate(BaseModel):
    business_name: str = Field(min_length=1, max_length=120)
    primary_color: str = Field(min_length=7, max_length=7)
    cashier_shift_start: str = Field(
        default=DEFAULT_CASHIER_SHIFT_START, min_length=5, max_length=5
    )
    cashier_shift_end: str = Field(
        default=DEFAULT_CASHIER_SHIFT_END, min_length=5, max_length=5
    )
    waive_first_mechanic_commission: bool = False

    @field_validator("business_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("business_name is required")
        return cleaned

    @field_validator("primary_color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        cleaned = value.strip()
        if not HEX_COLOR_RE.match(cleaned):
            raise ValueError("primary_color must be a hex color like #C26A1A")
        return cleaned.upper()

    @field_validator("cashier_shift_start", "cashier_shift_end")
    @classmethod
    def normalize_time(cls, value: str) -> str:
        cleaned = value.strip()
        if not TIME_HHMM_RE.match(cleaned):
            raise ValueError("time must look like HH:MM (24-hour), e.g. 08:00")
        return cleaned


__all__ = [
    "ShopSettingsRead",
    "ShopSettingsUpdate",
    "DEFAULT_BUSINESS_NAME",
    "DEFAULT_PRIMARY_COLOR",
    "DEFAULT_CASHIER_SHIFT_START",
    "DEFAULT_CASHIER_SHIFT_END",
]
