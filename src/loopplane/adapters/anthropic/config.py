"""Configuration for the Anthropic model adapter (020).

Carries no secret of its own: the credential is injected (``api_key``) or comes from the
host environment via the default client factory. The SDK is imported lazily inside the
factory so the adapter package imports without the ``anthropic`` extra installed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# A conservative default window; override per model via the config.
_DEFAULT_CONTEXT_CAPACITY = 200_000
_DEFAULT_MAX_OUTPUT_TOKENS = 4096


def default_client_factory(api_key: str | None) -> Any:
    """Build the official async Anthropic client, importing the SDK lazily."""

    from anthropic import AsyncAnthropic

    if api_key is not None:
        return AsyncAnthropic(api_key=api_key)
    return AsyncAnthropic()


@dataclass(frozen=True)
class AnthropicConfig:
    """Declarative configuration for :class:`AnthropicModel`.

    ``client`` lets a test (or an embedder) inject a ready client; when it is ``None``
    the ``client_factory`` builds one from ``api_key`` (or the environment).
    """

    model: str
    context_capacity: int = _DEFAULT_CONTEXT_CAPACITY
    max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS
    api_key: str | None = None
    client: Any = None
    client_factory: Callable[[str | None], Any] = default_client_factory
    # Whether this model accepts image input (spec 036; ADR 0001 D5). Claude
    # flagship families are vision-capable, so the default is True; set False for a
    # text-only model so the web/API layer degrades gracefully.
    accepts_media: bool = True
