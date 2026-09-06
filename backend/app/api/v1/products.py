from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_active_branch_id, require_role
from app.db.session import get_db
from app.models.branch import Branch, BranchPrice, BranchStock, StockTransferLine
from app.models.enums import NotificationType, Role, StockAdjustmentType
from app.models.inventory import StockAdjustment
from app.models.motorcycle import MotorcycleModel
from app.models.notification import Notification
from app.models.product import Product, ProductBrand, ProductCategory
from app.models.return_void import ReturnVoidPartLine
from app.models.transaction import TransactionPartLine
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import StockAdjustmentRead, StockAdjustRequest
from app.schemas.product import (
    ProductBrandCreate,
    ProductBrandRead,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductDeletionImpact,
    ProductImportResponse,
    ProductMotorcycleModelRead,
    ProductRead,
    ProductUpdate,
)
from app.services.barcodes import generate_unique_barcode
from app.services.brands import ensure_product_brand, list_brand_names
from app.services.product_import import (
    build_export_xlsx,
    build_import_template,
    import_products_from_xlsx,
    models_to_export_slots,
)
from app.services.stock import get_or_create_branch_stock

router = APIRouter(tags=["products"])

ProductLifecycle = Literal["active", "disabled", "deleted", "all"]
ProductSortBy = Literal[
    "name", "brand", "category", "barcode", "price", "stock", "status"
]
ProductSortDir = Literal["asc", "desc"]


def _apply_lifecycle(stmt, lifecycle: ProductLifecycle):
    if lifecycle == "active":
        return stmt.where(Product.deleted_at.is_(None), Product.is_active.is_(True))
    if lifecycle == "disabled":
        return stmt.where(Product.deleted_at.is_(None), Product.is_active.is_(False))
    if lifecycle == "deleted":
        return stmt.where(Product.deleted_at.is_not(None))
    return stmt


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
    } if product_ids else {}
    prices = {
        pr.product_id: pr
        for pr in db.scalars(
            select(BranchPrice).where(
                BranchPrice.branch_id == branch_id,
                BranchPrice.product_id.in_(product_ids),
            )
        ).all()
    } if product_ids else {}
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
        read.applicable_motorcycle_models = [
            ProductMotorcycleModelRead(
                id=m.id,
                brand=m.brand,
                name=m.name,
                display_name=m.display_name,
            )
            for m in (getattr(product, "applicable_motorcycle_models", None) or [])
        ]
        results.append(read)
    return results


def _load_motorcycle_models(db: Session, model_ids: list[UUID]) -> list[MotorcycleModel]:
    if not model_ids:
        return []
    unique_ids = list(dict.fromkeys(model_ids))
    models = list(
        db.scalars(
            select(MotorcycleModel).where(
                MotorcycleModel.id.in_(unique_ids),
                MotorcycleModel.is_active.is_(True),
            )
        ).all()
    )
    if len(models) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more motorcycle models were not found or are inactive",
        )
    by_id = {m.id: m for m in models}
    return [by_id[mid] for mid in unique_ids]


def _set_applicable_motorcycle_models(
    db: Session, product: Product, model_ids: list[UUID]
) -> None:
    product.applicable_motorcycle_models = _load_motorcycle_models(db, model_ids)


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
    """Return catalog brand names for filters and product forms."""
    return list_brand_names(db)


