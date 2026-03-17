"""Tests for internal admin APIs and permission boundaries."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.roles import ROLE_ADMIN, ROLE_STAFF
from app.models.plan import Plan
from app.models.usage_credit_grant import UsageCreditGrant
from app.models.user import User
from app.services.auth import register_user

REGISTER_URL = "/api/auth/register"


async def register(client, *, email: str) -> dict:
    response = await client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Admin Test User",
        },
    )
    assert response.status_code == 201
    return response.json()["user"]


async def set_user_role(db_session, *, user_id: str, role: str) -> None:
    user = (await db_session.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one()
    user.role = role
    await db_session.commit()


async def test_customer_cannot_access_admin_users(client):
    await register(client, email="customer-admin-block@example.com")

    response = await client.get("/api/admin/users")

    assert response.status_code == 403


async def test_staff_can_view_admin_data_and_grant_usage_credit(client, db_session):
    user = await register(client, email="staff@example.com")
    await set_user_role(db_session, user_id=user["id"], role=ROLE_STAFF)

    users_response = await client.get("/api/admin/users")
    plans_response = await client.get("/api/admin/plans")
    grant_response = await client.post(
        f"/api/admin/users/{user['id']}/usage-grants",
        json={
            "usage_type": "stories_created",
            "quantity": 2,
            "reason": "Support recovery credit",
        },
    )

    assert users_response.status_code == 200
    assert plans_response.status_code == 200
    assert grant_response.status_code == 200
    assert grant_response.json()["quantity"] == 2

    grants = (await db_session.execute(select(UsageCreditGrant))).scalars().all()
    assert len(grants) == 1
    assert grants[0].usage_type == "stories_created"


async def test_admin_can_edit_plan_and_update_user_role(client, db_session):
    admin_user = await register(client, email="admin@example.com")
    await set_user_role(db_session, user_id=admin_user["id"], role=ROLE_ADMIN)
    target_user = await register_user(
        db_session,
        email="target-role@example.com",
        password="securepass123",
        full_name="Target User",
    )

    plan_response = await client.patch(
        "/api/admin/plans/free",
        json={"monthly_story_limit": 4},
    )
    role_response = await client.patch(
        f"/api/admin/users/{target_user.id}/role",
        json={"role": "staff"},
    )

    assert plan_response.status_code == 200
    assert plan_response.json()["monthly_story_limit"] == 4
    assert role_response.status_code == 200
    assert role_response.json()["role"] == "staff"

    free_plan = (await db_session.execute(select(Plan).where(Plan.code == "free"))).scalar_one()
    updated_target = (await db_session.execute(select(User).where(User.id == target_user.id))).scalar_one()
    assert free_plan.monthly_story_limit == 4
    assert updated_target.role == ROLE_STAFF
