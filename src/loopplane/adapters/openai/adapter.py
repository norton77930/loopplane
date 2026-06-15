"""The OpenAI (GPT) model-provider adapter (020).

Implements the existing model boundary over the OpenAI chat-completions API. The SDK is
reached only through an injected client (built lazily by the config's factory), and the
stream is mapped by duck-typing, so the adapter imports without the ``openai`` extra and
is tested offline with a stub client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from loopplane.adapters._model_errors import ModelProviderError, error_text
from loopplane.adapters.openai.config import OpenAIConfig
from loopplane.adapters.openai.mapping import (
    OpenAIStreamDecoder,
    build_messages,
    build_tools,
)
from loopplane.model.boundary import ContextOverflowError, ModelIncrement, ModelRequest


def _is_overflow(exc: BaseException) -> bool:
    if getattr(exc, "code", None) == "context_length_exceeded":
        return True
    if getattr(exc, "status_code", None) != 400:
        return False
    text = error_text(exc).lower()
    return (
        "context length" in text
        or "maximum context" in text
        or "reduce the length" in text
    )


def _translate_error(exc: BaseException) -> BaseException:
    if _is_overflow(exc):
        return ContextOverflowError(
            "openai reported the prompt exceeds the model context window"
        )
    return ModelProviderError(f"openai request failed: {type(exc).__name__}")


class OpenAIModel:
    """A model boundary backed by the OpenAI chat-completions API."""

    def __init__(self, config: OpenAIConfig) -> None:
        self._config = config
        self._client: Any = (
            config.client
            if config.client is not None
            else config.client_factory(config.api_key)
        )

    def context_capacity(self) -> int:
        return self._config.context_capacity

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": build_messages(request.context),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        tools = build_tools(request.tools)
        if tools:
            kwargs["tools"] = tools
        max_output = request.limits.max_output_tokens or self._config.max_output_tokens
        if max_output:
            kwargs["max_tokens"] = max_output

        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise _translate_error(exc) from exc

        decoder = OpenAIStreamDecoder()
        try:
            async for chunk in stream:
                for increment in decoder.feed(chunk):
                    yield increment
        except Exception as exc:
            raise _translate_error(exc) from exc

        for increment in decoder.finish():
            yield increment
