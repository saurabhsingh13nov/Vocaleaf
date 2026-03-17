"""Auth business logic — register, authenticate, look up users."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, password_needs_rehash, verify_password
from app.models.auth_identity import AuthIdentity
from app.models.enums import AuthProvider, UserStatus
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.subscription import ensure_user_has_free_subscription
from app.services.user_roles import ensure_seeded_user_roles


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def _initialize_new_user_account(
    db: AsyncSession,
    *,
    user: User,
    provider: AuthProvider,
) -> None:
    await ensure_user_has_free_subscription(db, user_id=user.id)
    record_audit_event(
        db,
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        event_type="auth.registered",
        event_data={"provider": provider.value},
    )


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
) -> User:
    await ensure_seeded_user_roles(db)

    # Check for existing user by email
    existing = await db.execute(
        select(User).where(User.primary_email == email)
    )
    if existing.scalar_one_or_none():
        raise AuthError("Email already registered", status_code=409)

    # Also check auth_identities for the email (e.g. OAuth user with same email)
    existing_identity = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == AuthProvider.PASSWORD,
            AuthIdentity.email == email,
        )
    )
    if existing_identity.scalar_one_or_none():
        raise AuthError("Email already registered", status_code=409)

    user = User(
        primary_email=email,
        full_name=full_name,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()  # Get user.id

    identity = AuthIdentity(
        user_id=user.id,
        provider=AuthProvider.PASSWORD,
        provider_user_id=email,
        email=email,
        password_hash=hash_password(password),
        is_primary=True,
    )
    db.add(identity)
    await _initialize_new_user_account(db, user=user, provider=AuthProvider.PASSWORD)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    generic_error = AuthError("Invalid email or password", status_code=401)

    result = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == AuthProvider.PASSWORD,
            AuthIdentity.email == email,
        )
    )
    identity = result.scalar_one_or_none()
    if not identity or not identity.password_hash:
        raise generic_error

    if not verify_password(password, identity.password_hash):
        raise generic_error

    # Look up user separately to avoid async lazy-load
    user_result = await db.execute(
        select(User).where(
            User.id == identity.user_id,
            User.status == UserStatus.ACTIVE,
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise generic_error

    # Transparent rehash if needed
    if password_needs_rehash(identity.password_hash):
        identity.password_hash = hash_password(password)

    now = datetime.now(UTC).replace(tzinfo=None)
    identity.last_login_at = now
    user.last_login_at = now
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_google_user(
    db: AsyncSession,
    sub: str,
    email: str,
    full_name: str | None,
    avatar_url: str | None,
) -> User:
    return await _authenticate_oauth_user(
        db,
        provider=AuthProvider.GOOGLE,
        sub=sub,
        email=email,
        full_name=full_name,
        avatar_url=avatar_url,
        email_verified=True,
    )


async def link_google_identity(
    db: AsyncSession,
    email: str,
    password: str,
    sub: str,
    name: str | None,
    avatar_url: str | None,
) -> User:
    del name, avatar_url
    return await _link_oauth_identity(
        db,
        provider=AuthProvider.GOOGLE,
        email=email,
        password=password,
        sub=sub,
    )


async def authenticate_apple_user(
    db: AsyncSession,
    sub: str,
    email: str | None,
    full_name: str | None,
    email_verified: bool,
) -> User:
    return await _authenticate_oauth_user(
        db,
        provider=AuthProvider.APPLE,
        sub=sub,
        email=email,
        full_name=full_name,
        avatar_url=None,
        email_verified=email_verified,
    )


async def link_apple_identity(
    db: AsyncSession,
    email: str | None,
    password: str,
    sub: str,
) -> User:
    return await _link_oauth_identity(
        db,
        provider=AuthProvider.APPLE,
        email=email,
        password=password,
        sub=sub,
    )


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.status == UserStatus.ACTIVE,
        )
    )
    return result.scalar_one_or_none()


def _provider_label(provider: AuthProvider) -> str:
    return provider.value.capitalize()


async def _authenticate_oauth_user(
    db: AsyncSession,
    *,
    provider: AuthProvider,
    sub: str,
    email: str | None,
    full_name: str | None,
    avatar_url: str | None,
    email_verified: bool,
) -> User:
    await ensure_seeded_user_roles(db)

    result = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == sub,
        )
    )
    identity = result.scalar_one_or_none()

    now = datetime.now(UTC).replace(tzinfo=None)

    if identity:
        user_result = await db.execute(select(User).where(User.id == identity.user_id))
        user = user_result.scalar_one()
        identity.last_login_at = now
        user.last_login_at = now
        await db.commit()
        await db.refresh(user)
        return user

    if not email:
        raise AuthError(
            f"{_provider_label(provider)} credential is missing email for first-time sign-in",
            status_code=400,
        )

    existing_user = await db.execute(select(User).where(User.primary_email == email))
    if existing_user.scalar_one_or_none():
        raise AuthError(
            "Email already registered with a different method",
            status_code=409,
        )

    user = User(
        primary_email=email,
        full_name=full_name,
        avatar_url=avatar_url,
        status=UserStatus.ACTIVE,
        email_verified_at=now if email_verified else None,
        last_login_at=now,
    )
    db.add(user)
    await db.flush()

    identity = AuthIdentity(
        user_id=user.id,
        provider=provider,
        provider_user_id=sub,
        email=email,
        password_hash=None,
        is_primary=True,
        is_verified=email_verified,
        last_login_at=now,
    )
    db.add(identity)
    await _initialize_new_user_account(db, user=user, provider=provider)
    await db.commit()
    await db.refresh(user)
    return user


async def _link_oauth_identity(
    db: AsyncSession,
    *,
    provider: AuthProvider,
    email: str | None,
    password: str,
    sub: str,
) -> User:
    if not email:
        raise AuthError(
            f"{_provider_label(provider)} credential is missing email for account linking",
            status_code=400,
        )

    user = await authenticate_user(db, email, password)

    existing = await db.execute(
        select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == sub,
        )
    )
    if existing.scalar_one_or_none():
        return user

    identity = AuthIdentity(
        user_id=user.id,
        provider=provider,
        provider_user_id=sub,
        email=email,
        password_hash=None,
        is_primary=False,
        is_verified=True,
    )
    db.add(identity)
    await db.commit()
    await db.refresh(user)
    return user
