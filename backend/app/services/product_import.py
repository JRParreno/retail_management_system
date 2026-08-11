"""Parse Excel inventory uploads and create products (create-only)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any
from uuid import UUID

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.branch import Branch, BranchStock
from app.models.product import Product, ProductCategory
from app.schemas.product import ProductImportResponse, ProductImportRowResult
from app.services.barcodes import generate_unique_barcode
from app.services.brands import ensure_product_brand

TEMPLATE_HEADERS = [
    "barcode",
    "name",
    "brand",
    "category",
    "cost_price",
    "current_selling_price",
    "stock_qty",
    "min_stock_threshold",
]

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 2000

EXAMPLE_ROW = [
    "4800012345678",
    "Sample Brake Pad",
    "OEM",
    "Brakes",
    "150.00",
    "250.00",
    "10",
    "2",
]

# Second example: blank barcode → system generates RMS… and matches duplicates by name+brand
EXAMPLE_ROW_NO_BARCODE = [
    "",
    "Custom Labor Hose",
    "OEM",
    "Parts",
    "50.00",
    "120.00",
    "5",
    "1",
]


def build_import_template(brand_names: list[str] | None = None) -> bytes:
    brands = [b for b in (brand_names or []) if b and b.strip()]
    if "OEM" not in brands:
        # Keep example row valid even if catalog is empty.
        brands = ["OEM", *brands]

    wb = Workbook()
    ws = wb.active
    ws.title = "Products"
    ws.append(TEMPLATE_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.append(EXAMPLE_ROW)
    ws.append(EXAMPLE_ROW_NO_BARCODE)
    # Keep barcodes as text so Excel does not strip zeros / use scientific notation.
    for row in ws.iter_rows(min_row=2, max_col=1):
        for cell in row:
            cell.number_format = "@"

    brands_ws = wb.create_sheet("Brands")
    brands_ws.append(["brand"])
    brands_ws["A1"].font = Font(bold=True)
    for name in brands:
        brands_ws.append([name])
    brands_ws.column_dimensions["A"].width = 20

    # Brand dropdown on Products!C (allow blank for unbranded items).
    last_brand_row = max(2, len(brands) + 1)
    dv = DataValidation(
        type="list",
        formula1=f"Brands!$A$2:$A${last_brand_row}",
        allow_blank=True,
        showDropDown=False,
    )
    dv.error = "Select a brand from the dropdown list (or leave blank)"
    dv.errorTitle = "Brand"
    dv.prompt = "Choose a seeded brand"
    dv.promptTitle = "Brand"
    ws.add_data_validation(dv)
    dv.add(f"C2:C{MAX_IMPORT_ROWS + 1}")

    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 20
    ws.column_dimensions["G"].width = 12
    ws.column_dimensions["H"].width = 18
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).strip()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        # Avoid scientific notation for long numeric barcodes stored as float.
        text = f"{value:.0f}" if abs(value) >= 1e11 else str(value).rstrip("0").rstrip(".")
        return text.strip()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        return format(value, "f").rstrip("0").rstrip(".")
    return str(value).strip()


def _parse_decimal(raw: str, field: str) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if value < 0:
        raise ValueError(f"{field} must be >= 0")
    return value


def _parse_nonneg_int(raw: str, field: str, default: int = 0) -> int:
    if not raw:
        return default
    try:
        if "." in raw:
            as_dec = Decimal(raw)
            if as_dec != as_dec.to_integral_value():
                raise ValueError
            value = int(as_dec)
        else:
            value = int(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a whole number >= 0") from exc
    if value < 0:
        raise ValueError(f"{field} must be >= 0")
    return value


def _header_map(ws: Worksheet) -> dict[str, int]:
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        raise ValueError("Spreadsheet is empty")
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        key = _cell_str(cell).lower()
        if key:
            mapping[key] = idx
    missing = [h for h in ("barcode", "name", "category", "cost_price", "current_selling_price") if h not in mapping]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")
    return mapping


def _get_or_create_category(
    db: Session,
    name: str,
    cache: dict[str, ProductCategory],
) -> ProductCategory:
    key = name.casefold()
    cached = cache.get(key)
    if cached is not None:
        return cached
    existing = db.scalar(
        select(ProductCategory).where(func.lower(ProductCategory.name) == key)
    )
    if existing is not None:
        cache[key] = existing
        return existing
    category = ProductCategory(name=name[:100])
    db.add(category)
    db.flush()
    cache[key] = category
    return category


def _create_product_row(
    db: Session,
    *,
    active_branch_id: UUID,
    other_branch_ids: list[UUID],
    barcode: str,
    name: str,
    brand: str | None,
    category_id: UUID,
    cost_price: Decimal,
    selling_price: Decimal,
    stock_qty: int,
    min_stock: int,
) -> None:
    product = Product(
        barcode=barcode,
        name=name,
        brand=brand,
        cost_price=cost_price,
        current_selling_price=selling_price,
        stock_qty=stock_qty,
        min_stock_threshold=min_stock,
        category_id=category_id,
        is_active=True,
    )
    db.add(product)
    db.flush()
    db.add(
        BranchStock(
            branch_id=active_branch_id,
            product_id=product.id,
            stock_qty=stock_qty,
            min_stock_threshold=min_stock,
        )
    )
    for branch_id in other_branch_ids:
        db.add(
            BranchStock(
                branch_id=branch_id,
                product_id=product.id,
                stock_qty=0,
                min_stock_threshold=min_stock,
            )
        )


def import_products_from_xlsx(
    db: Session,
    data: bytes,
    active_branch_id: UUID,
) -> ProductImportResponse:
    if len(data) > MAX_IMPORT_BYTES:
        raise ValueError("File too large (max 5 MB)")

    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 — openpyxl raises varied errors
        raise ValueError("Invalid Excel file — use the downloadable .xlsx template") from exc

    ws = wb.active
    header_map = _header_map(ws)

    other_branch_ids = list(
        db.scalars(
            select(Branch.id).where(
                Branch.is_active.is_(True),
                Branch.id != active_branch_id,
            )
        ).all()
    )
    category_cache: dict[str, ProductCategory] = {}
    seen_barcodes: set[str] = set()
    seen_name_brand: set[tuple[str, str]] = set()
    results: list[ProductImportRowResult] = []
    created = skipped = errors = 0
    data_rows = 0

    for excel_row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row is None or all(cell is None or _cell_str(cell) == "" for cell in row):
            continue
        data_rows += 1
        if data_rows > MAX_IMPORT_ROWS:
            results.append(
                ProductImportRowResult(
                    row=excel_row_num,
                    status="error",
                    message=f"Row limit exceeded (max {MAX_IMPORT_ROWS})",
                )
            )
            errors += 1
            break

        def col(key: str) -> str:
            idx = header_map.get(key)
            if idx is None or idx >= len(row):
                return ""
            return _cell_str(row[idx])

        barcode = col("barcode")
        name = col("name")
        brand_raw = col("brand")
        category_name = col("category")
        cost_raw = col("cost_price")
        sell_raw = col("current_selling_price")
        stock_raw = col("stock_qty")
        min_raw = col("min_stock_threshold")
        auto_barcode = False

        try:
            if not name:
                raise ValueError("name is required")
            if len(name) > 200:
                raise ValueError("name must be at most 200 characters")
            if not category_name:
                raise ValueError("category is required")
            if len(category_name) > 100:
                raise ValueError("category must be at most 100 characters")
            if not cost_raw:
                raise ValueError("cost_price is required")
            if not sell_raw:
                raise ValueError("current_selling_price is required")

            cost_price = _parse_decimal(cost_raw, "cost_price")
            selling_price = _parse_decimal(sell_raw, "current_selling_price")
            stock_qty = _parse_nonneg_int(stock_raw, "stock_qty", default=0)
            min_stock = _parse_nonneg_int(min_raw, "min_stock_threshold", default=0)
            brand = brand_raw[:100] if brand_raw else None
            if brand:
                ensure_product_brand(db, brand)

            name_key = name.casefold()
            brand_key = (brand or "").casefold()
            identity = (name_key, brand_key)

            if barcode:
                if len(barcode) > 64:
                    raise ValueError("barcode must be at most 64 characters")
                if barcode in seen_barcodes:
                    raise ValueError("duplicate barcode in this file")
                existing = db.scalar(select(Product.id).where(Product.barcode == barcode))
                if existing is not None:
                    skipped += 1
                    results.append(
                        ProductImportRowResult(
                            row=excel_row_num,
                            barcode=barcode,
                            name=name,
                            status="skipped",
                            message="Barcode already exists",
                        )
                    )
                    continue
            else:
                # No package barcode — match by name + brand before creating.
                if identity in seen_name_brand:
                    skipped += 1
                    results.append(
                        ProductImportRowResult(
                            row=excel_row_num,
                            barcode=None,
                            name=name,
                            status="skipped",
                            message="Duplicate name+brand in this file (no barcode)",
                        )
                    )
                    continue
                name_stmt = select(Product).where(
                    func.lower(Product.name) == name_key,
                    Product.deleted_at.is_(None),
                )
                if brand:
                    name_stmt = name_stmt.where(func.lower(Product.brand) == brand_key)
                else:
                    name_stmt = name_stmt.where(
                        or_(Product.brand.is_(None), Product.brand == "")
                    )
                existing_by_name = db.scalar(name_stmt.limit(1))
                if existing_by_name is not None:
                    skipped += 1
                    results.append(
                        ProductImportRowResult(
                            row=excel_row_num,
                            barcode=existing_by_name.barcode,
                            name=name,
                            status="skipped",
                            message=(
                                "Possible duplicate — same name/brand already exists "
                                f"(barcode {existing_by_name.barcode})"
                            ),
                        )
                    )
                    continue
                barcode = generate_unique_barcode(db, reserved=seen_barcodes)
                auto_barcode = True

            seen_barcodes.add(barcode)
            seen_name_brand.add(identity)

            category = _get_or_create_category(db, category_name, category_cache)
            _create_product_row(
                db,
                active_branch_id=active_branch_id,
                other_branch_ids=other_branch_ids,
                barcode=barcode,
                name=name,
                brand=brand,
                category_id=category.id,
                cost_price=cost_price,
                selling_price=selling_price,
                stock_qty=stock_qty,
                min_stock=min_stock,
            )
            created += 1
            results.append(
                ProductImportRowResult(
                    row=excel_row_num,
                    barcode=barcode,
                    name=name,
                    status="created",
                    message=(
                        "Created (auto barcode)" if auto_barcode else "Created"
                    ),
                )
            )
        except ValueError as exc:
            errors += 1
            results.append(
                ProductImportRowResult(
                    row=excel_row_num,
                    barcode=barcode or None,
                    name=name or None,
                    status="error",
                    message=str(exc),
                )
            )

    wb.close()

    if data_rows == 0:
        raise ValueError("No data rows found — add products below the header row")

    db.commit()
    return ProductImportResponse(
        created=created,
        skipped=skipped,
        errors=errors,
        rows=results,
    )
