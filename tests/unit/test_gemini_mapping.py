"""Unit 037: native Gemini request mapping and stream decoding.

Offline + duck-typed: the decoder consumes Gemini-shaped ``SimpleNamespace`` chunks
(``candidates[0].content.parts`` + ``usage_metadata``), so no SDK and no network are
needed. Mirrors ``test_openai_mapping.py`` / ``test_anthropic_mapping.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

from loopplane.adapters.gemini.mapping import (
    SKIP_THOUGHT_SIGNATURE,
    GeminiStreamDecoder,
    build_contents,
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
from loopplane.model.content import (
    DocumentBlock,
    ImageBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)


def _chunk(parts: list[object], *, finish: str | None = None, usage: object = None):
    ns = SimpleNamespace
    return ns(
        candidates=[ns(content=ns(parts=parts), finish_reason=finish)],
        usage_metadata=usage,
    )


def _function_call_part(
    *,
    name: str = "echo",
    args: dict[str, object] | None = None,
    signature: object = "gemini-signature-1",
):
    ns = SimpleNamespace
    return ns(
        text=None,
        thought=None,
        function_call=ns(name=name, args=args or {"text": "hi"}),
        thought_signature=signature,
    )


# --- request mapping --------------------------------------------------------


def test_build_contents_maps_text_roles() -> None:
    context = [
        Message(role="user", blocks=[TextBlock(text="hi")]),
        Message(role="assistant", blocks=[TextBlock(text="hello")]),
    ]
    contents = build_contents(context)
    assert contents[0] == {"role": "user", "parts": [{"text": "hi"}]}
    assert contents[1] == {"role": "model", "parts": [{"text": "hello"}]}


def test_build_contents_maps_image_to_inline_data() -> None:
    context = [
        Message(role="user", blocks=[ImageBlock(media="QUJD", format="image/png")])
    ]
    part = build_contents(context)[0]["parts"][0]
    assert part == {"inline_data": {"mime_type": "image/png", "data": "QUJD"}}


def test_build_contents_maps_document_to_inline_data() -> None:
    context = [
        Message(
            role="user",
            blocks=[
                DocumentBlock(
                    media="JVBERi0xLjcKJSVFT0Y=",
                    format="application/pdf",
                    name="report.pdf",
                )
            ],
        )
    ]

    part = build_contents(context)[0]["parts"][0]

    assert part == {
        "inline_data": {
            "mime_type": "application/pdf",
            "data": "JVBERi0xLjcKJSVFT0Y=",
        }
    }


def test_build_contents_tool_call_carries_skip_sentinel_not_in_args() -> None:
    # A prior assistant tool call -> a model-role function_call part with the
    # official skip sentinel on the part (NOT in args; the gateway validates args).
    context = [
        Message(
            role="assistant",
            blocks=[ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "x"})],
        )
    ]
    message = build_contents(context)[0]
    assert message["role"] == "model"
    part = message["parts"][0]
    assert part["function_call"] == {"name": "echo", "args": {"text": "x"}}
    assert part["thought_signature"] == SKIP_THOUGHT_SIGNATURE
    # The sentinel must never leak into the args the gateway validates.
    assert "thought_signature" not in part["function_call"]["args"]
    assert "skip_thought_signature_validator" not in str(part["function_call"]["args"])


def test_tool_call_shapes_carry_provider_signature_outside_input() -> None:
    request = ToolCallRequest(
        call_id="c1",
        tool_name="echo",
        input={"text": "x"},
        provider_signature="gemini-signature-1",
    )
    block = ToolCallBlock(
        call_id=request.call_id,
        tool_name=request.tool_name,
        input=request.input,
        provider_signature=request.provider_signature,
    )

    assert request.provider_signature == "gemini-signature-1"
    assert block.provider_signature == "gemini-signature-1"
    assert "provider_signature" not in block.input


def test_unsigned_tool_call_serialized_shape_is_unchanged() -> None:
    block = ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "x"})

    assert block.model_dump(mode="json") == {
        "kind": "tool-call",
        "call_id": "c1",
        "tool_name": "echo",
        "input": {"text": "x"},
    }


def test_build_contents_tool_call_replays_provider_signature_not_in_args() -> None:
    context = [
        Message(
            role="assistant",
            blocks=[
                ToolCallBlock(
                    call_id="c1",
                    tool_name="echo",
                    input={"text": "x"},
                    provider_signature="gemini-signature-1",
                )
            ],
        )
    ]

    part = build_contents(context)[0]["parts"][0]

    assert part["function_call"] == {"name": "echo", "args": {"text": "x"}}
    assert part["thought_signature"] == "gemini-signature-1"
    assert "provider_signature" not in part["function_call"]["args"]
    assert "thought_signature" not in part["function_call"]["args"]


def test_build_contents_tool_result_is_function_response_user_role() -> None:
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
    message = build_contents(context)[0]
    assert message["role"] == "user"
    response = message["parts"][0]["function_response"]
    assert response["name"] == "c1"
    assert "pong" in str(response["response"])


def test_build_tools_maps_descriptor_to_function_declarations() -> None:
    tool = ToolDescriptor(name="echo", description="d", input_schema={"type": "object"})
    assert build_tools([tool]) == [
        {
            "function_declarations": [
                {
                    "name": "echo",
                    "description": "d",
                    "parameters": {"type": "object"},
                }
            ]
        }
    ]


def test_build_tools_empty_is_empty() -> None:
    assert build_tools([]) == []


# --- stream decoding --------------------------------------------------------


def test_decoder_text_then_turn_end_with_usage() -> None:
    ns = SimpleNamespace
    decoder = GeminiStreamDecoder()
    out: list[object] = []
    out += decoder.feed(_chunk([ns(text="Hello", thought=None, function_call=None)]))
    out += decoder.feed(
        _chunk(
            [ns(text=" world", thought=None, function_call=None)],
            finish="STOP",
            usage=ns(
                prompt_token_count=9,
                candidates_token_count=4,
                cached_content_token_count=3,
                thoughts_token_count=2,
            ),
        )
    )
    out += decoder.finish()

    assert [type(item) for item in out] == [TextIncrement, TextIncrement, TurnEnd]
    end = out[-1]
    assert isinstance(end, TurnEnd)
    assert end.stop_reason == "STOP"
    assert end.usage.input_tokens == 9
    assert end.usage.output_tokens == 4
    assert end.usage.cached_tokens == 3
    assert end.usage.reasoning_tokens == 2


def test_decoder_thought_part_is_reasoning() -> None:
    ns = SimpleNamespace
    decoder = GeminiStreamDecoder()
    out = decoder.feed(_chunk([ns(text="hmm", thought=True, function_call=None)]))
    assert [type(item) for item in out] == [ReasoningIncrement]
    assert isinstance(out[0], ReasoningIncrement)
    assert out[0].text == "hmm"


def test_decoder_function_call_is_raw_tool_call() -> None:
    ns = SimpleNamespace
    decoder = GeminiStreamDecoder()
    decoder.feed(
        _chunk(
            [
                ns(
                    text=None,
                    thought=None,
                    function_call=ns(name="echo", args={"text": "hi"}),
                )
            ],
            finish="STOP",
        )
    )
    out = decoder.finish()
    assert [type(item) for item in out] == [ToolCallRequest, TurnEnd]
    call = out[0]
    assert isinstance(call, ToolCallRequest)
    assert call.tool_name == "echo"
    assert call.input == {"text": "hi"}
    # A synthesized, non-empty, stable id (Gemini function_call carries no id).
    assert call.call_id


def test_decoder_function_call_preserves_provider_signature() -> None:
    decoder = GeminiStreamDecoder()
    decoder.feed(_chunk([_function_call_part(signature="gemini-signature-1")]))

    call, end = decoder.finish()

    assert isinstance(call, ToolCallRequest)
    assert call.provider_signature == "gemini-signature-1"
    assert call.input == {"text": "hi"}
    assert "provider_signature" not in call.input
    assert isinstance(end, TurnEnd)


def test_decoder_multiple_function_calls_keep_independent_signatures() -> None:
    decoder = GeminiStreamDecoder()
    decoder.feed(
        _chunk(
            [
                _function_call_part(name="first", signature="gemini-signature-1"),
                _function_call_part(name="second", signature="gemini-signature-2"),
            ]
        )
    )

    first, second, end = decoder.finish()

    assert isinstance(first, ToolCallRequest)
    assert isinstance(second, ToolCallRequest)
    assert first.tool_name == "first"
    assert first.provider_signature == "gemini-signature-1"
    assert second.tool_name == "second"
    assert second.provider_signature == "gemini-signature-2"
    assert isinstance(end, TurnEnd)


def test_decoder_ignores_missing_empty_or_non_string_signatures() -> None:
    decoder = GeminiStreamDecoder()
    no_signature = _function_call_part(name="none", signature=None)
    empty_signature = _function_call_part(name="empty", signature="")
    numeric_signature = _function_call_part(name="numeric", signature=123)
    decoder.feed(_chunk([no_signature, empty_signature, numeric_signature]))

    first, second, third, end = decoder.finish()

    assert isinstance(first, ToolCallRequest)
    assert isinstance(second, ToolCallRequest)
    assert isinstance(third, ToolCallRequest)
    assert first.provider_signature is None
    assert second.provider_signature is None
    assert third.provider_signature is None
    assert isinstance(end, TurnEnd)
