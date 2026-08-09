from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.branch import Branch, StockTransfer, StockTransferLine
from app.models.enums import DocumentPrefix, NotificationType, Role, StockAdjustmentType
from app.models.inventory import StockAdjustment
from app.models.notification import Notification
from app.models.product import Product
from app.models.user import User
from app.schemas.branch import StockTransferCreate, StockTransferRead
from app.services.document_numbers import mint_document_number
from app.services.stock import get_or_create_branch_stock

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _load_transfer(db: Session, transfer_id: UUID) -> StockTransfer | None:
    return db.scalar(
        select(StockTransfer)
        .where(StockTransfer.id == transfer_id)
        .options(selectinload(StockTransfer.lines))
    )


@router.get("", response_model=list[StockTransferRead])
def list_transfers(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> list[StockTransfer]:
    stmt = (
        select(StockTransfer)
        .where(
            or_(
                StockTransfer.from_branch_id == active_branch_id,
                StockTransfer.to_branch_id == active_branch_id,
            )
        )
        .options(selectinload(StockTransfer.lines))
        .order_by(StockTransfer.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=StockTransferRead, status_code=status.HTTP_201_CREATED)
def create_transfer(
    body: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> StockTransfer:
    from_branch = db.get(Branch, body.from_branch_id)
    to_branch = db.get(Branch, body.to_branch_id)
    if from_branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="from_branch_id not found"
        )
    if to_branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="to_branch_id not found"
        )

    document_number = mint_document_number(db, DocumentPrefix.TR, body.from_branch_id)
    transfer = StockTransfer(
        document_number=document_number,
        from_branch_id=body.from_branch_id,
        to_branch_id=body.to_branch_id,
        notes=body.notes,
        created_by_id=current_user.id,
    )
    db.add(transfer)
    db.flush()

    for line_in in body.lines:
        product = db.get(Product, line_in.product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {line_in.product_id} not found",
            )
        if not product.is_active or product.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{product.name} is disabled and cannot be transferred",
            )

        from_stock = get_or_create_branch_stock(
            db, branch_id=body.from_branch_id, product=product
        )
        if from_stock.stock_qty < line_in.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for {product.name} at {from_branch.code}",
            )
        qty_before_from = from_stock.stock_qty
        from_stock.stock_qty = qty_before_from - line_in.quantity
        db.add(
            StockAdjustment(
                product_id=product.id,
                branch_id=body.from_branch_id,
                adjustment_type=StockAdjustmentType.TRANSFER_OUT,
                quantity_delta=-line_in.quantity,
                qty_before=qty_before_from,
                qty_after=from_stock.stock_qty,
                reason=f"Transfer {document_number} to {to_branch.code}",
                adjusted_by_id=current_user.id,
            )
        )
        if from_stock.stock_qty <= from_stock.min_stock_threshold:
            db.add(
                Notification(
                    type=NotificationType.LOW_STOCK,
                    title=f"Low stock: {product.name}",
                    message=(
                        f"{product.name} is at {from_stock.stock_qty} at {from_branch.code} "
                        f"(threshold {from_stock.min_stock_threshold})."
                    ),
                    product_id=product.id,
                )
            )

        to_stock = get_or_create_branch_stock(db, branch_id=body.to_branch_id, product=product)
        qty_before_to = to_stock.stock_qty
        to_stock.stock_qty = qty_before_to + line_in.quantity
        db.add(
            StockAdjustment(
                product_id=product.id,
                branch_id=body.to_branch_id,
                adjustment_type=StockAdjustmentType.TRANSFER_IN,
                quantity_delta=line_in.quantity,
                qty_before=qty_before_to,
                qty_after=to_stock.stock_qty,
                reason=f"Transfer {document_number} from {from_branch.code}",
                adjusted_by_id=current_user.id,
            )
        )

        db.add(
            StockTransferLine(
                transfer_id=transfer.id,
                product_id=product.id,
                quantity=line_in.quantity,
            )
        )

    db.commit()
    transfer = _load_transfer(db, transfer.id)
    assert transfer is not None
    return transfer
