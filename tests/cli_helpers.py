"""Deterministic, public-safe helpers for the CLI host suites (feature 017,
extended for 079).

Includes an importable model builder (`tests.cli_helpers:build_fake_model`) for the
`LOOPPLANE_MODEL` provider-selection seam.
"""

from __future__ import annotations

import signal
from collections.abc import AsyncIterator
from pathlib import Path

import anyio

from loopplane.context import RunContext
from loopplane.events.envelope import Question
from loopplane.host import (
    ApprovalPolicy,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
    ToolSpec,
)
from loopplane.model import (
    OutputBlock,
    ScriptedFailure,
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
    ToolDescriptor,
    TurnEnd,
)

_NO_INPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def scripted_host(*texts: str, store: Path | None = None) -> LoopPlaneHost:
    """A host over a scripted model with one text turn per argument."""
    model = ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=t)]) for t in texts],
        context_capacity=100_000,
    )
    storage = StorageConfig(root=store) if store is not None else None
    return LoopPlaneHost(RuntimeConfig(model=model, storage=storage))


def build_fake_model() -> ScriptedModel:
    """A model builder the provider seam imports (LOOPPLANE_MODEL=module:function)."""
    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text="from a real builder")])],
        context_capacity=100_000,
    )


# --- 079 helpers: approvals, questions, and interruption ---------------------

GATED_DESCRIPTOR = ToolDescriptor(
    name="gated",
    description="A tool that requires permission.",
    input_schema=_NO_INPUT_SCHEMA,
)


async def gated_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text="the gated tool ran")]


GATED_TOOL = ToolSpec(descriptor=GATED_DESCRIPTOR, handler=gated_handler)

ASKING_DESCRIPTOR = ToolDescriptor(
    name="asking",
    description="A tool that asks the operator a question.",
    input_schema=_NO_INPUT_SCHEMA,
)


async def asking_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    broker = context.interactions
    if broker is None:
        return [TextBlock(text="no user attached")]
    answers = await broker.ask_question(
        [Question(text="which colour?", options=["teal", "amber"])]
    )
    if answers is None:
        return [TextBlock(text="unanswered")]
    return [TextBlock(text=f"you said {answers[0]}")]


ASKING_TOOL = ToolSpec(descriptor=ASKING_DESCRIPTOR, handler=asking_handler)


def _tool_turn(tool_name: str, call_id: str) -> ScriptedTurn:
    return ScriptedTurn(
        increments=[ToolCallRequest(call_id=call_id, tool_name=tool_name, input={})],
        stop_reason="tool-use",
    )


def gated_host(*, calls: int = 1, store: Path | None = None) -> LoopPlaneHost:
    """A host whose model asks to run a permission-gated tool ``calls`` times.

    Each call is followed by a closing text turn, so one submitted line drives
    exactly one approval round-trip.
    """

    script: list[ScriptedTurn] = []
    for index in range(calls):
        script.append(_tool_turn("gated", f"c{index}"))
        script.append(ScriptedTurn(increments=[TextIncrement(text="done")]))
    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(script=script, context_capacity=100_000),
            tools=(GATED_TOOL,),
            approval=ApprovalPolicy(ask=frozenset({"gated"})),
            storage=StorageConfig(root=store) if store is not None else None,
        )
    )


def asking_host() -> LoopPlaneHost:
    """A host whose model calls a tool that asks the operator a question."""

    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[
                    _tool_turn("asking", "q1"),
                    ScriptedTurn(increments=[TextIncrement(text="thanks")]),
                ],
                context_capacity=100_000,
            ),
            tools=(ASKING_TOOL,),
        )
    )


def interrupting_host(*, then: str = "still here") -> LoopPlaneHost:
    """A host whose first turn raises ``KeyboardInterrupt`` mid-run, and whose
    next turn answers normally — the shape US3 needs."""

    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel(
                script=[
                    ScriptedFailure(error=KeyboardInterrupt()),
                    ScriptedTurn(increments=[TextIncrement(text=then)]),
                ],
                context_capacity=100_000,
            )
        )
    )


class _SigintModel:
    """A model that presses Ctrl-C for the operator, mid-turn.

    This raises a REAL SIGINT, so the test exercises the path a terminal
    actually takes — the signal handler the conversation installs — rather than
    a `KeyboardInterrupt` injected into the turn's own frames, which is a
    different path and the one that made 079's first interrupt design look
    correct when it was not.
    """

    def __init__(self, *, then: str) -> None:
        self._fired = False
        self._then = then

    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(self, request: object) -> AsyncIterator[object]:
        if not self._fired:
            self._fired = True
            signal.raise_signal(signal.SIGINT)
            # Give the handler (and the cancellation it requests) a chance to
            # be observed before this turn produces anything.
            await anyio.sleep(0)
        yield TextIncrement(text=self._then)
        yield TurnEnd(stop_reason="end-turn", usage=TokenUsage())


def sigint_host(*, then: str = "still here") -> LoopPlaneHost:
    """A host whose first turn is interrupted by a real SIGINT."""

    return LoopPlaneHost(RuntimeConfig(model=_SigintModel(then=then)))
