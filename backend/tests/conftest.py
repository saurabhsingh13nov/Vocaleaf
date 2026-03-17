"""Async test fixtures with isolated Postgres setup and per-test rollback."""

import os
from collections.abc import AsyncGenerator

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.roles import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_STAFF
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

# Import all models so Base.metadata knows about them
import app.models  # noqa: F401


def _build_test_database_url() -> URL:
    raw_url = os.getenv("TEST_DATABASE_URL")
    url = make_url(raw_url or settings.database_url)

    if raw_url:
        test_url = url
    else:
        database_name = url.database or "vocaleaf"
        test_url = url.set(database=f"{database_name}_test")

    if not test_url.database or not test_url.database.endswith("_test"):
        raise RuntimeError(
            "Backend tests must use a dedicated test database. "
            "Set TEST_DATABASE_URL to a database whose name ends with '_test'."
        )

    return test_url


def _asyncpg_dsn(url: URL) -> str:
    return url.render_as_string(hide_password=False).replace("+asyncpg", "")


async def _ensure_test_database_exists(test_url: URL) -> None:
    admin_url = test_url.set(database="postgres")
    connection = await asyncpg.connect(_asyncpg_dsn(admin_url))

    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            test_url.database,
        )
        if not exists:
            database_name = test_url.database.replace('"', '""')
            await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


async def _reset_test_database(test_url: URL) -> None:
    """Reset schema inside the dedicated test database."""
    engine = create_async_engine(
        test_url.render_as_string(hide_password=False),
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                """
                INSERT INTO user_roles (code, display_name, description)
                VALUES
                    (:customer_code, 'Customer', 'Standard customer account with no internal admin access.'),
                    (:staff_code, 'Staff', 'Internal support role with access to support tooling.'),
                    (:admin_code, 'Admin', 'Internal admin role with access to plan and role management.')
                """
            ),
            {
                "customer_code": ROLE_CUSTOMER,
                "staff_code": ROLE_STAFF,
                "admin_code": ROLE_ADMIN,
            },
        )

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def reset_test_database() -> None:
    """Reset the dedicated test database once before the suite runs."""
    test_url = _build_test_database_url()
    await _ensure_test_database_exists(test_url)
    await _reset_test_database(test_url)


@pytest_asyncio.fixture
async def db_session(reset_test_database) -> AsyncGenerator[AsyncSession]:
    """Yield a session wrapped in a savepoint that rolls back after each test."""
    test_url = _build_test_database_url()
    engine = create_async_engine(
        test_url.render_as_string(hide_password=False),
        echo=False,
    )
    conn = await engine.connect()
    txn = await conn.begin()
    session_factory = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()

    nested = await conn.begin_nested()

    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = conn.sync_connection.begin_nested()

    yield session

    await session.close()
    await txn.rollback()
    await conn.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient]:
    """HTTP test client with DB dependency overridden."""
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
