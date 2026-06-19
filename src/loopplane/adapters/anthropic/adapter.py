"""The Anthropic (Claude) model-provider adapter (020).

Implements the existing model boundary over the Anthropic messages API. The SDK is
reached only through an injected client (built lazily by the config's factory), and the
stream is mapped by duck-typing, so the adapter imports without the ``anthropic`` extra
and is tested offline with a stub client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from loopplane.adapters._model_errors import ModelProviderError, error_text
from loopplane.adapters.anthropic.config import AnthropicConfig
from loopplane.adapters.anthropic.mapping import (
    AnthropicStreamDecoder,
    build_messages,
    build_tools,
)
from loopplane.model.boundary import ContextOverflowError, ModelIncrement, ModelRequest


def _is_overflow(exc: BaseException) -> bool:
    if getattr(exc, "status_code", None) != 400:
        return False
    text = error_text(exc).lower()
    return "too long" in text or ("context" in text and "exceed" in text)


def _translate_error(exc: BaseException) -> BaseException:
    if _is_overflow(exc):
        return ContextOverflowError(
            "anthropic reported the prompt exceeds the model context window"
        )
    return ModelProviderError(f"anthropic request failed: {type(exc).__name__}")


class AnthropicModel:
    """A :class:`loopplane.model.ModelBoundary` backed by the Anthropic messages API."""

    def __init__(self, config: AnthropicConfig) -> None:
        self._config = config
        self._client: Any = (
            config.client
            if config.client is not None
            else config.client_factory(config.api_key)
        )

    def context_capacity(self) -> int:
        return self._config.context_capacity

    def accepts_media(self) -> bool:
        """Whether this model accepts image input (spec 036; ADR 0001 D5)."""
        return self._config.accepts_media

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": request.limits.max_output_tokens
            or self._config.max_output_tokens,
            "messages": build_messages(request.context),
            "stream": True,
        }
        tools = build_tools(request.tools)
        if tools:
            kwargs["tools"] = tools

        try:
            stream = await self._client.messages.create(**kwargs)
        except Exception as exc:
            raise _translate_error(exc) from exc

        decoder = AnthropicStreamDecoder()
        try:
            async for event in stream:
                for increment in decoder.feed(event):
                    yield increment
        except Exception as exc:
            raise _translate_error(exc) from exc

        if not decoder.ended:
            yield decoder.turn_end()
