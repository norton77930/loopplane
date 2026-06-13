"""US3: drive and observe a run as a host — ordered events, cancellation, the
approval round-trip, and consumer-failure isolation (spec US3; FR-004/007/014).
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from loopplane.events.envelope import ApprovalRequestedPayload
from loopplane.host import (
    ApprovalDecision,
    ApprovalPolicy,
    LoopPlaneHost,
    RuntimeConfig,
)
from loopplane.model import ScriptedModel, ScriptedTurn, TextIncrement

from .conftest import (
    ECHO_TOOL,
    EventCollector,
    multi_text_model,
    text_model,
    tool_then_text_model,
)

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


async def test_failing_approval_handler_denies_without_crashing(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(
            model=tool_then_text_model(),
            tools=(ECHO_TOOL,),
            approval=ApprovalPolicy(ask=frozenset({"echo"})),
        ),
        working_scope=tmp_path,
    )

    async def boom(payload: ApprovalRequestedPayload) -> ApprovalDecision:
        raise RuntimeError("handler bug")

    sink = EventCollector()
    outcome = await host.run("echo please", sink, on_approval=boom)

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "failure"  # denied, not executed
    assert outcome.termination_reason == "natural-completion"  # run survived


async def test_concurrent_runs_on_one_host_are_rejected(tmp_path: Path) -> None:
    host = LoopPlaneHost(
        RuntimeConfig(model=multi_text_model("a", "b")), working_scope=tmp_path
    )
    started = anyio.Event()
    release = anyio.Event()

    async def slow_sink(event: object) -> None:
        if event.type == "user-input":  # type: ignore[attr-defined]
            started.set()
            await release.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(host.run, "one", slow_sink)
        await started.wait()
        with pytest.raises(RuntimeError):
            await host.run("two", EventCollector())
        release.set()


async def test_cancel_resolves_a_pending_approval_without_hanging(
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

    class CancelOnApproval(EventCollector):
        session: object | None = None

        async def __call__(self, event: object) -> None:
            await super().__call__(event)  # type: ignore[arg-type]
            if event.type == "approval-requested" and self.session is not None:  # type: ignore[attr-defined]
                self.session.cancel()  # type: ignore[attr-defined]

    sink = CancelOnApproval()
    with anyio.fail_after(5):
        async with host.session(sink) as session:
            sink.session = session
            await session.submit("echo please")
            outcome = session.outcome()

    assert outcome.termination_reason == "cancelled"


async def test_observability_fault_does_not_crash_the_run(tmp_path: Path) -> None:
    host = LoopPlaneHost(RuntimeConfig(model=text_model("hi")), working_scope=tmp_path)

    async def failing_overlay(event: object) -> None:
        raise RuntimeError("exporter down")

    # Attach a raising telemetry overlay directly (as assembly does when
    # observability is enabled); a fault in it must not affect the run.
    host._assembled.sink.set_observability(failing_overlay)
    sink = EventCollector()

    outcome = await host.run("hello", sink)

    assert outcome.termination_reason == "natural-completion"
    assert sink.types[-1] == "run-terminated"  # host still got the full stream


async def test_session_outcome_is_a_stable_snapshot(tmp_path: Path) -> None:
    model = ScriptedModel(
        script=[
            ScriptedTurn(increments=[TextIncrement(text=f"c{i}") for i in range(20)]),
            ScriptedTurn(increments=[TextIncrement(text="later")]),
        ],
        context_capacity=100_000,
    )
    host = LoopPlaneHost(RuntimeConfig(model=model), working_scope=tmp_path)

    class Canceller(EventCollector):
        session: object | None = None

        async def __call__(self, event: object) -> None:
            await super().__call__(event)  # type: ignore[arg-type]
            if event.type == "assistant-output-increment" and self.session is not None:  # type: ignore[attr-defined]
                self.session.cancel()  # type: ignore[attr-defined]

    sink = Canceller()
    async with host.session(sink) as session:
        sink.session = session
        await session.submit("go")
        captured = session.outcome()
    assert captured.termination_reason == "cancelled"

    # A later natural run on the same host rebinds the shared sink; the retained
    # session's snapshot must not change.
    await host.run("again", EventCollector())
    assert session.outcome().termination_reason == "cancelled"
