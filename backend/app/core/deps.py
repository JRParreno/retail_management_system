from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.branch import Branch
from app.models.enums import Role
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

MAIN_BRANCH_ID = UUID("11111111-1111-1111-1111-111111111111")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = UUID(str(subject))
    except (ValueError, TypeError) as exc:
        raise credentials_exception from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(*roles: Role | str) -> Callable[..., User]:
    allowed = {Role(role) if not isinstance(role, Role) else role for role in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


def get_active_branch_id(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_branch_id: str | None = Header(default=None, alias="X-Branch-Id"),
) -> UUID:
    """Cashiers are locked to their home branch. Admins may override via header."""
    if current_user.role == Role.ADMIN and x_branch_id:
        try:
            branch_id = UUID(x_branch_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Branch-Id",
            ) from exc
        branch = db.get(Branch, branch_id)
        if branch is None or not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found",
            )
        return branch_id
    return current_user.branch_id
