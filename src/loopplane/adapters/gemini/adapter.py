"""The native Google Gemini model-provider adapter (037).

Implements the existing model boundary over the direct Google GenAI API. The SDK is
reached only through an injected client (built lazily by the config's factory), and the
stream is mapped by duck-typing, so the adapter imports without the ``gemini`` extra and
is tested offline with a stub client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from loopplane.adapters._model_errors import ModelProviderError, error_text
from loopplane.adapters.gemini.config import GeminiConfig
from loopplane.adapters.gemini.mapping import (
    GeminiStreamDecoder,
    build_contents,
    build_tools,
)
from loopplane.model.boundary import ContextOverflowError, ModelIncrement, ModelRequest


def _is_overflow(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    text = error_text(exc).lower()
    if status in (429, "RESOURCE_EXHAUSTED") or "resource_exhausted" in text:
        return True
    if status in (400, "INVALID_ARGUMENT") or "invalid_argument" in text:
        return (
            "token" in text
            and ("exceed" in text or "maximum" in text or "too long" in text)
        ) or ("context" in text and ("length" in text or "window" in text))
    return False


def _translate_error(exc: BaseException) -> BaseException:
    if _is_overflow(exc):
        return ContextOverflowError(
            "gemini reported the prompt exceeds the model context window"
        )
    return ModelProviderError(f"gemini request failed: {type(exc).__name__}")


class GeminiModel:
    """A :class:`loopplane.model.ModelBoundary` backed by the Google GenAI API."""

    def __init__(self, config: GeminiConfig) -> None:
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
        config: dict[str, Any] = {}
        tools = build_tools(request.tools)
        if tools:
            config["tools"] = tools
        max_output = request.limits.max_output_tokens or self._config.max_output_tokens
        if max_output:
            config["max_output_tokens"] = max_output

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "contents": build_contents(request.context),
        }
        if config:
            kwargs["config"] = config

        try:
            stream = await self._client.aio.models.generate_content_stream(**kwargs)
        except Exception as exc:
            raise _translate_error(exc) from exc

        decoder = GeminiStreamDecoder()
        try:
            async for chunk in stream:
                for increment in decoder.feed(chunk):
                    yield increment
        except Exception as exc:
            raise _translate_error(exc) from exc

        for increment in decoder.finish():
            yield increment
