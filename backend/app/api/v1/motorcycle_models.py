from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.enums import Role
from app.models.motorcycle import MotorcycleModel
from app.models.user import User
from app.schemas.motorcycle import MotorcycleModelCreate, MotorcycleModelRead

router = APIRouter(prefix="/motorcycle-models", tags=["motorcycle-models"])


def _to_read(row: MotorcycleModel) -> MotorcycleModelRead:
    return MotorcycleModelRead(
        id=row.id,
        brand=row.brand,
        name=row.name,
        display_name=row.display_name,
        is_active=row.is_active,
        created_at=row.created_at,
    )


@router.get("", response_model=list[MotorcycleModelRead])
def list_motorcycle_models(
    q: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN, Role.CASHIER)),
) -> list[MotorcycleModelRead]:
    stmt = select(MotorcycleModel)
    if active_only:
        stmt = stmt.where(MotorcycleModel.is_active.is_(True))
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                MotorcycleModel.brand.ilike(pattern),
                MotorcycleModel.name.ilike(pattern),
            )
        )
    rows = list(
        db.scalars(
            stmt.order_by(MotorcycleModel.brand.asc(), MotorcycleModel.name.asc())
        ).all()
    )
    return [_to_read(row) for row in rows]


@router.post(
    "",
    response_model=MotorcycleModelRead,
    status_code=status.HTTP_201_CREATED,
)
def create_motorcycle_model(
    body: MotorcycleModelCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> MotorcycleModelRead:
    brand = body.brand.strip()
    name = body.name.strip()
    existing = db.scalar(
        select(MotorcycleModel).where(
            MotorcycleModel.brand == brand,
            MotorcycleModel.name == name,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Motorcycle model already exists",
        )
    row = MotorcycleModel(brand=brand, name=name, is_active=body.is_active)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_read(row)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_motorcycle_model(
    model_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> None:
    row = db.get(MotorcycleModel, model_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    row.is_active = False
    db.commit()
