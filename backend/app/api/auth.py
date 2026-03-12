"""Auth endpoints — register, login, logout, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthRequest,
    LinkGoogleRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.integrations.google_oauth import verify_google_token
from app.services.auth import (
    AuthError,
    authenticate_google_user,
    authenticate_user,
    get_user_by_id,
    link_google_identity,
    register_user,
)
from app.api.dependencies import get_current_user

import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: Response, user_id: str) -> None:
    secure = not settings.debug
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/api/auth/refresh",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await register_user(db, body.email, body.password, body.full_name)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    _set_auth_cookies(response, str(user.id))
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await authenticate_user(db, body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    _set_auth_cookies(response, str(user.id))
    return user


@router.post("/google", response_model=UserResponse)
async def google_auth(
    body: GoogleAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        google_info = verify_google_token(body.credential)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    try:
        user = await authenticate_google_user(
            db,
            sub=google_info.sub,
            email=google_info.email,
            full_name=google_info.name,
            avatar_url=google_info.picture,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    _set_auth_cookies(response, str(user.id))
    return user


@router.post("/link-google", response_model=UserResponse)
async def link_google(
    body: LinkGoogleRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        google_info = verify_google_token(body.credential)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    try:
        user = await link_google_identity(
            db,
            email=google_info.email,
            password=body.password,
            sub=google_info.sub,
            name=google_info.name,
            avatar_url=google_info.picture,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    _set_auth_cookies(response, str(user.id))
    return user


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out")


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Issue new access token only
    secure = not settings.debug
    access_token = create_access_token(str(user.id))
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    return MessageResponse(message="Token refreshed")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
