"""Tests for worker crash cleanup behavior."""

from __future__ import annotations

import uuid

import pytest


def test_audio_worker_task_is_registered() -> None:
    from app.tasks.celery_app import celery_app

    assert "app.workers.audio_worker.generate_page_audio_task" in celery_app.tasks


def test_generate_story_text_task_disposes_session_state_before_cleanup(monkeypatch) -> None:
    from app.workers import text_worker

    story_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    calls: list[tuple[str, str]] = []

    async def fake_run_text_generation(*args, **kwargs) -> None:
        raise RuntimeError("boom")

    async def fake_mark_text_generation_failed(story_uuid, job_uuid, *, error_message: str) -> None:
        calls.append(("cleanup", error_message))

    def fake_dispose() -> None:
        calls.append(("dispose", ""))

    def fake_asyncio_run(coro):
        try:
            return coro.send(None)
        except StopIteration as exc:
            return exc.value

    monkeypatch.setattr(text_worker, "run_text_generation", fake_run_text_generation)
    monkeypatch.setattr(text_worker, "mark_text_generation_failed", fake_mark_text_generation_failed)
    monkeypatch.setattr(text_worker, "dispose_session_state_sync", fake_dispose)
    monkeypatch.setattr(text_worker.asyncio, "run", fake_asyncio_run)

    with pytest.raises(RuntimeError, match="boom"):
        text_worker.generate_story_text_task(story_id, job_id)

    assert calls == [
        ("dispose", ""),
        ("cleanup", "boom"),
    ]


def test_generate_page_image_task_disposes_session_state_before_cleanup(monkeypatch) -> None:
    from app.workers import image_worker

    page_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    calls: list[tuple[str, str]] = []

    async def fake_run_image_generation(*args, **kwargs) -> None:
        raise RuntimeError("image boom")

    async def fake_mark_image_generation_failed(page_uuid, job_uuid, *, error_message: str) -> None:
        calls.append(("cleanup", error_message))

    def fake_dispose() -> None:
        calls.append(("dispose", ""))

    def fake_asyncio_run(coro):
        try:
            return coro.send(None)
        except StopIteration as exc:
            return exc.value

    monkeypatch.setattr(image_worker, "run_image_generation", fake_run_image_generation)
    monkeypatch.setattr(image_worker, "mark_image_generation_failed", fake_mark_image_generation_failed)
    monkeypatch.setattr(image_worker, "dispose_session_state_sync", fake_dispose)
    monkeypatch.setattr(image_worker.asyncio, "run", fake_asyncio_run)

    with pytest.raises(RuntimeError, match="image boom"):
        image_worker.generate_page_image_task(page_id, job_id)

    assert calls == [
        ("dispose", ""),
        ("cleanup", "image boom"),
    ]


def test_clone_voice_profile_task_disposes_session_state_before_cleanup(monkeypatch) -> None:
    from app.workers import voice_clone_worker

    profile_id = str(uuid.uuid4())
    calls: list[str] = []

    async def fake_run_voice_clone(*args, **kwargs) -> None:
        raise RuntimeError("voice boom")

    async def fake_mark_voice_clone_failed(profile_uuid) -> None:
        calls.append("cleanup")

    def fake_dispose() -> None:
        calls.append("dispose")

    def fake_asyncio_run(coro):
        try:
            return coro.send(None)
        except StopIteration as exc:
            return exc.value

    monkeypatch.setattr(voice_clone_worker, "run_voice_clone", fake_run_voice_clone)
    monkeypatch.setattr(voice_clone_worker, "mark_voice_clone_failed", fake_mark_voice_clone_failed)
    monkeypatch.setattr(voice_clone_worker, "dispose_session_state_sync", fake_dispose)
    monkeypatch.setattr(voice_clone_worker.asyncio, "run", fake_asyncio_run)

    with pytest.raises(RuntimeError, match="voice boom"):
        voice_clone_worker.clone_voice_profile_task(profile_id)

    assert calls == ["dispose", "cleanup"]


def test_generate_page_audio_task_disposes_session_state_before_cleanup(monkeypatch) -> None:
    from app.workers import audio_worker

    page_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    calls: list[tuple[str, str]] = []

    async def fake_run_audio_generation(*args, **kwargs) -> None:
        raise RuntimeError("audio boom")

    async def fake_mark_audio_generation_failed(page_uuid, job_uuid, *, error_message: str) -> None:
        calls.append(("cleanup", error_message))

    def fake_dispose() -> None:
        calls.append(("dispose", ""))

    def fake_asyncio_run(coro):
        try:
            return coro.send(None)
        except StopIteration as exc:
            return exc.value

    monkeypatch.setattr(audio_worker, "run_audio_generation", fake_run_audio_generation)
    monkeypatch.setattr(audio_worker, "mark_audio_generation_failed", fake_mark_audio_generation_failed)
    monkeypatch.setattr(audio_worker, "dispose_session_state_sync", fake_dispose)
    monkeypatch.setattr(audio_worker.asyncio, "run", fake_asyncio_run)

    with pytest.raises(RuntimeError, match="audio boom"):
        audio_worker.generate_page_audio_task(page_id, job_id)

    assert calls == [
        ("dispose", ""),
        ("cleanup", "audio boom"),
    ]
