"""Unit tests for the OpenAI-compatible providers (spec 035): OpenRouter and
Ollama reuse OpenAIModel and differ only in the client's base_url. Offline — the
``openai`` SDK is replaced by a fake module that records the client kwargs.
"""

from __future__ import annotations

import sys
import types

import pytest

from loopplane.adapters.openai import OpenAIModel
from loopplane.adapters.openai_compat import (
    OLLAMA_BASE_URL,
    OPENROUTER_BASE_URL,
    ollama_model,
    openrouter_model,
)


class _FakeAsyncOpenAI:
    last_kwargs: dict[str, object] = {}

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> type[_FakeAsyncOpenAI]:
    module = types.ModuleType("openai")
    module.AsyncOpenAI = _FakeAsyncOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", module)
    _FakeAsyncOpenAI.last_kwargs = {}
    return _FakeAsyncOpenAI


def test_openrouter_passes_its_base_url_and_injected_key(
    fake_openai: type[_FakeAsyncOpenAI],
) -> None:
    # Constructing the model (client=None) triggers the lazy client factory.
    openrouter_model("anthropic/claude-3.5-sonnet", api_key="sk-test")
    assert fake_openai.last_kwargs == {
        "api_key": "sk-test",
        "base_url": OPENROUTER_BASE_URL,
    }


def test_ollama_uses_the_local_base_url_and_a_placeholder_key(
    fake_openai: type[_FakeAsyncOpenAI],
) -> None:
    ollama_model("llama3")
    assert fake_openai.last_kwargs == {
        "api_key": "ollama",
        "base_url": OLLAMA_BASE_URL,
    }


def test_ollama_accepts_a_custom_base_url(
    fake_openai: type[_FakeAsyncOpenAI],
) -> None:
    ollama_model("llama3", base_url="http://remote-host:11434/v1")
    assert fake_openai.last_kwargs["base_url"] == "http://remote-host:11434/v1"


def test_compat_providers_build_openai_models() -> None:
    # Injecting a client bypasses the factory (and the openai import), proving
    # both providers reuse OpenAIModel unchanged.
    assert isinstance(openrouter_model("x", client=object()), OpenAIModel)
    assert isinstance(ollama_model("x", client=object()), OpenAIModel)
