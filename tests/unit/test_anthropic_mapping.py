"""Unit 020 US1: Anthropic request mapping and stream decoding."""

from __future__ import annotations

from types import SimpleNamespace

from loopplane.adapters.anthropic.mapping import (
    AnthropicStreamDecoder,
    build_messages,
    build_tools,
)
from loopplane.model import (
    Message,
    ReasoningIncrement,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
    TurnEnd,
)
from loopplane.model.content import TextBlock, ToolCallBlock, ToolResultBlock


def test_build_messages_maps_blocks() -> None:
    context = [
        Message(role="user", blocks=[TextBlock(text="hi")]),
        Message(
            role="assistant",
            blocks=[ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "x"})],
        ),
        Message(
            role="user",
            blocks=[
                ToolResultBlock(
                    call_id="c1", outcome="success", outputs=[TextBlock(text="x")]
                )
            ],
        ),
    ]
    messages = build_messages(context)
    assert messages[0] == {"role": "user", "content": [{"type": "text", "text": "hi"}]}
    assert messages[1]["content"][0]["type"] == "tool_use"
    result = messages[2]["content"][0]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "c1"


def test_build_tools_maps_descriptor() -> None:
    tool = ToolDescriptor(name="echo", description="d", input_schema={"type": "object"})
    assert build_tools([tool]) == [
        {"name": "echo", "description": "d", "input_schema": {"type": "object"}}
    ]


def test_decoder_text_then_turn_end() -> None:
    ns = SimpleNamespace
    decoder = AnthropicStreamDecoder()
    out: list[object] = []
    out += decoder.feed(
        ns(
            type="message_start",
            message=ns(usage=ns(input_tokens=10, cache_read_input_tokens=2)),
        )
    )
    out += decoder.feed(
        ns(type="content_block_start", index=0, content_block=ns(type="text"))
    )
    out += decoder.feed(
        ns(
            type="content_block_delta",
            index=0,
            delta=ns(type="text_delta", text="Hello"),
        )
    )
    out += decoder.feed(ns(type="content_block_stop", index=0))
    out += decoder.feed(
        ns(
            type="message_delta",
            delta=ns(stop_reason="end_turn"),
            usage=ns(output_tokens=5),
        )
    )
    out += decoder.feed(ns(type="message_stop"))

    assert [type(item) for item in out] == [TextIncrement, TurnEnd]
    assert isinstance(out[0], TextIncrement) and out[0].text == "Hello"
    end = out[1]
    assert isinstance(end, TurnEnd)
    assert end.usage.input_tokens == 10
    assert end.usage.output_tokens == 5
    assert end.usage.cached_tokens == 2
    assert decoder.ended


def test_decoder_reasoning_and_tool_call() -> None:
    ns = SimpleNamespace
    decoder = AnthropicStreamDecoder()
    decoder.feed(ns(type="message_start", message=ns(usage=ns(input_tokens=1))))
    decoder.feed(
        ns(type="content_block_start", index=0, content_block=ns(type="thinking"))
    )
    reasoning = decoder.feed(
        ns(
            type="content_block_delta",
            index=0,
            delta=ns(type="thinking_delta", thinking="hmm"),
        )
    )
    assert [type(item) for item in reasoning] == [ReasoningIncrement]
    decoder.feed(ns(type="content_block_stop", index=0))
    decoder.feed(
        ns(
            type="content_block_start",
            index=1,
            content_block=ns(type="tool_use", id="t1", name="echo"),
        )
    )
    decoder.feed(
        ns(
            type="content_block_delta",
            index=1,
            delta=ns(type="input_json_delta", partial_json='{"text":'),
        )
    )
    decoder.feed(
        ns(
            type="content_block_delta",
            index=1,
            delta=ns(type="input_json_delta", partial_json='"hi"}'),
        )
    )
    calls = decoder.feed(ns(type="content_block_stop", index=1))
    assert len(calls) == 1
    call = calls[0]
    assert isinstance(call, ToolCallRequest)
    assert call.call_id == "t1"
    assert call.tool_name == "echo"
    assert call.input == {"text": "hi"}
