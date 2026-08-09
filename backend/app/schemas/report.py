from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MechanicCommissionRow(BaseModel):
    mechanic_id: UUID
    nickname: str
    labor_sales: Decimal
    commission_gross: Decimal
    commission_waived: Decimal
    commission_total: Decimal
    line_count: int = 0
    is_first_mechanic_waived: bool = False


class ProductSalesRow(BaseModel):
    product_id: UUID
    product_name: str
    barcode: str
    brand: str | None = None
    quantity_sold: int
    sales_total: Decimal
    cogs_total: Decimal
    profit: Decimal
    line_count: int = 0


class ReportSummary(BaseModel):
    gross_revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    parts_sales: Decimal
    labor_sales: Decimal
    avg_ticket: Decimal
    commission_total: Decimal
    commission_gross_total: Decimal
    commission_waived_total: Decimal
    low_stock_count: int
    parts_profit: Decimal
    labor_profit_before_commission: Decimal
    net_profit: Decimal
    transaction_count: int
    mechanic_commissions: list[MechanicCommissionRow] = Field(default_factory=list)
    product_sales: list[ProductSalesRow] = Field(default_factory=list)
