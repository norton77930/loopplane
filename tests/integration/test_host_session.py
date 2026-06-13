"""US3: drive and observe a run as a host — ordered events, cancellation, the
approval round-trip, and consumer-failure isolation (spec US3; FR-004/007/014).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.events.envelope import ApprovalRequestedPayload
from loopplane.host import (
    ApprovalDecision,
    ApprovalPolicy,
    LoopPlaneHost,
    RuntimeConfig,
)
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

from .conftest import ECHO_TOOL, EventCollector, text_model, tool_then_text_model

pytestmark = pytest.mark.anyio


def _streaming_model(chunks: int = 20) -> ScriptedModel:
    return ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[TextIncrement(text=f"chunk-{i}") for i in range(chunks)]
            )
        ],
        context_capacity=100_000,
    )


async def test_cancel_mid_run_ends_cancelled(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(model=_streaming_model()), working_scope=tmp_path
    )

    class Canceller(EventCollector):
        session: object | None = None

        async def __call__(self, event: object) -> None:
            await super().__call__(event)  # type: ignore[arg-type]
            if event.type == "assistant-output-increment" and self.session is not None:  # type: ignore[attr-defined]
                self.session.cancel()  # type: ignore[attr-defined]

    sink = Canceller()
    async with host.session(sink) as session:
        sink.session = session
        await session.submit("hi")
        outcome = session.outcome()

    assert outcome.termination_reason == "cancelled"
    assert sink.types[-1] == "run-terminated"


async def test_cancel_before_first_response_leaves_no_orphan(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(model=_streaming_model()), working_scope=tmp_path
    )

    class CancelOnUserInput(EventCollector):
        session: object | None = None

        async def __call__(self, event: object) -> None:
            await super().__call__(event)  # type: ignore[arg-type]
            if event.type == "user-input" and self.session is not None:  # type: ignore[attr-defined]
                self.session.cancel()  # type: ignore[attr-defined]

    sink = CancelOnUserInput()
    async with host.session(sink) as session:
        sink.session = session
        await session.submit("hi")
        outcome = session.outcome()

    assert outcome.termination_reason == "cancelled"
    assert outcome.history == ()


async def test_approval_ask_round_trips_to_host_handler(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=tool_then_text_model(),
            tools=(ECHO_TOOL,),
            approval=ApprovalPolicy(ask=frozenset({"echo"})),
        ),
        working_scope=tmp_path,
    )
    asked: list[str] = []

    async def on_approval(payload: ApprovalRequestedPayload) -> ApprovalDecision:
        asked.append(payload.tool_name)
        return ApprovalDecision(allow=True)

    sink = EventCollector()
    outcome = await host.run("echo please", sink, on_approval=on_approval)

    assert asked == ["echo"]
    assert "approval-requested" in sink.types
    assert "approval-resolved" in sink.types
    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "success"
    assert outcome.termination_reason == "natural-completion"


async def test_denied_approval_blocks_the_tool_but_run_continues(
    tmp_path: Path,
) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=tool_then_text_model(),
            tools=(ECHO_TOOL,),
            approval=ApprovalPolicy(ask=frozenset({"echo"})),
        ),
        working_scope=tmp_path,
    )

    async def deny(payload: ApprovalRequestedPayload) -> ApprovalDecision:
        return ApprovalDecision(allow=False, reason="not allowed")

    sink = EventCollector()
    outcome = await host.run("echo please", sink, on_approval=deny)

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "failure"
    assert outcome.termination_reason == "natural-completion"


async def test_consumer_failure_is_isolated(tmp_path: Path) -> None:
    host = LoopPlaneHost(RuntimeConfig(model=text_model("hi")), working_scope=tmp_path)

    async def raising(event: object) -> None:
        raise RuntimeError("boom")

    outcome = await host.run("hello", raising)

    assert outcome.termination_reason == "natural-completion"
    assert outcome.consumer_failures  # isolated and recorded, run not corrupted
