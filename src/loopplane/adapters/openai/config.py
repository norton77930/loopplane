"""Configuration for the OpenAI model adapter (020).

Carries no secret of its own: the credential is injected (``api_key``) or comes from the
host environment via the default client factory. The SDK is imported lazily inside the
factory so the adapter package imports without the ``openai`` extra installed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# A conservative default window; override per model via the config.
_DEFAULT_CONTEXT_CAPACITY = 128_000


def default_client_factory(api_key: str | None) -> Any:
    """Build the official async OpenAI client, importing the SDK lazily."""

    from openai import AsyncOpenAI

    if api_key is not None:
        return AsyncOpenAI(api_key=api_key)
    return AsyncOpenAI()


@dataclass(frozen=True)
class OpenAIConfig:
    """Declarative configuration for :class:`OpenAIModel`.

    ``client`` lets a test (or an embedder) inject a ready client; when it is ``None``
    the ``client_factory`` builds one from ``api_key`` (or the environment).
    """

    model: str
    context_capacity: int = _DEFAULT_CONTEXT_CAPACITY
    max_output_tokens: int | None = None
    api_key: str | None = None
    client: Any = None
    client_factory: Callable[[str | None], Any] = default_client_factory
    # Whether this model accepts image input (spec 036; ADR 0001 D5). GPT-4o-class
    # models are vision-capable, so the default is True; set False for a text-only
    # model so the web/API layer degrades gracefully.
    accepts_media: bool = True
