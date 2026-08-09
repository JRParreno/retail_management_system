import re
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
TIME_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DEFAULT_BUSINESS_NAME = "MotoShop RMS"
DEFAULT_PRIMARY_COLOR = "#C26A1A"
DEFAULT_CASHIER_SHIFT_START = "08:00"
DEFAULT_CASHIER_SHIFT_END = "17:00"


class ShopSettings(Base):
    """Singleton shop branding settings (always row id=1)."""

    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_name: Mapped[str] = mapped_column(String(120), nullable=False)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False)
    cashier_shift_start: Mapped[str] = mapped_column(
        String(5), nullable=False, default=DEFAULT_CASHIER_SHIFT_START
    )
    cashier_shift_end: Mapped[str] = mapped_column(
        String(5), nullable=False, default=DEFAULT_CASHIER_SHIFT_END
    )
    waive_first_mechanic_commission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
