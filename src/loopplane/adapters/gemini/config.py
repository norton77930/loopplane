"""Configuration for the native Gemini model adapter (037).

Carries no secret of its own: the credential is injected (``api_key``) or comes from the
host environment via the default client factory. The SDK is imported lazily inside the
factory so the adapter package imports without the ``gemini`` extra installed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Gemini context windows are large; override per model via the config.
_DEFAULT_CONTEXT_CAPACITY = 1_000_000


def default_client_factory(api_key: str | None) -> Any:
    """Build the official async Google GenAI client, importing the SDK lazily."""

    from google import genai

    if api_key is not None:
        return genai.Client(api_key=api_key)
    return genai.Client()


@dataclass(frozen=True)
class GeminiConfig:
    """Declarative configuration for :class:`GeminiModel`.

    ``client`` lets a test (or an embedder) inject a ready client; when it is ``None``
    the ``client_factory`` builds one from ``api_key`` (or the environment).
    """

    model: str
    context_capacity: int = _DEFAULT_CONTEXT_CAPACITY
    max_output_tokens: int | None = None
    api_key: str | None = None
    client: Any = None
    client_factory: Callable[[str | None], Any] = default_client_factory
    # Whether this model accepts image input (spec 036; ADR 0001 D5). Gemini families
    # are vision-capable, so the default is True; set False for a text-only model so
    # the web/API layer degrades gracefully.
    accepts_media: bool = True