@router.post(
    "/products/brands",
    response_model=ProductBrandRead,
    status_code=status.HTTP_201_CREATED,
)
def create_brand(
    body: ProductBrandCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> ProductBrand:
    existing = db.scalar(
        select(ProductBrand).where(
            func.lower(ProductBrand.name) == body.name.casefold()
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brand name already exists",
        )
    brand = ProductBrand(name=body.name)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


@router.post("/products/barcode/generate")
def generate_product_barcode(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> dict[str, str]:
    """Issue a unique internal barcode for parts without a manufacturer code.

    Path is intentionally nested under /barcode/ so it cannot be captured by
    GET /products/{product_id}.
    """
    try:
        return {"barcode": generate_unique_barcode(db)}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/products/import/template")
def download_product_import_template(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> Response:
    """Download .xlsx template for bulk product create (physical barcodes)."""
    motorcycle_names = [
        m.display_name
        for m in db.scalars(
            select(MotorcycleModel)
            .where(MotorcycleModel.is_active.is_(True))
            .order_by(MotorcycleModel.brand, MotorcycleModel.name)
        ).all()
    ]
    category_names = [
        c.name
        for c in db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
    ]
    content = build_import_template(
        list_brand_names(db),
        category_names,
        motorcycle_names,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="inventory-import-template.xlsx"',
        },
    )


@router.post("/products/import", response_model=ProductImportResponse)
async def import_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ProductImportResponse:
    """Create products from Excel. Duplicate barcodes are skipped; other rows still import."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported — download the template first",
        )
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    try:
        return import_products_from_xlsx(db, data, active_branch_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _product_filter_stmts(
    *,
    q: str | None,
    category_id: UUID | None,
    brand: str | None,
    lifecycle: ProductLifecycle,
):
    stmt = _apply_lifecycle(select(Product), lifecycle)
    count_stmt = _apply_lifecycle(select(func.count()).select_from(Product), lifecycle)
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
    return stmt, count_stmt


@router.get("/products/export")
def export_products(
    q: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    brand: str | None = Query(default=None),
    lifecycle: ProductLifecycle = Query(default="active"),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> Response:
    """Download inventory as .xlsx using the same columns as the import template."""
    stmt, _ = _product_filter_stmts(
        q=q, category_id=category_id, brand=brand, lifecycle=lifecycle
    )
    products = list(
        db.scalars(
            stmt.options(selectinload(Product.applicable_motorcycle_models)).order_by(
                Product.name
            )
        ).all()
    )
    overlaid = _overlay_products(db, products, active_branch_id)
    category_ids = {p.category_id for p in products if p.category_id is not None}
    categories = {
        c.id: c.name
        for c in db.scalars(
            select(ProductCategory).where(ProductCategory.id.in_(category_ids))
        ).all()
    } if category_ids else {}

    motorcycle_names = [
        m.display_name
        for m in db.scalars(
            select(MotorcycleModel)
            .where(MotorcycleModel.is_active.is_(True))
            .order_by(MotorcycleModel.brand, MotorcycleModel.name)
        ).all()
    ]
    category_names = [
        c.name
        for c in db.scalars(select(ProductCategory).order_by(ProductCategory.name)).all()
    ]

    rows: list[list[object]] = []
    for product, read in zip(products, overlaid, strict=True):
        model_slots = models_to_export_slots(
            [m.display_name for m in read.applicable_motorcycle_models]
        )
        rows.append(
            [
                read.barcode,
                read.name,
                read.brand or "",
                categories.get(product.category_id, "") if product.category_id else "",
                f"{read.cost_price:.2f}",
                f"{read.current_selling_price:.2f}",
                read.stock_qty,
                read.min_stock_threshold,
                *model_slots,
            ]
        )

    content = build_export_xlsx(
        rows,
        list_brand_names(db),
        category_names,
        motorcycle_names,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="inventory-export.xlsx"',
        },
    )


@router.get("/products", response_model=PaginatedResponse[ProductRead])
def list_products(
    q: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    brand: str | None = Query(default=None),
    lifecycle: ProductLifecycle = Query(default="active"),
    sort_by: ProductSortBy = Query(default="name"),
    sort_dir: ProductSortDir = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> PaginatedResponse[ProductRead]:
    stmt, count_stmt = _product_filter_stmts(
        q=q, category_id=category_id, brand=brand, lifecycle=lifecycle
    )

    if sort_by == "category":
        stmt = stmt.outerjoin(
            ProductCategory, Product.category_id == ProductCategory.id
        )
        order_col = ProductCategory.name
    elif sort_by == "stock":
        stmt = stmt.outerjoin(
            BranchStock,
            and_(
                BranchStock.product_id == Product.id,
                BranchStock.branch_id == active_branch_id,
            ),
        )
        order_col = func.coalesce(BranchStock.stock_qty, Product.stock_qty)
    elif sort_by == "price":
        stmt = stmt.outerjoin(
            BranchPrice,
            and_(
                BranchPrice.product_id == Product.id,
                BranchPrice.branch_id == active_branch_id,
            ),
        )
        order_col = func.coalesce(
            BranchPrice.selling_price, Product.current_selling_price
        )
    elif sort_by == "brand":
        order_col = Product.brand
    elif sort_by == "barcode":
        order_col = Product.barcode
    elif sort_by == "status":
        order_col = case(
            (Product.deleted_at.is_not(None), 2),
            (Product.is_active.is_(False), 1),
            else_=0,
        )
    else:
        order_col = Product.name

    if sort_dir == "desc":
        primary = order_col.desc().nulls_last()
    else:
        primary = order_col.asc().nulls_last()

    total = db.scalar(count_stmt) or 0
    products = list(
        db.scalars(
            stmt.options(selectinload(Product.applicable_motorcycle_models))
            .order_by(primary, Product.name.asc())
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

    payload = body.model_dump(exclude={"applicable_motorcycle_model_ids"})
    product = Product(**payload)
    db.add(product)
    db.flush()
    ensure_product_brand(db, body.brand)
    _set_applicable_motorcycle_models(db, product, body.applicable_motorcycle_model_ids)

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
    return _overlay_products(db, [product], active_branch_id)[0]

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
    if product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Restore this product before editing or enabling it",
        )
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
    model_ids = data.pop("applicable_motorcycle_model_ids", None)
    selling_price = data.get("current_selling_price")
    for key, value in data.items():
        setattr(product, key, value)
    if "brand" in data:
        ensure_product_brand(db, data.get("brand"))
    if model_ids is not None:
        _set_applicable_motorcycle_models(db, product, model_ids)
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


def _deletion_impact(db: Session, product: Product) -> ProductDeletionImpact:
    branch_stock = db.scalar(
        select(func.coalesce(func.sum(BranchStock.stock_qty), 0)).where(
            BranchStock.product_id == product.id
        )
    ) or 0
    transaction_lines = db.scalar(
        select(func.count()).select_from(TransactionPartLine).where(
            TransactionPartLine.product_id == product.id
        )
    ) or 0
    stock_adjustments = db.scalar(
        select(func.count()).select_from(StockAdjustment).where(
            StockAdjustment.product_id == product.id
        )
    ) or 0
    transfer_lines = db.scalar(
        select(func.count()).select_from(StockTransferLine).where(
            StockTransferLine.product_id == product.id
        )
    ) or 0
    return_lines = db.scalar(
        select(func.count()).select_from(ReturnVoidPartLine).where(
            ReturnVoidPartLine.product_id == product.id
        )
    ) or 0
    can_hard_delete = (
        product.deleted_at is not None
        and product.stock_qty == 0
        and branch_stock == 0
        and transaction_lines == 0
        and stock_adjustments == 0
        and transfer_lines == 0
        and return_lines == 0
    )
    return ProductDeletionImpact(
        product_id=product.id,
        can_hard_delete=can_hard_delete,
        catalog_stock=product.stock_qty,
        branch_stock=branch_stock,
        transaction_lines=transaction_lines,
        stock_adjustments=stock_adjustments,
        transfer_lines=transfer_lines,
        return_lines=return_lines,
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is already soft-deleted",
        )
    product.is_active = False
    product.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/products/{product_id}/restore", response_model=ProductRead)
def restore_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
    active_branch_id: UUID = Depends(get_active_branch_id),
) -> ProductRead:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is not soft-deleted",
        )
    product.deleted_at = None
    product.is_active = False
    db.commit()
    db.refresh(product)
    return _overlay_products(db, [product], active_branch_id)[0]


@router.get(
    "/products/{product_id}/deletion-impact",
    response_model=ProductDeletionImpact,
)
def get_product_deletion_impact(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> ProductDeletionImpact:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _deletion_impact(db, product)


@router.delete("/products/{product_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    impact = _deletion_impact(db, product)
    if not impact.can_hard_delete:
        blockers = []
        if product.deleted_at is None:
            blockers.append("soft-delete the product first")
        if impact.catalog_stock or impact.branch_stock:
            blockers.append("stock must be zero in every branch")
        if impact.transaction_lines:
            blockers.append(f"{impact.transaction_lines} transaction line(s)")
        if impact.stock_adjustments:
            blockers.append(f"{impact.stock_adjustments} stock adjustment(s)")
        if impact.transfer_lines:
            blockers.append(f"{impact.transfer_lines} transfer line(s)")
        if impact.return_lines:
            blockers.append(f"{impact.return_lines} return/void line(s)")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot permanently delete: " + ", ".join(blockers),
        )
    try:
        db.execute(delete(Product).where(Product.id == product_id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product gained history while deletion was in progress; try again",
        ) from exc


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
