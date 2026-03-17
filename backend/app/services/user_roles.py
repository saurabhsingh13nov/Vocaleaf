"""Helpers for database-backed user roles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_STAFF
from app.models.user_role import UserRole

SEEDED_USER_ROLES = (
    {
        "code": ROLE_CUSTOMER,
        "display_name": "Customer",
        "description": "Standard customer account with no internal admin access.",
    },
    {
        "code": ROLE_STAFF,
        "display_name": "Staff",
        "description": "Internal support role with access to support tooling.",
    },
    {
        "code": ROLE_ADMIN,
        "display_name": "Admin",
        "description": "Internal admin role with access to plan and role management.",
    },
)


async def ensure_seeded_user_roles(db: AsyncSession) -> tuple[dict[str, UserRole], bool]:
    result = await db.execute(select(UserRole))
    roles = list(result.scalars())
    existing_by_code = {role.code: role for role in roles}

    changed = False
    for payload in SEEDED_USER_ROLES:
        if payload["code"] in existing_by_code:
            continue

        role = UserRole(**payload)
        db.add(role)
        existing_by_code[role.code] = role
        changed = True

    if changed:
        await db.flush()

    return existing_by_code, changed


async def get_user_role_by_code(db: AsyncSession, *, code: str) -> UserRole | None:
    normalized_code = code.strip().lower()
    seeded_roles, _ = await ensure_seeded_user_roles(db)
    role = seeded_roles.get(normalized_code)
    if role is not None:
        return role

    result = await db.execute(select(UserRole).where(UserRole.code == normalized_code))
    return result.scalar_one_or_none()
