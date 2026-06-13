"""Contract tests for the model boundary (contracts/model-boundary.md).

Asserts that the scripted substitute yields normalized increments in order,
reports usage on turn end, answers the context-capacity query, signals
context overflow distinctly, and surfaces other failures to the caller.
"""

from __future__ import annotations

import pytest

from loopplane.model.boundary import (
    ContextOverflowError,
    GenerationLimits,
    Message,
    ModelBoundary,
    ModelRequest,
    ReasoningIncrement,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
    TurnEnd,
)
from loopplane.model.content import TextBlock
from loopplane.model.scripted import (
    ScriptedFailure,
    ScriptedModel,
    ScriptedOverflow,
    ScriptedTurn,
)

pytestmark = pytest.mark.anyio


def _request() -> ModelRequest:
    return ModelRequest(
        context=[Message(role="user", blocks=[TextBlock(text="do the thing")])],
        tools=[],
        limits=GenerationLimits(),
    )


async def _collect(model: ScriptedModel) -> list[object]:
    return [increment async for increment in model.stream_turn(_request())]


async def test_scripted_turn_yields_normalized_increments_in_order() -> None:
    usage = TokenUsage(
        input_tokens=7, output_tokens=3, cached_tokens=0, reasoning_tokens=1
    )
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    ReasoningIncrement(text="let me think"),
                    TextIncrement(text="working on it"),
                    ToolCallRequest(
                        call_id="call-1", tool_name="echo", input={"text": "hi"}
                    ),
                ],
                stop_reason="tool-use",
                usage=usage,
            )
        ],
        context_capacity=8000,
    )

    increments = await _collect(model)

    assert [type(i) for i in increments] == [
        ReasoningIncrement,
        TextIncrement,
        ToolCallRequest,
        TurnEnd,
    ]
    reasoning, text, call, end = increments
    assert (
        isinstance(reasoning, ReasoningIncrement) and reasoning.text == "let me think"
    )
    assert isinstance(text, TextIncrement) and text.text == "working on it"
    assert isinstance(call, ToolCallRequest)
    assert (call.call_id, call.tool_name, call.input) == (
        "call-1",
        "echo",
        {"text": "hi"},
    )
    assert isinstance(end, TurnEnd)


async def test_turn_end_carries_stop_reason_and_full_usage() -> None:
    usage = TokenUsage(
        input_tokens=11, output_tokens=4, cached_tokens=2, reasoning_tokens=3
    )
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="ok")], usage=usage)],
        context_capacity=8000,
    )

    *_, end = await _collect(model)

    assert isinstance(end, TurnEnd)
    assert end.stop_reason == "end-turn"
    assert end.usage.input_tokens == 11
    assert end.usage.output_tokens == 4
    assert end.usage.cached_tokens == 2
    assert end.usage.reasoning_tokens == 3


async def test_consecutive_calls_consume_the_script_in_order() -> None:
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text="first")]),
            ScriptedTurn(increments=[TextIncrement(text="second")]),
        ],
        context_capacity=8000,
    )

    first = await _collect(model)
    second = await _collect(model)

    assert isinstance(first[0], TextIncrement) and first[0].text == "first"
    assert isinstance(second[0], TextIncrement) and second[0].text == "second"


def test_context_capacity_answers_the_configured_value() -> None:
    model = ScriptedModel(script=[], context_capacity=1234)
    assert model.context_capacity() == 1234


async def test_context_overflow_is_a_distinct_signal() -> None:
    model = ScriptedModel(script=[ScriptedOverflow()], context_capacity=10)

    with pytest.raises(ContextOverflowError):
        await _collect(model)


async def test_other_failures_surface_to_the_caller() -> None:
    boom = RuntimeError("scripted model failure")
    model = ScriptedModel(script=[ScriptedFailure(error=boom)], context_capacity=8000)

    with pytest.raises(RuntimeError) as excinfo:
        await _collect(model)
    assert excinfo.value is boom


def test_overflow_error_is_not_a_generic_failure_alias() -> None:
    assert not issubclass(ContextOverflowError, RuntimeError)


def test_scripted_substitute_satisfies_the_boundary_protocol() -> None:
    model = ScriptedModel(script=[], context_capacity=1)
    assert isinstance(model, ModelBoundary)
