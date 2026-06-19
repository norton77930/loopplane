"""Provider-shaped stub clients and event builders for the model-adapter suites (020).

The adapters consume provider streams by duck-typing, so a stub client that yields plain
``SimpleNamespace`` events drives a real loop with no SDK and no credential.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel
from loopplane.adapters.gemini import GeminiConfig, GeminiModel
from loopplane.adapters.openai import OpenAIConfig, OpenAIModel
from loopplane.model import ModelBoundary

PROVIDERS = ("anthropic", "openai", "gemini")

# A turn spec is ("text", text) or ("tool", call_id, name, input_dict).
Turn = tuple[Any, ...]


class StubAPIError(Exception):
    """A stand-in provider error carrying the attributes the adapters inspect."""

    def __init__(
        self, message: str, *, status_code: int | None = None, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for event in events:
        if isinstance(event, BaseException):
            raise event
        yield event


class _Endpoint:
    def __init__(self, owner: _StubClient) -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> Any:
        return self._owner.next_turn(kwargs)


class _StubClient:
    def __init__(self, turns: list[Any]) -> None:
        self._turns = list(turns)
        self._cursor = 0
        self.calls: list[dict[str, Any]] = []

    def next_turn(self, kwargs: dict[str, Any]) -> Any:
        self.calls.append(kwargs)
        index = min(self._cursor, len(self._turns) - 1)
        self._cursor += 1
        item = self._turns[index]
        if isinstance(item, BaseException):
            raise item
        return _aiter(item)


class AnthropicStubClient(_StubClient):
    def __init__(self, turns: list[Any]) -> None:
        super().__init__(turns)
        self.messages = _Endpoint(self)


class OpenAIStubClient(_StubClient):
    def __init__(self, turns: list[Any]) -> None:
        super().__init__(turns)
        self.chat = SimpleNamespace(completions=_Endpoint(self))


class _GeminiModels:
    def __init__(self, owner: _StubClient) -> None:
        self._owner = owner

    async def generate_content_stream(self, **kwargs: Any) -> Any:
        return self._owner.next_turn(kwargs)


class GeminiStubClient(_StubClient):
    def __init__(self, turns: list[Any]) -> None:
        super().__init__(turns)
        self.aio = SimpleNamespace(models=_GeminiModels(self))


def _anthropic_events(turn: Turn) -> list[Any]:
    ns = SimpleNamespace
    start = ns(
        type="message_start",
        message=ns(usage=ns(input_tokens=11, cache_read_input_tokens=0)),
    )
    stop = ns(type="message_stop")
    if turn[0] == "text":
        return [
            start,
            ns(type="content_block_start", index=0, content_block=ns(type="text")),
            ns(
                type="content_block_delta",
                index=0,
                delta=ns(type="text_delta", text=turn[1]),
            ),
            ns(type="content_block_stop", index=0),
            ns(
                type="message_delta",
                delta=ns(stop_reason="end_turn"),
                usage=ns(output_tokens=7),
            ),
            stop,
        ]
    _, call_id, name, arguments = turn
    return [
        start,
        ns(
            type="content_block_start",
            index=0,
            content_block=ns(type="tool_use", id=call_id, name=name),
        ),
        ns(
            type="content_block_delta",
            index=0,
            delta=ns(type="input_json_delta", partial_json=json.dumps(arguments)),
        ),
        ns(type="content_block_stop", index=0),
        ns(
            type="message_delta",
            delta=ns(stop_reason="tool_use"),
            usage=ns(output_tokens=7),
        ),
        stop,
    ]


def _openai_chunks(turn: Turn) -> list[Any]:
    ns = SimpleNamespace
    usage = ns(
        usage=ns(
            prompt_tokens=11,
            completion_tokens=7,
            prompt_tokens_details=None,
            completion_tokens_details=None,
        ),
        choices=[],
    )
    if turn[0] == "text":
        return [
            ns(
                usage=None,
                choices=[
                    ns(delta=ns(content=turn[1], tool_calls=None), finish_reason=None)
                ],
            ),
            ns(
                usage=None,
                choices=[
                    ns(delta=ns(content=None, tool_calls=None), finish_reason="stop")
                ],
            ),
            usage,
        ]
    _, call_id, name, arguments = turn
    return [
        ns(
            usage=None,
            choices=[
                ns(
                    delta=ns(
                        content=None,
                        tool_calls=[
                            ns(
                                index=0,
                                id=call_id,
                                function=ns(name=name, arguments=json.dumps(arguments)),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
        ),
        ns(
            usage=None,
            choices=[
                ns(
                    delta=ns(content=None, tool_calls=None),
                    finish_reason="tool_calls",
                )
            ],
        ),
        usage,
    ]


def _gemini_chunks(turn: Turn) -> list[Any]:
    ns = SimpleNamespace
    usage = ns(
        prompt_token_count=11,
        candidates_token_count=7,
        cached_content_token_count=0,
        thoughts_token_count=0,
    )
    if turn[0] == "text":
        return [
            ns(
                candidates=[
                    ns(
                        content=ns(
                            parts=[ns(text=turn[1], thought=None, function_call=None)]
                        ),
                        finish_reason="STOP",
                    )
                ],
                usage_metadata=usage,
            )
        ]
    _, _call_id, name, arguments = turn
    return [
        ns(
            candidates=[
                ns(
                    content=ns(
                        parts=[
                            ns(
                                text=None,
                                thought=None,
                                function_call=ns(name=name, args=arguments),
                            )
                        ]
                    ),
                    finish_reason="STOP",
                )
            ],
            usage_metadata=usage,
        )
    ]


def make_model(provider: str, script: list[Turn]) -> tuple[ModelBoundary, _StubClient]:
    if provider == "anthropic":
        anthropic_client = AnthropicStubClient([_anthropic_events(t) for t in script])
        anthropic = AnthropicModel(
            AnthropicConfig(model="claude-stub", client=anthropic_client)
        )
        return anthropic, anthropic_client
    if provider == "gemini":
        gemini_client = GeminiStubClient([_gemini_chunks(t) for t in script])
        gemini = GeminiModel(GeminiConfig(model="gemini-stub", client=gemini_client))
        return gemini, gemini_client
    openai_client = OpenAIStubClient([_openai_chunks(t) for t in script])
    openai = OpenAIModel(OpenAIConfig(model="gpt-stub", client=openai_client))
    return openai, openai_client


def make_failing_model(
    provider: str, error: BaseException
) -> tuple[ModelBoundary, _StubClient]:
    if provider == "anthropic":
        anthropic_client = AnthropicStubClient([error])
        anthropic = AnthropicModel(
            AnthropicConfig(model="claude-stub", client=anthropic_client)
        )
        return anthropic, anthropic_client
    if provider == "gemini":
        gemini_client = GeminiStubClient([error])
        gemini = GeminiModel(GeminiConfig(model="gemini-stub", client=gemini_client))
        return gemini, gemini_client
    openai_client = OpenAIStubClient([error])
    openai = OpenAIModel(OpenAIConfig(model="gpt-stub", client=openai_client))
    return openai, openai_client


def overflow_error(provider: str) -> StubAPIError:
    if provider == "anthropic":
        return StubAPIError(
            "prompt is too long: 200000 tokens > 100000 maximum",
            status_code=400,
        )
    if provider == "gemini":
        return StubAPIError(
            "input token count exceeds the maximum number of tokens allowed",
            status_code=400,
            code="INVALID_ARGUMENT",
        )
    return StubAPIError(
        "This model's maximum context length is 8192 tokens; reduce the length.",
        status_code=400,
        code="context_length_exceeded",
    )
