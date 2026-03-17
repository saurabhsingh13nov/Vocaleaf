"""Tests for child profile CRUD endpoints."""

import uuid

import pytest
from httpx import AsyncClient


# ── Helpers ──────────────────────────────────────────────────────────

REGISTER_URL = "/api/auth/register"
CHILDREN_URL = "/api/children"


async def register_and_get_client(client: AsyncClient, suffix: str = "") -> AsyncClient:
    """Register a user and return the same client (cookies are set)."""
    await client.post(
        REGISTER_URL,
        json={
            "email": f"parent{suffix}@example.com",
            "password": "securepass123",
            "full_name": f"Parent {suffix}",
        },
    )
    return client


async def create_child(client: AsyncClient, name: str = "Luna", **kwargs) -> dict:
    payload = {"name": name, **kwargs}
    resp = await client.post(CHILDREN_URL, json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── Create ───────────────────────────────────────────────────────────


async def test_create_child_success(client: AsyncClient):
    await register_and_get_client(client)
    data = await create_child(client, name="Luna", age=5)

    assert data["name"] == "Luna"
    assert data["age"] == 5
    assert data["id"] is not None
    assert data["user_id"] is not None


async def test_create_child_all_fields(client: AsyncClient):
    await register_and_get_client(client)
    data = await create_child(
        client,
        name="Max",
        age=7,
        favorite_themes={"adventure": True},
        favorite_characters={"dragon": "Sparky"},
        bedtime_preferences={"duration": "short"},
    )

    assert data["favorite_themes"] == {"adventure": True}
    assert data["favorite_characters"] == {"dragon": "Sparky"}
    assert data["bedtime_preferences"] == {"duration": "short"}


async def test_create_child_missing_name(client: AsyncClient):
    await register_and_get_client(client)
    resp = await client.post(CHILDREN_URL, json={"age": 5})
    assert resp.status_code == 422


async def test_create_child_unauthenticated(client: AsyncClient):
    resp = await client.post(CHILDREN_URL, json={"name": "Luna"})
    assert resp.status_code == 401


async def test_create_child_with_bearer_token(client: AsyncClient):
    register_resp = await client.post(
        REGISTER_URL,
        json={
            "email": "bearer-parent@example.com",
            "password": "securepass123",
            "full_name": "Bearer Parent",
        },
    )
    access_token = register_resp.json()["access_token"]

    client.cookies.clear()
    resp = await client.post(
        CHILDREN_URL,
        json={"name": "Luna"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert resp.status_code == 201
    assert resp.json()["name"] == "Luna"


# ── List ─────────────────────────────────────────────────────────────


async def test_list_children_empty(client: AsyncClient):
    await register_and_get_client(client)
    resp = await client.get(CHILDREN_URL)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_children_with_data(client: AsyncClient):
    await register_and_get_client(client)
    await create_child(client, name="Luna")
    await create_child(client, name="Max")

    resp = await client.get(CHILDREN_URL)
    assert resp.status_code == 200
    children = resp.json()
    assert len(children) == 2
    assert children[0]["name"] == "Luna"
    assert children[1]["name"] == "Max"


async def test_list_children_only_own(client: AsyncClient, db_session):
    """A second user's children should not appear."""
    # User A
    await register_and_get_client(client, suffix="A")
    await create_child(client, name="Luna")

    # Register user B in a separate client sharing the same DB
    from httpx import ASGITransport, AsyncClient as HC
    from app.main import app as fastapi_app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)

    async with HC(transport=transport, base_url="https://test") as client_b:
        await register_and_get_client(client_b, suffix="B")
        await create_child(client_b, name="Max")

        # User B only sees their own
        resp = await client_b.get(CHILDREN_URL)
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Max"

    # User A only sees their own
    resp = await client.get(CHILDREN_URL)
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Luna"


# ── Get ──────────────────────────────────────────────────────────────


async def test_get_child_success(client: AsyncClient):
    await register_and_get_client(client)
    child = await create_child(client, name="Luna")

    resp = await client.get(f"{CHILDREN_URL}/{child['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Luna"


async def test_get_child_not_found(client: AsyncClient):
    await register_and_get_client(client)
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"{CHILDREN_URL}/{fake_id}")
    assert resp.status_code == 404


async def test_get_child_wrong_user(client: AsyncClient, db_session):
    """User B cannot access User A's child."""
    await register_and_get_client(client, suffix="A")
    child = await create_child(client, name="Luna")

    from httpx import ASGITransport, AsyncClient as HC
    from app.main import app as fastapi_app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)

    async with HC(transport=transport, base_url="https://test") as client_b:
        await register_and_get_client(client_b, suffix="B")
        resp = await client_b.get(f"{CHILDREN_URL}/{child['id']}")
        assert resp.status_code == 404


# ── Update ───────────────────────────────────────────────────────────


async def test_update_child_success(client: AsyncClient):
    await register_and_get_client(client)
    child = await create_child(client, name="Luna", age=5)

    resp = await client.put(
        f"{CHILDREN_URL}/{child['id']}",
        json={"name": "Luna Star", "age": 6},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Luna Star"
    assert resp.json()["age"] == 6


async def test_update_child_partial(client: AsyncClient):
    await register_and_get_client(client)
    child = await create_child(client, name="Luna", age=5)

    resp = await client.put(
        f"{CHILDREN_URL}/{child['id']}",
        json={"name": "Luna Star"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Luna Star"
    assert resp.json()["age"] == 5  # unchanged


async def test_update_child_not_found(client: AsyncClient):
    await register_and_get_client(client)
    fake_id = str(uuid.uuid4())
    resp = await client.put(f"{CHILDREN_URL}/{fake_id}", json={"name": "Ghost"})
    assert resp.status_code == 404


async def test_update_child_wrong_user(client: AsyncClient, db_session):
    await register_and_get_client(client, suffix="A")
    child = await create_child(client, name="Luna")

    from httpx import ASGITransport, AsyncClient as HC
    from app.main import app as fastapi_app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)

    async with HC(transport=transport, base_url="https://test") as client_b:
        await register_and_get_client(client_b, suffix="B")
        resp = await client_b.put(
            f"{CHILDREN_URL}/{child['id']}",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 404


# ── Delete ───────────────────────────────────────────────────────────


async def test_delete_child_success(client: AsyncClient):
    await register_and_get_client(client)
    child = await create_child(client, name="Luna")

    resp = await client.delete(f"{CHILDREN_URL}/{child['id']}")
    assert resp.status_code == 204

    # Confirm gone
    resp = await client.get(f"{CHILDREN_URL}/{child['id']}")
    assert resp.status_code == 404


async def test_delete_child_not_found(client: AsyncClient):
    await register_and_get_client(client)
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"{CHILDREN_URL}/{fake_id}")
    assert resp.status_code == 404


async def test_delete_child_wrong_user(client: AsyncClient, db_session):
    await register_and_get_client(client, suffix="A")
    child = await create_child(client, name="Luna")

    from httpx import ASGITransport, AsyncClient as HC
    from app.main import app as fastapi_app
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)

    async with HC(transport=transport, base_url="https://test") as client_b:
        await register_and_get_client(client_b, suffix="B")
        resp = await client_b.delete(f"{CHILDREN_URL}/{child['id']}")
        assert resp.status_code == 404

    # Confirm still exists for user A
    resp = await client.get(f"{CHILDREN_URL}/{child['id']}")
    assert resp.status_code == 200
