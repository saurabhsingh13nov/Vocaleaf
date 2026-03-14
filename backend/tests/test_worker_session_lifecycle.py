"""Tests for worker-owned DB session disposal."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _fake_session_factory() -> _FakeSessionContext:
    return _FakeSessionContext()


@pytest.mark.asyncio
async def test_run_text_generation_disposes_owned_session_state(monkeypatch) -> None:
    from app.workers import text_worker

    events: list[str] = []

    async def fake_run_in_session(db, *, story_id, job_id) -> None:
        events.append("run")

    async def fake_dispose() -> None:
        events.append("dispose")

    monkeypatch.setattr(text_worker, "get_async_session_factory", lambda: _fake_session_factory)
    monkeypatch.setattr(text_worker, "run_text_generation_in_session", fake_run_in_session)
    monkeypatch.setattr(text_worker, "dispose_session_state", fake_dispose)

    await text_worker.run_text_generation(story_id=object(), job_id=object())  # type: ignore[arg-type]

    assert events == ["run", "dispose"]


@pytest.mark.asyncio
async def test_run_text_generation_does_not_dispose_custom_session_factory(monkeypatch) -> None:
    from app.workers import text_worker

    events: list[str] = []

    async def fake_run_in_session(db, *, story_id, job_id) -> None:
        events.append("run")

    async def fake_dispose() -> None:
        events.append("dispose")

    monkeypatch.setattr(text_worker, "run_text_generation_in_session", fake_run_in_session)
    monkeypatch.setattr(text_worker, "dispose_session_state", fake_dispose)

    await text_worker.run_text_generation(
        story_id=object(),  # type: ignore[arg-type]
        job_id=object(),  # type: ignore[arg-type]
        session_factory=_fake_session_factory,
    )

    assert events == ["run"]


@pytest.mark.asyncio
async def test_run_image_generation_disposes_owned_session_state(monkeypatch) -> None:
    from app.workers import image_worker

    events: list[str] = []

    async def fake_run_in_session(db, *, story_page_id, job_id) -> None:
        events.append("run")

    async def fake_dispose() -> None:
        events.append("dispose")

    monkeypatch.setattr(image_worker, "get_async_session_factory", lambda: _fake_session_factory)
    monkeypatch.setattr(image_worker, "run_image_generation_in_session", fake_run_in_session)
    monkeypatch.setattr(image_worker, "dispose_session_state", fake_dispose)

    await image_worker.run_image_generation(story_page_id=object(), job_id=object())  # type: ignore[arg-type]

    assert events == ["run", "dispose"]


@pytest.mark.asyncio
async def test_run_voice_clone_disposes_owned_session_state(monkeypatch) -> None:
    from app.workers import voice_clone_worker

    events: list[str] = []

    async def fake_run_in_session(db, profile_id) -> None:
        events.append("run")

    async def fake_dispose() -> None:
        events.append("dispose")

    monkeypatch.setattr(voice_clone_worker, "get_async_session_factory", lambda: _fake_session_factory)
    monkeypatch.setattr(voice_clone_worker, "run_voice_clone_in_session", fake_run_in_session)
    monkeypatch.setattr(voice_clone_worker, "dispose_session_state", fake_dispose)

    await voice_clone_worker.run_voice_clone(profile_id=object())  # type: ignore[arg-type]

    assert events == ["run", "dispose"]
