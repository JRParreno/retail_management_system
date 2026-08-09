from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.shop_settings import ShopSettingsRead, ShopSettingsUpdate
from app.services.shop_settings import get_or_create_shop_settings

router = APIRouter(prefix="/shop-settings", tags=["shop-settings"])


@router.get("", response_model=ShopSettingsRead)
def read_shop_settings(db: Session = Depends(get_db)) -> ShopSettingsRead:
    """Public branding for login + in-app chrome (name + primary color only)."""
    return ShopSettingsRead.model_validate(get_or_create_shop_settings(db))


@router.put("", response_model=ShopSettingsRead)
def update_shop_settings(
    body: ShopSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> ShopSettingsRead:
    row = get_or_create_shop_settings(db)
    row.business_name = body.business_name
    row.primary_color = body.primary_color
    row.cashier_shift_start = body.cashier_shift_start
    row.cashier_shift_end = body.cashier_shift_end
    row.waive_first_mechanic_commission = body.waive_first_mechanic_commission
    db.add(row)
    db.commit()
    db.refresh(row)
    return ShopSettingsRead.model_validate(row)
