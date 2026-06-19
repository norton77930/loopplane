"""Unit 040: Anthropic explicit prompt-cache breakpoints.

Covers the opt-in cache overlay (``apply_prompt_caching``) and the
``AnthropicConfig.prompt_caching`` toggle: with caching ON the assembled request
carries ``cache_control: {"type": "ephemeral"}`` on the stable prefix (the last
tool definition + the first message's last content block when there are >=2
messages), never on the rolling last message, and never more than 4 breakpoints;
with caching OFF the request is byte-identical to ``build_messages`` /
``build_tools``. Fully offline (a duck-typed stub client; no SDK, no network).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from loopplane.adapters.anthropic import AnthropicConfig, AnthropicModel
from loopplane.adapters.anthropic.mapping import (
    apply_prompt_caching,
    build_messages,
    build_tools,
)
from loopplane.model import Message, ModelRequest, ToolDescriptor
from loopplane.model.content import TextBlock, ToolResultBlock

_EPHEMERAL = {"type": "ephemeral"}


def _tools() -> list[ToolDescriptor]:
    return [
        ToolDescriptor(name="echo", description="d", input_schema={"type": "object"}),
        ToolDescriptor(name="read", description="r", input_schema={"type": "object"}),
    ]


def _multi_turn_context() -> list[Message]:
    return [
        Message(role="user", blocks=[TextBlock(text="instructions + first turn")]),
        Message(role="assistant", blocks=[TextBlock(text="ok")]),
        Message(role="user", blocks=[TextBlock(text="latest rolling turn")]),
    ]


# --- apply_prompt_caching (the overlay, unit) --------------------------------


def test_overlay_marks_last_tool_definition() -> None:
    tools = build_tools(_tools())
    _, cached_tools = apply_prompt_caching(build_messages(_multi_turn_context()), tools)

    assert cached_tools[-1]["cache_control"] == _EPHEMERAL
    # No earlier tool is marked.
    assert "cache_control" not in cached_tools[0]


def test_overlay_marks_first_message_not_the_rolling_tail() -> None:
    messages = build_messages(_multi_turn_context())
    cached_messages, _ = apply_prompt_caching(messages, build_tools(_tools()))

    # First message's last content block is the stable-prefix breakpoint.
    assert cached_messages[0]["content"][-1]["cache_control"] == _EPHEMERAL
    # The rolling last message carries no breakpoint on any block.
    for block in cached_messages[-1]["content"]:
        assert "cache_control" not in block


def test_overlay_emits_at_most_four_breakpoints() -> None:
    cached_messages, cached_tools = apply_prompt_caching(
        build_messages(_multi_turn_context()), build_tools(_tools())
    )
    markers = sum("cache_control" in tool for tool in cached_tools)
    for message in cached_messages:
        markers += sum("cache_control" in block for block in message["content"])
    assert markers <= 4
    # This implementation emits exactly two (last tool + first message).
    assert markers == 2


def test_overlay_no_tools_skips_tool_marker() -> None:
    cached_messages, cached_tools = apply_prompt_caching(
        build_messages(_multi_turn_context()), []
    )
    assert cached_tools == []
    # The messages-prefix marker still applies.
    assert cached_messages[0]["content"][-1]["cache_control"] == _EPHEMERAL


def test_overlay_single_message_skips_messages_marker() -> None:
    single = [Message(role="user", blocks=[TextBlock(text="only turn")])]
    cached_messages, cached_tools = apply_prompt_caching(
        build_messages(single), build_tools(_tools())
    )
    # The sole message is the rolling tail — never cache it.
    assert "cache_control" not in cached_messages[0]["content"][-1]
    # The tools marker is still added.
    assert cached_tools[-1]["cache_control"] == _EPHEMERAL


def test_overlay_empty_first_content_skips_messages_marker() -> None:
    # A tool-result-only first message maps to a non-empty content list, so to
    # exercise the empty-content guard we mark directly on an empty content list.
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": []},
        {"role": "assistant", "content": [{"type": "text", "text": "x"}]},
    ]
    cached_messages, _ = apply_prompt_caching(messages, [])
    assert cached_messages[0]["content"] == []


def test_overlay_does_not_mutate_inputs() -> None:
    messages = build_messages(_multi_turn_context())
    tools = build_tools(_tools())
    apply_prompt_caching(messages, tools)

    # The originals stay byte-identical (the overlay copies what it marks).
    assert messages == build_messages(_multi_turn_context())
    assert tools == build_tools(_tools())


def test_overlay_off_path_byte_identical_via_build_functions() -> None:
    # The "off" path is simply not calling the overlay: build_* output is the
    # pre-caching request and must carry no cache_control.
    messages = build_messages(_multi_turn_context())
    tools = build_tools(_tools())
    for tool in tools:
        assert "cache_control" not in tool
    for message in messages:
        for block in message["content"]:
            assert "cache_control" not in block


# --- AnthropicModel.stream_turn (the toggle, adapter integration) ------------


async def _aiter(events: list[Any]) -> AsyncIterator[Any]:
    for event in events:
        yield event


class _Messages:
    def __init__(self, owner: _StubClient) -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> Any:
        self._owner.calls.append(kwargs)
        ns = SimpleNamespace
        return _aiter(
            [
                ns(
                    type="message_start",
                    message=ns(usage=ns(input_tokens=10, cache_read_input_tokens=4)),
                ),
                ns(type="content_block_start", index=0, content_block=ns(type="text")),
                ns(
                    type="content_block_delta",
                    index=0,
                    delta=ns(type="text_delta", text="hi"),
                ),
                ns(type="content_block_stop", index=0),
                ns(
                    type="message_delta",
                    delta=ns(stop_reason="end_turn"),
                    usage=ns(output_tokens=2),
                ),
                ns(type="message_stop"),
            ]
        )


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.messages = _Messages(self)


def _request() -> ModelRequest:
    return ModelRequest(context=_multi_turn_context(), tools=_tools())


async def _drive(model: AnthropicModel) -> None:
    async for _ in model.stream_turn(_request()):
        pass


@pytest.mark.anyio
async def test_adapter_caching_on_marks_stable_prefix() -> None:
    client = _StubClient()
    model = AnthropicModel(
        AnthropicConfig(model="claude-stub", client=client, prompt_caching=True)
    )
    await _drive(model)

    kwargs = client.calls[0]
    assert kwargs["tools"][-1]["cache_control"] == _EPHEMERAL
    assert kwargs["messages"][0]["content"][-1]["cache_control"] == _EPHEMERAL
    # Never the rolling tail.
    for block in kwargs["messages"][-1]["content"]:
        assert "cache_control" not in block


@pytest.mark.anyio
async def test_adapter_caching_off_is_byte_identical_to_today() -> None:
    client = _StubClient()
    model = AnthropicModel(
        AnthropicConfig(model="claude-stub", client=client, prompt_caching=False)
    )
    await _drive(model)

    kwargs = client.calls[0]
    assert kwargs["messages"] == build_messages(_multi_turn_context())
    assert kwargs["tools"] == build_tools(_tools())


@pytest.mark.anyio
async def test_adapter_default_enables_caching() -> None:
    client = _StubClient()
    model = AnthropicModel(AnthropicConfig(model="claude-stub", client=client))
    await _drive(model)

    kwargs = client.calls[0]
    assert kwargs["tools"][-1]["cache_control"] == _EPHEMERAL


@pytest.mark.anyio
async def test_adapter_caching_on_without_tools_still_runs() -> None:
    client = _StubClient()
    model = AnthropicModel(
        AnthropicConfig(model="claude-stub", client=client, prompt_caching=True)
    )
    request = ModelRequest(
        context=[
            Message(role="user", blocks=[TextBlock(text="first")]),
            Message(
                role="user",
                blocks=[
                    ToolResultBlock(
                        call_id="c1", outcome="success", outputs=[TextBlock(text="x")]
                    )
                ],
            ),
        ],
        tools=[],
    )
    async for _ in model.stream_turn(request):
        pass

    kwargs = client.calls[0]
    # No tools key was sent (empty tools list), and the first message is marked.
    assert "tools" not in kwargs
    assert kwargs["messages"][0]["content"][-1]["cache_control"] == _EPHEMERAL
