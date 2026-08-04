from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationType


class NotificationCreate(BaseModel):
    type: NotificationType
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)
    product_id: UUID | None = None
    user_id: UUID | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: NotificationType
    title: str
    message: str
    product_id: UUID | None
    user_id: UUID | None
    is_read: bool
    created_at: datetime


class NotificationUpdate(BaseModel):
    is_read: bool
