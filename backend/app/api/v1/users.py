from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.branch import Branch
from app.models.enums import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.ADMIN)),
) -> User:
    existing = db.scalar(select(User).where(User.username == body.username))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    if db.get(Branch, body.branch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    user = User(
        username=body.username.strip(),
        hashed_password=get_password_hash(body.password),
        full_name=body.full_name.strip(),
        role=body.role,
        branch_id=body.branch_id,
        is_active=body.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        password = data.pop("password")
        if password:
            user.hashed_password = get_password_hash(password)

    if "branch_id" in data and data["branch_id"] is not None:
        if db.get(Branch, data["branch_id"]) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found"
            )

    demoting = data.get("role") == Role.CASHIER and user.role == Role.ADMIN
    deactivating = data.get("is_active") is False and user.is_active

    if demoting or deactivating:
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote or deactivate your own admin account",
            )
        other_admins = list(
            db.scalars(
                select(User).where(
                    User.role == Role.ADMIN,
                    User.is_active.is_(True),
                    User.id != user.id,
                )
            ).all()
        )
        if not other_admins:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last active admin",
            )

    for key, value in data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user
