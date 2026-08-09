from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MotorcycleModelCreate(BaseModel):
    brand: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True


class MotorcycleModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand: str
    name: str
    display_name: str
    is_active: bool
    created_at: datetime
