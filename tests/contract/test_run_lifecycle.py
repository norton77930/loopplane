"""Contract tests for the run lifecycle (contracts/run-lifecycle.md).

Asserts the Controller operations (create, attach, drive, detach, resume,
terminate, list), single-driving-consumer attach replacement, mid-turn
submit-input rejection, disconnect semantics, replay brackets with `replay`
flags including past user inputs, and increment batching that never reorders
(FR-010–FR-015).
"""

from __future__ import annotations

import math
import os
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from loopplane.approval import HumanApproval
from loopplane.artifacts import ArtifactStore
from loopplane.artifacts.store import ArtifactSessionDeletion
from loopplane.checkpoint import FileCheckpointStore
from loopplane.checkpoint.records import SessionMetaPayload, SessionMetaRecord
from loopplane.controller.controller import RuntimeController
from loopplane.controller.dispatcher import (
    BatchingSink,
    ConsumerRequest,
    Dispatcher,
    SubmitInput,
)
from loopplane.events import (
    AssistantOutputIncrementEvent,
    AssistantOutputIncrementPayload,
    RuntimeEvent,
    TurnCompletedEvent,
    TurnCompletedPayload,
)
from loopplane.gateway import ToolGateway
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    TokenUsage,
    ToolCallRequest,
)
from tests.integration.conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


def _controller(
    script: list[ScriptEntry],
    sink: EventCollector,
    tmp_path: Path,
    *,
    durable: bool = True,
    decide: HumanApproval | None = None,
) -> RuntimeController:
    gateway = ToolGateway(decide=decide)
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    return RuntimeController(
        model=ScriptedModel(script=script, context_capacity=100_000),
        gateway=gateway,
        event_sink=sink,
        checkpoint_store=FileCheckpointStore(tmp_path / "sessions")
        if durable
        else None,
    )


