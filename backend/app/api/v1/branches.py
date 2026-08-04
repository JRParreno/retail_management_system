from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.branch import Branch, BranchPrice
from app.models.enums import Role
from app.models.product import Product
from app.models.user import User
from app.schemas.branch import (
    BranchCreate,
    BranchPriceRead,
    BranchPriceUpsert,
    BranchRead,
    BranchUpdate,
)

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("", response_model=list[BranchRead])
def list_branches(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[Branch]:
    stmt = select(Branch).order_by(Branch.name)
    if not (include_inactive and current_user.role == Role.ADMIN):
        stmt = stmt.where(Branch.is_active.is_(True))
    return list(db.scalars(stmt).all())


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
def create_branch(
    body: BranchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> Branch:
    existing = db.scalar(select(Branch).where(Branch.code == body.code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Branch code already exists",
        )
    branch = Branch(**body.model_dump())
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: UUID,
    body: BranchUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(branch, key, value)
    db.commit()
    db.refresh(branch)
    return branch


@router.get("/{branch_id}/prices", response_model=list[BranchPriceRead])
def list_branch_prices(
    branch_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[BranchPrice]:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return list(
        db.scalars(select(BranchPrice).where(BranchPrice.branch_id == branch_id)).all()
    )


@router.put("/{branch_id}/prices/{product_id}", response_model=BranchPriceRead)
def upsert_branch_price(
    branch_id: UUID,
    product_id: UUID,
    body: BranchPriceUpsert,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> BranchPrice:
    if product_id != body.product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_id in path must match body",
        )
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    price = db.scalar(
        select(BranchPrice).where(
            BranchPrice.branch_id == branch_id,
            BranchPrice.product_id == product_id,
        )
    )
    if price is None:
        price = BranchPrice(
            branch_id=branch_id,
            product_id=product_id,
            selling_price=body.selling_price,
        )
        db.add(price)
    else:
        price.selling_price = body.selling_price
    db.commit()
    db.refresh(price)
    return price
