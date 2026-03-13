"""Tests for process-local async DB session management."""

from types import SimpleNamespace

from app.db import session as db_session_module


def test_get_async_session_factory_reuses_within_process_and_rebuilds_after_fork(monkeypatch):
    engine_calls: list[object] = []
    factory_calls: list[object] = []
    current_pid = [101]

    def fake_create_async_engine(database_url: str, echo: bool):
        engine = object()
        engine_calls.append(engine)
        return engine

    def fake_async_sessionmaker(engine, class_, expire_on_commit):
        factory = object()
        factory_calls.append(factory)
        return factory

    monkeypatch.setattr(db_session_module, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(db_session_module, "async_sessionmaker", fake_async_sessionmaker)
    monkeypatch.setattr(db_session_module.os, "getpid", lambda: current_pid[0])

    db_session_module.reset_session_state()

    first_factory = db_session_module.get_async_session_factory()
    second_factory = db_session_module.get_async_session_factory()
    current_pid[0] = 202
    third_factory = db_session_module.get_async_session_factory()

    assert first_factory is second_factory
    assert first_factory is not third_factory
    assert len(engine_calls) == 2
    assert len(factory_calls) == 2

    db_session_module.reset_session_state()


async def test_dispose_session_state_clears_cached_engine(monkeypatch):
    dispose_calls: list[str] = []

    class FakeEngine:
        async def dispose(self) -> None:
            dispose_calls.append("disposed")

    monkeypatch.setattr(db_session_module, "create_async_engine", lambda database_url, echo: FakeEngine())
    monkeypatch.setattr(
        db_session_module,
        "async_sessionmaker",
        lambda engine, class_, expire_on_commit: SimpleNamespace(engine=engine),
    )
    monkeypatch.setattr(db_session_module.os, "getpid", lambda: 303)

    db_session_module.reset_session_state()
    factory = db_session_module.get_async_session_factory()
    assert factory is not None

    await db_session_module.dispose_session_state()

    assert dispose_calls == ["disposed"]
    assert db_session_module._engine is None
    assert db_session_module._async_session_factory is None
    assert db_session_module._engine_pid is None