def _tool_script() -> list[ScriptEntry]:
    return [
        ScriptedTurn(
            increments=[
                TextIncrement(text="using the tool"),
                ToolCallRequest(call_id="c1", tool_name="echo", input={"text": "hi"}),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


# --- controller operations -----------------------------------------------------


async def test_artifact_rollback_failure_retains_authority_for_host_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A proven pre-effect failure cannot discard detached artifact authority."""

    sink = EventCollector()
    store = ArtifactStore(tmp_path / "sessions")
    checkpoint = FileCheckpointStore(tmp_path / "sessions")
    controller = RuntimeController(
        model=ScriptedModel(script=[], context_capacity=100_000),
        gateway=ToolGateway(),
        event_sink=sink,
        checkpoint_store=checkpoint,
        artifact_store=store,
    )
    session_id = controller.create_session(working_scope=tmp_path, principal_id="owner")
    now = datetime.now(UTC)
    await checkpoint.append(
        SessionMetaRecord(
            session_id=session_id,
            sequence=1,
            recorded_at=now,
            payload=SessionMetaPayload(
                created_at=now,
                label="rollback retry",
                principal_id="owner",
            ),
        )
    )
    await store.offload(
        session_id=session_id,
        call_id="c1",
        outputs=[TextBlock(text="owned artifact")],
    )

    def fail_checkpoint_delete(_session_id: str) -> None:
        raise OSError("checkpoint delete rejected")

    monkeypatch.setattr(checkpoint, "delete_session", fail_checkpoint_delete)
    original_rollback = store.rollback_session_deletion

    def fail_rollback(deletion: ArtifactSessionDeletion) -> None:
        assert deletion.has_retained_authority is True
        raise RuntimeError("artifact deletion rollback blocked")

    monkeypatch.setattr(store, "rollback_session_deletion", fail_rollback)
    with pytest.raises(RuntimeError, match="rollback blocked"):
        controller.delete_session(session_id)

    assert len(controller._pending_artifact_deletions) == 1
    monkeypatch.setattr(store, "rollback_session_deletion", original_rollback)
    controller.retry_pending_artifact_deletions()
    assert controller._pending_artifact_deletions == []
    assert (tmp_path / "sessions" / session_id / "artifacts").is_dir()


async def test_delete_retries_failed_prepare_cleanup_before_detaching_next_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retained prepare handle blocks the next direct delete until released."""

    import loopplane.artifacts.store as artifact_store_module

    sink = EventCollector()
    store = ArtifactStore(tmp_path / "sessions")
    controller = RuntimeController(
        model=ScriptedModel(script=[], context_capacity=100_000),
        gateway=ToolGateway(),
        event_sink=sink,
        checkpoint_store=FileCheckpointStore(tmp_path / "sessions"),
        artifact_store=store,
    )
    first = controller.create_session(working_scope=tmp_path, principal_id="owner")
    second = controller.create_session(working_scope=tmp_path, principal_id="owner")
    for session_id in (first, second):
        await store.offload(
            session_id=session_id,
            call_id="c1",
            outputs=[TextBlock(text="owned artifact")],
        )
    original_validate = store._validate_staged_tree
    original_anchor_close = artifact_store_module._windows_close_directory_anchor
    original_os_close = os.close
    fail_validation = True
    failures = 1
    target_authority: int | None = None

    def fail_first_validation(*args: object, **kwargs: object) -> None:
        nonlocal fail_validation
        original_validate(*args, **kwargs)  # type: ignore[arg-type]
        if fail_validation:
            fail_validation = False
            raise RuntimeError("validation failed")

    monkeypatch.setattr(store, "_validate_staged_tree", fail_first_validation)
    if os.name == "nt":

        def fail_once(handle: int) -> None:
            nonlocal failures, target_authority
            if target_authority is None:
                target_authority = handle
            if handle == target_authority and failures:
                failures -= 1
                raise OSError("injected prepare close failure")
            original_anchor_close(handle)

        monkeypatch.setattr(
            artifact_store_module,
            "_windows_close_directory_anchor",
            fail_once,
        )
    else:

        def fail_once(descriptor: int) -> None:
            nonlocal failures, target_authority
            if target_authority is None:
                target_authority = descriptor
            if descriptor == target_authority and failures:
                failures -= 1
                raise OSError("injected prepare close failure")
            original_os_close(descriptor)

        monkeypatch.setattr(os, "close", fail_once)

    with pytest.raises(RuntimeError, match="rollback blocked"):
        controller.delete_session(first)

    with pytest.raises(OSError, match="prepare close failure"):
        controller.delete_session(second)
    assert second in controller._sessions
    assert (tmp_path / "sessions" / second / "artifacts").is_dir()

    controller.delete_session(second)
    assert second not in controller._sessions


async def test_artifact_commit_failure_drops_session_and_retries_before_next_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-checkpoint erase failure remains exact and retryable."""

    if os.name == "nt":
        pytest.skip("POSIX retained-member retry contract")
    sink = EventCollector()
    gateway = ToolGateway()
    store = ArtifactStore(tmp_path / "sessions")
    controller = RuntimeController(
        model=ScriptedModel(script=[], context_capacity=100_000),
        gateway=gateway,
        event_sink=sink,
        checkpoint_store=FileCheckpointStore(tmp_path / "sessions"),
        artifact_store=store,
    )
    first = controller.create_session(working_scope=tmp_path, principal_id="owner")
    second = controller.create_session(working_scope=tmp_path, principal_id="owner")
    await store.offload(
        session_id=first,
        call_id="c1",
        outputs=[TextBlock(text="first artifact")],
    )
    await store.offload(
        session_id=second,
        call_id="c2",
        outputs=[TextBlock(text="second artifact")],
    )
    failures = 1
    original_commit = store.commit_session_deletion

    def fail_once(deletion: ArtifactSessionDeletion) -> None:
        nonlocal failures
        if failures:
            failures -= 1
            raise OSError("injected artifact erase failure")
        original_commit(deletion)

    monkeypatch.setattr(store, "commit_session_deletion", fail_once)
    with pytest.raises(OSError, match="erase failure"):
        controller.delete_session(first)

    assert first not in controller._sessions
    assert first not in {summary.session_id for summary in controller.list_sessions()}
    assert len(controller._pending_artifact_deletions) == 1

    deleted = controller.bulk_delete_sessions([second], principal_id="owner")

    assert deleted == [second]
    assert controller._pending_artifact_deletions == []


async def test_create_drive_detach_resume_terminate_and_list(tmp_path: Path) -> None:
    sink = EventCollector()
    controller = _controller(
        [ScriptedTurn(increments=[TextIncrement(text="hi")])], sink, tmp_path
    )

    session_id = controller.create_session(working_scope=tmp_path, label="lifecycle")
    await controller.drive(session_id, [TextBlock(text="hello")])

    controller.detach(session_id)

    listed = controller.list_sessions()
    assert [s.session_id for s in listed] == [session_id]
    assert listed[0].label == "lifecycle"

    fresh = _controller([], EventCollector(), tmp_path)
    await fresh.resume(session_id)
    assert [e.role for e in fresh.history_snapshot(session_id)] == ["user", "assistant"]

    fresh.terminate(session_id)
    with pytest.raises(RuntimeError):
        await fresh.drive(session_id, [TextBlock(text="after terminate")])


# --- replay on attach (FR-014) ----------------------------------------------------


async def test_attach_replays_history_bracketed_with_replay_flags(
    tmp_path: Path,
) -> None:
    first = _controller(_tool_script(), EventCollector(), tmp_path)
    session_id = first.create_session(working_scope=tmp_path)
    await first.drive(session_id, [TextBlock(text="please echo")])
    del first

    sink = EventCollector()
    second = _controller([], sink, tmp_path)
    await second.resume(session_id)
    sink.events.clear()  # drop resume diagnostics; observe the replay alone

    await second.attach(session_id)

    types = sink.types
    assert types[0] == "replay-started"
    assert types[-1] == "replay-completed"
    body = sink.events[1:-1]
    assert all(event.replay is True for event in sink.events)

    # Past user inputs replay verbatim (FR-014).
    user_inputs = [e for e in body if e.type == "user-input"]
    assert len(user_inputs) == 1
    assert list(user_inputs[0].payload.blocks) == [TextBlock(text="please echo")]

    body_types = [e.type for e in body]
    assert "assistant-output-increment" in body_types
    assert "tool-call-started" in body_types
    assert "tool-call-completed" in body_types
    assert sink.events[0].payload.count == len(body)
    assert sink.events[-1].payload.count == len(body)


async def test_attach_replaces_the_previous_driving_consumer(tmp_path: Path) -> None:
    sink = EventCollector()
    controller = _controller(
        [ScriptedTurn(increments=[TextIncrement(text="hi")])], sink, tmp_path
    )
    session_id = controller.create_session(working_scope=tmp_path)
    await controller.drive(session_id, [TextBlock(text="hello")])

    await controller.attach(session_id)
    first_replay = [e for e in sink.events if e.replay]
    sink.events.clear()

    await controller.attach(session_id)  # a new consumer replaces the old one
    second_replay = [e for e in sink.events if e.replay]

    assert [e.type for e in second_replay] == [e.type for e in first_replay]


# --- dispatcher semantics (FR-012, FR-013, FR-015) ---------------------------------


async def test_submit_input_during_an_active_turn_is_rejected_with_a_diagnostic(
    tmp_path: Path,
) -> None:
    script = [
        ScriptedTurn(increments=[TextIncrement(text=f"chunk-{i}") for i in range(30)]),
        ScriptedTurn(increments=[TextIncrement(text="second")]),
    ]
    sink = EventCollector()
    controller = _controller(script, sink, tmp_path, durable=False)
    session_id = controller.create_session(working_scope=tmp_path)

    send_requests, receive_requests = anyio.create_memory_object_stream[
        ConsumerRequest
    ](math.inf)
    dispatcher = Dispatcher(
        controller=controller, session_id=session_id, inbound=receive_requests
    )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(dispatcher.run)
        await send_requests.send(SubmitInput(blocks=(TextBlock(text="first"),)))
        with anyio.fail_after(5):
            while not any(e.type == "assistant-output-increment" for e in sink.events):
                await anyio.lowlevel.checkpoint()
            await send_requests.send(SubmitInput(blocks=(TextBlock(text="rejected"),)))
            while not any(e.type == "diagnostic" for e in sink.events):
                await anyio.lowlevel.checkpoint()
        send_requests.close()

    diagnostic = next(e for e in sink.events if e.type == "diagnostic")
    assert "already active" in diagnostic.payload.message
    assert sum(1 for e in sink.events if e.type == "user-input") == 1


async def test_disconnect_mid_run_denies_pending_approvals_and_never_hangs(
    tmp_path: Path,
) -> None:
    sink = EventCollector()
    controller = _controller(
        _tool_script(), sink, tmp_path, durable=False, decide=HumanApproval(rules=[])
    )
    session_id = controller.create_session(working_scope=tmp_path)

    send_requests, receive_requests = anyio.create_memory_object_stream[
        ConsumerRequest
    ](math.inf)
    dispatcher = Dispatcher(
        controller=controller, session_id=session_id, inbound=receive_requests
    )

    with anyio.fail_after(10):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(dispatcher.run)
            await send_requests.send(SubmitInput(blocks=(TextBlock(text="go"),)))
            while not any(e.type == "approval-requested" for e in sink.events):
                await anyio.lowlevel.checkpoint()
            # The consumer channel closes while the approval is pending.
            send_requests.close()

    resolved = next(e for e in sink.events if e.type == "approval-resolved")
    assert resolved.payload.decision == "deny"
    assert resolved.payload.resolution_source == "disconnect"
    terminated = next(e for e in sink.events if e.type == "run-terminated")
    assert terminated.payload.reason == "cancelled"


# --- increment batching (FR-015) -----------------------------------------------------


def _increment(sequence: int, text: str) -> RuntimeEvent:
    return AssistantOutputIncrementEvent(
        session_id="s1",
        sequence=sequence,
        occurred_at=datetime.now(UTC),
        payload=AssistantOutputIncrementPayload(text=text, turn_index=0),
    )


def _turn_completed(sequence: int) -> RuntimeEvent:
    return TurnCompletedEvent(
        session_id="s1",
        sequence=sequence,
        occurred_at=datetime.now(UTC),
        payload=TurnCompletedPayload(
            turn_index=0, stop_reason="end-turn", usage=TokenUsage()
        ),
    )


async def test_batching_buffers_increments_until_a_non_incremental_event(
    tmp_path: Path,
) -> None:
    delivered: list[RuntimeEvent] = []

    async def capture(event: RuntimeEvent) -> None:
        delivered.append(event)

    sink = BatchingSink(capture, max_buffer=16)

    await sink(_increment(1, "a"))
    await sink(_increment(2, "b"))
    assert delivered == []  # increments may be buffered (FR-015)

    await sink(_turn_completed(3))
    assert [e.sequence for e in delivered] == [
        1,
        2,
        3,
    ]  # flushed first, never reordered


async def test_batching_never_reorders_and_flushes_on_buffer_limit(
    tmp_path: Path,
) -> None:
    delivered: list[RuntimeEvent] = []

    async def capture(event: RuntimeEvent) -> None:
        delivered.append(event)

    sink = BatchingSink(capture, max_buffer=3)

    fed = [_increment(i, f"t{i}") for i in range(1, 5)]
    for event in fed:
        await sink(event)
    assert [e.sequence for e in delivered] == [1, 2, 3]  # limit flush

    await sink(_turn_completed(5))
    await sink(_increment(6, "after"))
    await sink.flush()

    assert [e.sequence for e in delivered] == [1, 2, 3, 4, 5, 6]
