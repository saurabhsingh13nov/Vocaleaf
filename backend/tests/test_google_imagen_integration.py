"""Tests for the Google Gemini image integration wrapper."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.integrations.google_gemini_image import (
    GeneratedImage,
    GoogleGeminiImageClient,
    GoogleGeminiImageError,
)


def _install_fake_google_genai(monkeypatch, fake_client_class) -> None:
    fake_types = SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: SimpleNamespace(**kwargs),
        ImageConfig=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    fake_module = ModuleType("google.genai")
    fake_module.Client = fake_client_class
    fake_module.types = fake_types

    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_module))
    monkeypatch.setitem(sys.modules, "google.genai", fake_module)
    monkeypatch.setattr("app.integrations.google_gemini_image._get_genai_module", lambda: fake_module)


def test_generate_image_retries_empty_responses(monkeypatch):
    calls: list[dict] = []

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.models = SimpleNamespace(generate_content=self.generate_content)

        def generate_content(self, *, model: str, contents: str, config) -> SimpleNamespace:
            calls.append({"model": model, "contents": contents, "config": config})
            if len(calls) == 1:
                return SimpleNamespace(candidates=[])
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(
                            parts=[
                                SimpleNamespace(
                                    inline_data=SimpleNamespace(
                                        data=b"PNG_BYTES",
                                        mime_type="image/png",
                                    )
                                )
                            ]
                        )
                    )
                ]
            )

    _install_fake_google_genai(monkeypatch, FakeClient)

    client = GoogleGeminiImageClient(
        api_key="test-key",
        model="gemini-3.1-flash-image-preview",
    )
    result = client.generate_image(
        prompt="A lantern in the forest",
        art_style="Dreamy",
        continuity_context="Keep the lantern warm and golden",
    )

    assert result == GeneratedImage(content=b"PNG_BYTES", mime_type="image/png")
    assert len(calls) == 2
    assert calls[0]["model"] == "gemini-3.1-flash-image-preview"
    assert calls[0]["config"].response_modalities == ["IMAGE"]
    assert calls[0]["config"].image_config.aspect_ratio == "4:3"
    assert "Art style: Dreamy" in calls[0]["contents"]
    assert "Visual continuity: Keep the lantern warm and golden" in calls[0]["contents"]


def test_generate_image_raises_after_repeated_empty_responses(monkeypatch):
    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.models = SimpleNamespace(generate_content=self.generate_content)

        def generate_content(self, *, model: str, contents: str, config) -> SimpleNamespace:
            return SimpleNamespace(candidates=[])

    _install_fake_google_genai(monkeypatch, FakeClient)

    client = GoogleGeminiImageClient(
        api_key="test-key",
        model="gemini-3.1-flash-image-preview",
    )

    with pytest.raises(GoogleGeminiImageError, match="returned no images after 3 attempts"):
        client.generate_image(prompt="A lantern in the forest")
