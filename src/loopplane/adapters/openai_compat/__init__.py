"""OpenAI-compatible model providers (spec 035): OpenRouter and Ollama.

Both REUSE the unit-020 :class:`~loopplane.adapters.openai.OpenAIModel` and its
chat-completions mapping unchanged, differing only in the client's ``base_url``
(and OpenRouter's injected key). No new dependency beyond the existing ``openai``
extra; the SDK is imported lazily inside the client factory, exactly as the
OpenAI adapter does — so this package imports without the ``openai`` extra and is
tested offline.

OpenRouter brokers 100+ models (including Claude, Gemini, Llama, …) behind the
OpenAI wire format, so this unit widens provider reach without a per-provider
adapter. A *native* Gemini adapter (direct Google GenAI API, to preserve
``thought_signature`` across tool turns) is a separate, later unit; Gemini is
reachable today via OpenRouter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loopplane.adapters.openai import OpenAIConfig, OpenAIModel

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_BASE_URL = "http://localhost:11434/v1"

# A conservative default window; override per model via the constructors.
_DEFAULT_CONTEXT_CAPACITY = 128_000


def _base_url_client_factory(base_url: str) -> Callable[[str | None], Any]:
    """Mirror the OpenAI adapter's default client factory, but pin the client's
    ``base_url`` to an OpenAI-compatible endpoint. The SDK is imported lazily so
    the package imports without the ``openai`` extra installed."""

    def factory(api_key: str | None) -> Any:
        from openai import AsyncOpenAI

        if api_key is not None:
            return AsyncOpenAI(api_key=api_key, base_url=base_url)
        return AsyncOpenAI(base_url=base_url)

    return factory


def openrouter_model(
    model: str,
    *,
    api_key: str | None = None,
    context_capacity: int = _DEFAULT_CONTEXT_CAPACITY,
    max_output_tokens: int | None = None,
    client: Any = None,
    accepts_media: bool = True,
) -> OpenAIModel:
    """Build an :class:`OpenAIModel` pointed at OpenRouter.

    The OpenAI chat-completions mapping is reused unchanged; only the client's
    ``base_url`` (and the injected key) differ. ``client`` lets a test inject a
    ready stand-in, bypassing the factory. ``accepts_media`` defaults to ``True``
    because OpenRouter brokers vision models (spec 036; ADR 0001 D5); set it
    ``False`` when routing to a text-only model.
    """

    return OpenAIModel(
        OpenAIConfig(
            model=model,
            context_capacity=context_capacity,
            max_output_tokens=max_output_tokens,
            api_key=api_key,
            client=client,
            client_factory=_base_url_client_factory(OPENROUTER_BASE_URL),
            accepts_media=accepts_media,
        )
    )


def ollama_model(
    model: str,
    *,
    base_url: str = OLLAMA_BASE_URL,
    context_capacity: int = _DEFAULT_CONTEXT_CAPACITY,
    max_output_tokens: int | None = None,
    client: Any = None,
    accepts_media: bool = False,
) -> OpenAIModel:
    """Build an :class:`OpenAIModel` pointed at a local Ollama OpenAI-compatible
    endpoint. Ollama ignores the API key, so a placeholder satisfies the SDK
    client; ``base_url`` defaults to the local daemon and is overridable.
    ``accepts_media`` defaults to ``False`` because local Ollama models are
    commonly text-only (spec 036; ADR 0001 D5); set it ``True`` for a local
    vision model.
    """

    return OpenAIModel(
        OpenAIConfig(
            model=model,
            context_capacity=context_capacity,
            max_output_tokens=max_output_tokens,
            api_key="ollama",
            client=client,
            client_factory=_base_url_client_factory(base_url),
            accepts_media=accepts_media,
        )
    )


__all__ = [
    "OLLAMA_BASE_URL",
    "OPENROUTER_BASE_URL",
    "ollama_model",
    "openrouter_model",
]
