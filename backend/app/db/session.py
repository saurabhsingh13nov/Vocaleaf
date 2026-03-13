import asyncio
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine_pid: int | None = None


def _clear_cached_session_state() -> None:
    global _engine, _async_session_factory, _engine_pid
    _engine = None
    _async_session_factory = None
    _engine_pid = None


def reset_session_state() -> None:
    """Drop cached engine/session references so the current process rebuilds them lazily."""
    _clear_cached_session_state()


def _current_pid() -> int:
    return os.getpid()


def _ensure_process_local_state() -> None:
    # Celery prefork workers must not inherit an async engine bound to the parent process.
    if _engine_pid is not None and _engine_pid != _current_pid():
        reset_session_state()


def get_engine() -> AsyncEngine:
    """Return an async engine scoped to the current process."""
    global _engine, _async_session_factory, _engine_pid

    _ensure_process_local_state()
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
        )
        _async_session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _engine_pid = _current_pid()

    return _engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the lazily created async session factory for the current process."""
    global _async_session_factory

    _ensure_process_local_state()
    if _async_session_factory is None:
        get_engine()

    assert _async_session_factory is not None
    return _async_session_factory


async def dispose_session_state() -> None:
    """Dispose the current process engine, if one has been created."""
    engine = _engine
    _clear_cached_session_state()

    if engine is not None:
        await engine.dispose()


def dispose_session_state_sync() -> None:
    """Synchronous wrapper for Celery worker lifecycle hooks."""
    try:
        asyncio.run(dispose_session_state())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(dispose_session_state())
        finally:
            loop.close()


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields an async database session."""
    async with get_async_session_factory()() as session:
        yield session
