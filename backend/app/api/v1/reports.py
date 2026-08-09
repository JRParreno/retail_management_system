from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.branch import BranchStock
from app.models.enums import Role, TransactionStatus
from app.models.mechanic import Mechanic
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.report import MechanicCommissionRow, ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])

ZERO = Decimal("0.00")


@router.get("/summary", response_model=ReportSummary)
def report_summary(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ReportSummary:
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

    transactions = list(
        db.scalars(
            select(Transaction)
            .where(
                Transaction.status == TransactionStatus.PAID,
                Transaction.branch_id == active_branch_id,
                Transaction.paid_at.is_not(None),
                Transaction.paid_at >= start_dt,
                Transaction.paid_at <= end_dt,
            )
            .options(
                selectinload(Transaction.part_lines),
                selectinload(Transaction.labor_lines),
            )
        ).all()
    )

    parts_sales = ZERO
    labor_sales = ZERO
    cogs = ZERO
    commission_total = ZERO
    commission_gross_total = ZERO
    commission_waived_total = ZERO
    ticket_count = len(transactions)
    mechanic_totals: dict[UUID, dict[str, Decimal | int | bool]] = {}

    # Historical integrity: use line snapshots only — never Product.current_*
    # or BranchPrice. Changing catalog/branch prices must not rewrite past tickets.
    for txn in transactions:
        for line in txn.part_lines:
            parts_sales += line.actual_selling_price * line.quantity
            cogs += line.cost_price_snapshot * line.quantity
        for line in txn.labor_lines:
            labor_sales += line.actual_price
            gross = (
                line.mechanic_payout_gross
                if line.mechanic_payout_gross is not None
                else (
                    ZERO
                    if line.commission_waived
                    else (line.mechanic_payout_amount or ZERO)
                )
            )
            if line.mechanic_payout_gross is None and line.mechanic_payout_amount is not None:
                if not line.commission_waived:
                    gross = line.mechanic_payout_amount
            net = ZERO if line.commission_waived else (line.mechanic_payout_amount or ZERO)
            waived = gross - net
            commission_gross_total += gross
            commission_waived_total += waived
            commission_total += net
            if line.mechanic_id is not None:
                bucket = mechanic_totals.setdefault(
                    line.mechanic_id,
                    {
                        "labor_sales": ZERO,
                        "commission_gross": ZERO,
                        "commission_waived": ZERO,
                        "commission_total": ZERO,
                        "line_count": 0,
                        "is_first_mechanic_waived": False,
                    },
                )
                bucket["labor_sales"] += line.actual_price
                bucket["commission_gross"] += gross
                bucket["commission_waived"] += waived
                bucket["commission_total"] += net
                bucket["line_count"] = int(bucket["line_count"]) + 1
                if line.commission_waived:
                    bucket["is_first_mechanic_waived"] = True

    gross_revenue = parts_sales + labor_sales
    parts_profit = parts_sales - cogs
    # Labor has no COGS in v1; commission is deducted separately below.
    labor_profit_before_commission = labor_sales
    gross_profit = parts_profit + labor_profit_before_commission
    net_profit = gross_profit - commission_total
    avg_ticket = (
        (gross_revenue / ticket_count).quantize(Decimal("0.01"))
        if ticket_count
        else ZERO
    )

    low_stock_count = (
        db.scalar(
            select(func.count())
            .select_from(BranchStock)
            .join(Product, Product.id == BranchStock.product_id)
            .where(
                BranchStock.branch_id == active_branch_id,
                Product.is_active.is_(True),
                BranchStock.stock_qty <= BranchStock.min_stock_threshold,
            )
        )
        or 0
    )

    mechanic_commissions: list[MechanicCommissionRow] = []
    if mechanic_totals:
        mechanics = {
            m.id: m
            for m in db.scalars(
                select(Mechanic).where(Mechanic.id.in_(mechanic_totals.keys()))
            ).all()
        }
        for mechanic_id, totals in mechanic_totals.items():
            mechanic = mechanics.get(mechanic_id)
            mechanic_commissions.append(
                MechanicCommissionRow(
                    mechanic_id=mechanic_id,
                    nickname=mechanic.nickname if mechanic else "Unknown",
                    labor_sales=totals["labor_sales"],  # type: ignore[arg-type]
                    commission_gross=totals["commission_gross"],  # type: ignore[arg-type]
                    commission_waived=totals["commission_waived"],  # type: ignore[arg-type]
                    commission_total=totals["commission_total"],  # type: ignore[arg-type]
                    line_count=int(totals["line_count"]),
                    is_first_mechanic_waived=bool(totals["is_first_mechanic_waived"]),
                )
            )
        mechanic_commissions.sort(key=lambda row: row.commission_total, reverse=True)

    return ReportSummary(
        gross_revenue=gross_revenue,
        cogs=cogs,
        gross_profit=gross_profit,
        parts_sales=parts_sales,
        labor_sales=labor_sales,
        avg_ticket=avg_ticket,
        commission_total=commission_total,
        commission_gross_total=commission_gross_total,
        commission_waived_total=commission_waived_total,
        low_stock_count=low_stock_count,
        parts_profit=parts_profit,
        labor_profit_before_commission=labor_profit_before_commission,
        net_profit=net_profit,
        transaction_count=ticket_count,
        mechanic_commissions=mechanic_commissions,
    )
