from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
import secrets

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.branch import Branch, BranchPrice, BranchStock
from app.models.enums import NotificationType, Role, StockAdjustmentType
from app.models.inventory import StockAdjustment
from app.models.notification import Notification
from app.models.product import Product, ProductCategory
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import StockAdjustmentRead, StockAdjustRequest
from app.schemas.product import (
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.services.stock import get_or_create_branch_stock

router = APIRouter(tags=["products"])


def _overlay_products(
    db: Session, products: list[Product], branch_id: UUID
) -> list[ProductRead]:
    """Overlay branch-specific stock and pricing onto product catalog rows."""
    product_ids = [p.id for p in products]
    stocks = {
        s.product_id: s
        for s in db.scalars(
            select(BranchStock).where(
                BranchStock.branch_id == branch_id,
                BranchStock.product_id.in_(product_ids),
            )
        ).all()
    }
    prices = {
        pr.product_id: pr
        for pr in db.scalars(
            select(BranchPrice).where(
                BranchPrice.branch_id == branch_id,
                BranchPrice.product_id.in_(product_ids),
            )
        ).all()
    }
    results: list[ProductRead] = []
    for product in products:
        read = ProductRead.model_validate(product)
        stock = stocks.get(product.id)
        if stock is not None:
            read.stock_qty = stock.stock_qty
            read.min_stock_threshold = stock.min_stock_threshold
        price = prices.get(product.id)
        read.current_selling_price = (
            price.selling_price if price is not None else product.current_selling_price
        )
        results.append(read)
    return results


# --- Categories ---


@router.get("/categories", response_model=list[ProductCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[ProductCategory]:
    return list(db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all())


@router.post(
    "/categories",
    response_model=ProductCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    body: ProductCategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> ProductCategory:
    existing = db.scalar(select(ProductCategory).where(ProductCategory.name == body.name))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category name already exists",
        )
    category = ProductCategory(name=body.name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=ProductCategoryRead)
def update_category(
    category_id: UUID,
    body: ProductCategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> ProductCategory:
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        clash = db.scalar(
            select(ProductCategory).where(
                ProductCategory.name == data["name"],
                ProductCategory.id != category_id,
            )
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category name already exists",
            )
        category.name = data["name"]
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> None:
    category = db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    db.commit()


# --- Products ---


@router.get("/products/brands", response_model=list[str])
def list_brands(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[str]:
    rows = db.scalars(
        select(Product.brand)
        .where(Product.brand.is_not(None), Product.brand != "")
        .distinct()
        .order_by(Product.brand)
    ).all()
    return [b for b in rows if b]


@router.post("/products/barcode/generate")
def generate_product_barcode(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, str]:
    """Issue a unique internal barcode for parts without a manufacturer code.

    Path is intentionally nested under /barcode/ so it cannot be captured by
    GET /products/{product_id}.
    """
    for _ in range(32):
        # RMS + 12 digits — unique, printable, gun/camera friendly
        candidate = f"RMS{secrets.randbelow(10**12):012d}"
        exists = db.scalar(select(Product.id).where(Product.barcode == candidate))
        if exists is None:
            return {"barcode": candidate}
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate a unique barcode — try again",
    )


@router.get("/products", response_model=PaginatedResponse[ProductRead])
def list_products(
    q: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    brand: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> PaginatedResponse[ProductRead]:
    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)
    if q:
        pattern = f"%{q.strip()}%"
        filt = or_(
            Product.name.ilike(pattern),
            Product.barcode.ilike(pattern),
            Product.brand.ilike(pattern),
        )
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
        count_stmt = count_stmt.where(Product.category_id == category_id)
    if brand and brand.strip():
        brand_filter = brand.strip()
        stmt = stmt.where(Product.brand.ilike(brand_filter))
        count_stmt = count_stmt.where(Product.brand.ilike(brand_filter))

    total = db.scalar(count_stmt) or 0
    products = list(
        db.scalars(
            stmt.order_by(Product.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    items = _overlay_products(db, products, active_branch_id)
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ProductRead:
    existing = db.scalar(select(Product).where(Product.barcode == body.barcode))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Barcode already exists",
        )
    if body.category_id is not None and db.get(ProductCategory, body.category_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    product = Product(**body.model_dump())
    db.add(product)
    db.flush()

    db.add(
        BranchStock(
            branch_id=active_branch_id,
            product_id=product.id,
            stock_qty=body.stock_qty,
            min_stock_threshold=body.min_stock_threshold,
        )
    )
    other_branch_ids = db.scalars(
        select(Branch.id).where(Branch.is_active.is_(True), Branch.id != active_branch_id)
    ).all()
    for branch_id in other_branch_ids:
        db.add(
            BranchStock(
                branch_id=branch_id,
                product_id=product.id,
                stock_qty=0,
                min_stock_threshold=body.min_stock_threshold,
            )
        )

    db.commit()
    db.refresh(product)
    read = ProductRead.model_validate(product)
    read.stock_qty = body.stock_qty
    read.min_stock_threshold = body.min_stock_threshold
    return read


@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ProductRead:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _overlay_products(db, [product], active_branch_id)[0]


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: UUID,
    body: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ProductRead:
    """Update catalog fields for future sales only.

    Paid tickets keep `cost_price_snapshot` / `actual_selling_price` on their
    line items, so changing cost or sell price here does not rewrite reports.
    Stock quantity is changed via `/adjust` (or opening stock on create).
    """
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    data = body.model_dump(exclude_unset=True)
    # Locked after create — accidental barcode/category changes cause messy
    # inventory history and support confusion. Name/brand/prices remain editable.
    if "barcode" in data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode cannot be changed after create",
        )
    if "category_id" in data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category cannot be changed after create — set it when adding the product",
        )
    # stock_qty on the active branch is managed via BranchStock / the /adjust
    # endpoint, not this catalog-level update.
    data.pop("stock_qty", None)
    selling_price = data.get("current_selling_price")
    for key, value in data.items():
        setattr(product, key, value)
    if "min_stock_threshold" in data:
        branch_stock = get_or_create_branch_stock(
            db, branch_id=active_branch_id, product=product
        )
        branch_stock.min_stock_threshold = data["min_stock_threshold"]
    # Keep this branch's sell price in sync if a BranchPrice override exists,
    # or create one so the active branch reflects the new catalog price.
    if selling_price is not None:
        override = db.scalar(
            select(BranchPrice).where(
                BranchPrice.branch_id == active_branch_id,
                BranchPrice.product_id == product.id,
            )
        )
        if override is None:
            db.add(
                BranchPrice(
                    branch_id=active_branch_id,
                    product_id=product.id,
                    selling_price=selling_price,
                )
            )
        else:
            override.selling_price = selling_price
    db.commit()
    db.refresh(product)
    return _overlay_products(db, [product], active_branch_id)[0]


@router.post(
    "/products/{product_id}/adjust",
    response_model=StockAdjustmentRead,
    status_code=status.HTTP_201_CREATED,
)
def adjust_stock(
    product_id: UUID,
    body: StockAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> StockAdjustment:
    if body.quantity_delta == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quantity_delta must be non-zero",
        )
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    stock = get_or_create_branch_stock(db, branch_id=active_branch_id, product=product)
    qty_before = stock.stock_qty
    qty_after = qty_before + body.quantity_delta
    if qty_after < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adjustment would result in negative stock",
        )

    adjustment_type = (
        StockAdjustmentType.IN if body.quantity_delta > 0 else StockAdjustmentType.OUT
    )
    stock.stock_qty = qty_after
    # Keep catalog mirror in sync for Main convenience / legacy reads
    product.stock_qty = max(0, product.stock_qty + body.quantity_delta)
    adjustment = StockAdjustment(
        product_id=product.id,
        branch_id=active_branch_id,
        adjustment_type=adjustment_type,
        quantity_delta=body.quantity_delta,
        qty_before=qty_before,
        qty_after=qty_after,
        reason=body.reason,
        adjusted_by_id=current_user.id,
    )
    db.add(adjustment)
    if qty_after <= stock.min_stock_threshold:
        db.add(
            Notification(
                type=NotificationType.LOW_STOCK,
                title=f"Low stock: {product.name}",
                message=(
                    f"{product.name} is at {qty_after} "
                    f"(threshold {stock.min_stock_threshold})."
                ),
                product_id=product.id,
            )
        )
    db.commit()
    db.refresh(adjustment)
    return adjustment
