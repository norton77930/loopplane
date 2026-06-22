"""Unit 020 US1: OpenAI request mapping and stream decoding."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from loopplane.adapters.openai.mapping import (
    OpenAIStreamDecoder,
    UnsupportedContentError,
    build_messages,
    build_tools,
)
from loopplane.model import (
    Message,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
    TurnEnd,
)
from loopplane.model.content import (
    DocumentBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)


def test_build_messages_tool_result_is_tool_role() -> None:
    context = [
        Message(
            role="user",
            blocks=[
                ToolResultBlock(
                    call_id="c1", outcome="success", outputs=[TextBlock(text="pong")]
                )
            ],
        )
    ]
    assert build_messages(context) == [
        {"role": "tool", "tool_call_id": "c1", "content": "pong"}
    ]


def test_build_messages_assistant_tool_call() -> None:
    context = [
        Message(
            role="assistant",
            blocks=[
                TextBlock(text="ok"),
                ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "x"}),
            ],
        )
    ]
    message = build_messages(context)[0]
    assert message["role"] == "assistant"
    assert message["content"] == "ok"
    call = message["tool_calls"][0]
    assert call["function"]["name"] == "echo"
    assert json.loads(call["function"]["arguments"]) == {"text": "x"}


def test_build_messages_rejects_document_blocks_public_safe() -> None:
    payload = "JVBERi0xLjcKJSVFT0Y="
    private_name = "".join(["C", ":\\", "private\\", "sec", "ret-report.pdf"])
    document = DocumentBlock.model_construct(
        kind="document",
        media=payload,
        format="application/pdf",
        name=private_name,
    )
    context = [
        Message(
            role="user",
            blocks=[TextBlock(text="read"), document],
        )
    ]

    with pytest.raises(UnsupportedContentError) as excinfo:
        build_messages(context)

    message = str(excinfo.value)
    assert "document input is not supported" in message
    assert payload not in message
    assert private_name not in message
    assert ("sec" + "ret") not in message.lower()
    assert ("pass" + "word") not in message.lower()
    assert ("tok" + "en") not in message.lower()


def test_build_messages_rejects_document_inside_tool_result_message() -> None:
    document = DocumentBlock.model_construct(
        kind="document",
        media="JVBERi0xLjcKJSVFT0Y=",
        format="application/pdf",
        name="report.pdf",
    )

    with pytest.raises(UnsupportedContentError):
        build_messages([Message(role="user", blocks=[document])])


def test_build_tools_maps_descriptor() -> None:
    tool = ToolDescriptor(name="echo", description="d", input_schema={"type": "object"})
    assert build_tools([tool]) == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "d",
                "parameters": {"type": "object"},
            },
        }
    ]


def test_decoder_text_and_usage() -> None:
    ns = SimpleNamespace
    decoder = OpenAIStreamDecoder()
    out: list[object] = []
    out += decoder.feed(
        ns(
            usage=None,
            choices=[
                ns(delta=ns(content="Hello", tool_calls=None), finish_reason=None)
            ],
        )
    )
    out += decoder.feed(
        ns(
            usage=None,
            choices=[
                ns(delta=ns(content=" world", tool_calls=None), finish_reason="stop")
            ],
        )
    )
    out += decoder.feed(
        ns(
            usage=ns(
                prompt_tokens=9,
                completion_tokens=4,
                prompt_tokens_details=ns(cached_tokens=3),
                completion_tokens_details=ns(reasoning_tokens=2),
            ),
            choices=[],
        )
    )
    out += decoder.finish()

    assert [type(item) for item in out] == [TextIncrement, TextIncrement, TurnEnd]
    end = out[-1]
    assert isinstance(end, TurnEnd)
    assert end.stop_reason == "stop"
    assert end.usage.input_tokens == 9
    assert end.usage.output_tokens == 4
    assert end.usage.cached_tokens == 3
    assert end.usage.reasoning_tokens == 2


def test_decoder_reports_cached_tokens_from_usage_chunk() -> None:
    # Spec 040: OpenAI prompt caching is automatic/server-side — the adapter
    # sends no cache parameter — and the cached_tokens it reports already flows
    # into TokenUsage.cached_tokens via the existing stream decoder. (OpenRouter
    # and Ollama inherit this through the reused OpenAIModel + mapping, unit 035.)
    ns = SimpleNamespace
    decoder = OpenAIStreamDecoder()
    decoder.feed(
        ns(
            usage=ns(
                prompt_tokens=100,
                completion_tokens=10,
                prompt_tokens_details=ns(cached_tokens=80),
                completion_tokens_details=None,
            ),
            choices=[ns(delta=ns(content=None, tool_calls=None), finish_reason="stop")],
        )
    )
    end = decoder.finish()[-1]
    assert isinstance(end, TurnEnd)
    assert end.usage.cached_tokens == 80


def test_decoder_tool_call_accumulates_arguments() -> None:
    ns = SimpleNamespace
    decoder = OpenAIStreamDecoder()
    decoder.feed(
        ns(
            usage=None,
            choices=[
                ns(
                    delta=ns(
                        content=None,
                        tool_calls=[
                            ns(
                                index=0,
                                id="call_1",
                                function=ns(name="echo", arguments='{"text":'),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ],
        )
    )
    decoder.feed(
        ns(
            usage=None,
            choices=[
                ns(
                    delta=ns(
                        content=None,
                        tool_calls=[
                            ns(
                                index=0,
                                id=None,
                                function=ns(name=None, arguments='"hi"}'),
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
        )
    )
    out = decoder.finish()
    assert [type(item) for item in out] == [ToolCallRequest, TurnEnd]
    call = out[0]
    assert isinstance(call, ToolCallRequest)
    assert call.call_id == "call_1"
    assert call.tool_name == "echo"
    assert call.input == {"text": "hi"}
