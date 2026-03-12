"""Async test fixtures with savepoint-based transaction rollback."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

# Import all models so Base.metadata knows about them
import app.models  # noqa: F401


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Yield a session wrapped in a savepoint that rolls back after each test."""
    engine = create_async_engine(settings.database_url, echo=False)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    conn = await engine.connect()
    txn = await conn.begin()
    session_factory = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()

    # When service code calls commit(), restart the savepoint so the
    # outer transaction remains open — keeps test isolation intact.
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
