"""Internal / unique product barcode helpers."""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product


def generate_unique_barcode(
    db: Session,
    *,
    reserved: set[str] | None = None,
    attempts: int = 64,
) -> str:
    """Issue an RMS + 12-digit code unused in DB and not in `reserved`."""
    reserved = reserved or set()
    for _ in range(attempts):
        candidate = f"RMS{secrets.randbelow(10**12):012d}"
        if candidate in reserved:
            continue
        exists = db.scalar(select(Product.id).where(Product.barcode == candidate))
        if exists is None:
            return candidate
    raise ValueError("Could not generate a unique barcode — try again")
