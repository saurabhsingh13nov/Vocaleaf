"""FastAPI dependencies for auth and internal role checks."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import ADMIN_ROLE_CODES, STAFF_ROLE_CODES
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth import get_user_by_id


def extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = extract_bearer_token(request) or request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return user


def _require_role(user: User, *, allowed_roles: set[str]) -> User:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource",
        )
    return user


async def get_staff_user(current_user: User = Depends(get_current_user)) -> User:
    return _require_role(
        current_user,
        allowed_roles=STAFF_ROLE_CODES,
    )


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    return _require_role(
        current_user,
        allowed_roles=ADMIN_ROLE_CODES,
    )
