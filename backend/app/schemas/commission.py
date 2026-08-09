from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MechanicCommissionComputation(BaseModel):
    mechanic_id: UUID
    nickname: str
    labor_sales: Decimal
    commission_gross: Decimal
    commission_waived: Decimal
    commission_net: Decimal
    line_count: int
    is_first_mechanic: bool = False
    commission_waived_for_policy: bool = False


class CommissionComputationReport(BaseModel):
    day: date
    policy_enabled: bool
    applied: bool
    first_mechanic_id: UUID | None = None
    first_mechanic_nickname: str | None = None
    mechanics: list[MechanicCommissionComputation] = Field(default_factory=list)
    labor_sales_total: Decimal
    commission_gross_total: Decimal
    commission_waived_total: Decimal
    commission_net_total: Decimal


class CommissionSettleBody(BaseModel):
    """Apply first-mechanic waiver for the local shop day (before/at shift close)."""

    first_mechanic_id: UUID | None = None
    day: date | None = None


class DailyZeroCommissionMechanic(BaseModel):
    """The mechanic selected for today's zero-commission shop policy."""

    mechanic_id: UUID
