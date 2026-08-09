from sqlalchemy.orm import Session

from app.models.shop_settings import (
    DEFAULT_BUSINESS_NAME,
    DEFAULT_CASHIER_SHIFT_END,
    DEFAULT_CASHIER_SHIFT_START,
    DEFAULT_PRIMARY_COLOR,
    ShopSettings,
)


def get_or_create_shop_settings(db: Session) -> ShopSettings:
    row = db.get(ShopSettings, 1)
    if row is not None:
        return row
    row = ShopSettings(
        id=1,
        business_name=DEFAULT_BUSINESS_NAME,
        primary_color=DEFAULT_PRIMARY_COLOR,
        cashier_shift_start=DEFAULT_CASHIER_SHIFT_START,
        cashier_shift_end=DEFAULT_CASHIER_SHIFT_END,
        waive_first_mechanic_commission=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
