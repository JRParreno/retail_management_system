from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MechanicCommissionRow(BaseModel):
    mechanic_id: UUID
    nickname: str
    labor_sales: Decimal
    commission_total: Decimal


class ReportSummary(BaseModel):
    gross_revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    parts_sales: Decimal
    labor_sales: Decimal
    avg_ticket: Decimal
    commission_total: Decimal
    low_stock_count: int
    parts_profit: Decimal
    labor_profit_before_commission: Decimal
    net_profit: Decimal
    transaction_count: int
    mechanic_commissions: list[MechanicCommissionRow] = Field(default_factory=list)
