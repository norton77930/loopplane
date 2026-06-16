"""US3 acceptance 3.1–3.4: record a session, "kill the process" (discard all
in-memory state), resume from records alone, and compare reconstructed state
(SC-003; FR-080–FR-083, FR-090–FR-093).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.artifacts import ArtifactStore, make_artifact_handoff
from loopplane.checkpoint import (
    AssistantMessageRecord,
    FileCheckpointStore,
    SessionMetaRecord,
    UserInputRecord,
)
from loopplane.controller.controller import RuntimeController
from loopplane.gateway import ToolGateway
from loopplane.model import (
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    ToolCallBlock,
    ToolCallRequest,
    ToolResultBlock,
)

from .conftest import ECHO_DESCRIPTOR, EventCollector, echo_handler

pytestmark = pytest.mark.anyio


def _controller(
    script: list[ScriptEntry],
    sink: EventCollector,
    tmp_path: Path,
    *,
    output_limit: int | None = None,
) -> RuntimeController:
    """Build a controller wired to durable stores under tmp_path; a fresh
    call simulates a fresh process over the same storage.
    """
    checkpoint = FileCheckpointStore(tmp_path / "sessions")
    artifacts = ArtifactStore(tmp_path / "sessions", preview_chars=64)
    handoff = make_artifact_handoff(artifacts)
    if output_limit is not None:
        gateway = ToolGateway(output_limit_bytes=output_limit, artifact_handoff=handoff)
    else:
        gateway = ToolGateway(artifact_handoff=handoff)
    gateway.register(ECHO_DESCRIPTOR, echo_handler)
    return RuntimeController(
        model=ScriptedModel(script=script, context_capacity=100_000),
        gateway=gateway,
        event_sink=sink,
        checkpoint_store=checkpoint,
        artifact_store=artifacts,
    )


async def test_resume_restores_completed_turns_and_continues(tmp_path: Path) -> None:
    """Acceptance 3.1: restored history matches all completed steps and the
    next prompt continues coherently.
    """
    first = _controller(
        [
            ScriptedTurn(
                increments=[
                    ToolCallRequest(
                        call_id="c1", tool_name="echo", input={"text": "one"}
                    )
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="first run done")]),
        ],
        EventCollector(),
        tmp_path,
    )
    session_id = first.create_session(working_scope=tmp_path, label="resumable")
    await first.drive(session_id, [TextBlock(text="run one")])
    recorded_history = first.history_snapshot(session_id)
    del first  # the process dies; only the records remain

    sink = EventCollector()
    second = _controller(
        [ScriptedTurn(increments=[TextIncrement(text="continued")])], sink, tmp_path
    )
    await second.resume(session_id)

    restored = second.history_snapshot(session_id)
    assert [entry.role for entry in restored] == [e.role for e in recorded_history]
    assert [entry.blocks for entry in restored] == [e.blocks for e in recorded_history]

    await second.drive(session_id, [TextBlock(text="run two")])
    final = second.history_snapshot(session_id)
    assert final[-2].blocks == (TextBlock(text="run two"),)
    assert final[-1].blocks == (TextBlock(text="continued"),)
    assert sink.events[-1].payload.reason == "natural-completion"


async def test_resume_repairs_an_interrupted_tool_call(tmp_path: Path) -> None:
    """Acceptance 3.2: a recorded call without a result is repaired with an
    error-marked synthetic result and surfaced as a warning.
    """
    now = datetime.now(UTC)
    store = FileCheckpointStore(tmp_path / "sessions")
    await store.append(
        SessionMetaRecord(
            session_id="s1",
            sequence=1,
            recorded_at=now,
            payload={"created_at": now, "label": "interrupted"},
        )
    )
    await store.append(
        UserInputRecord(
            session_id="s1",
            sequence=2,
            recorded_at=now,
            payload={"blocks": [TextBlock(text="please echo")]},
        )
    )
    await store.append(
        AssistantMessageRecord(
            session_id="s1",
            sequence=3,
            recorded_at=now,
            payload={
                "blocks": [
                    ToolCallBlock(
                        call_id="c-lost", tool_name="echo", input={"text": "x"}
                    )
                ]
            },
        )
    )
    # The process died here: the call has no recorded result.

    sink = EventCollector()
    controller = _controller(
        [ScriptedTurn(increments=[TextIncrement(text="recovered")])], sink, tmp_path
    )
    await controller.resume("s1")

    history = controller.history_snapshot("s1")
    (synthetic,) = history[-1].blocks
    assert isinstance(synthetic, ToolResultBlock)
    assert synthetic.call_id == "c-lost"
    assert synthetic.outcome == "failure"

    warnings = [e for e in sink.events if e.type == "diagnostic"]
    assert any("c-lost" in w.payload.message for w in warnings)

    # The conversation remains valid: the next run drives normally.
    await controller.drive("s1", [TextBlock(text="continue")])
    assert sink.events[-1].payload.reason == "natural-completion"


async def test_oversized_output_round_trips_via_an_artifact(tmp_path: Path) -> None:
    """Acceptance 3.3: full output stored as an artifact; the conversation
    carries preview + stable reference; retrieval works after the run.
    """
    big = "important data line\n" * 500
    sink = EventCollector()
    controller = _controller(
        [
            ScriptedTurn(
                increments=[
                    ToolCallRequest(call_id="c1", tool_name="echo", input={"text": big})
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="done")]),
        ],
        sink,
        tmp_path,
        output_limit=256,
    )
    session_id = controller.create_session(working_scope=tmp_path)

    await controller.drive(session_id, [TextBlock(text="produce a lot")])

    completed = next(e for e in sink.events if e.type == "tool-call-completed")
    reference = completed.payload.artifact_reference
    assert reference is not None

    artifacts = ArtifactStore(tmp_path / "sessions", preview_chars=64)
    assert artifacts.retrieve(session_id, reference) == big

    history = controller.history_snapshot(session_id)
    (result_block,) = history[2].blocks
    assert isinstance(result_block, ToolResultBlock)
    assert result_block.artifact_reference == reference
    preview = "".join(
        block.text for block in result_block.outputs if isinstance(block, TextBlock)
    )
    assert 0 < len(preview) < len(big)


async def test_corrupted_record_is_skipped_with_a_warning_on_resume(
    tmp_path: Path,
) -> None:
    """Acceptance 3.4: one corrupted record skips with a warning; everything
    else loads.
    """
    first = _controller(
        [ScriptedTurn(increments=[TextIncrement(text="answer")])],
        EventCollector(),
        tmp_path,
    )
    session_id = first.create_session(working_scope=tmp_path)
    await first.drive(session_id, [TextBlock(text="hello")])
    expected = first.history_snapshot(session_id)
    del first

    record_file = next((tmp_path / "sessions" / session_id).glob("*.jsonl"))
    lines = record_file.read_text("utf-8").splitlines()
    lines.insert(2, '{"corrupted": ')
    record_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sink = EventCollector()
    second = _controller([], sink, tmp_path)
    await second.resume(session_id)

    assert [e.blocks for e in second.history_snapshot(session_id)] == [
        e.blocks for e in expected
    ]
    warnings = [e for e in sink.events if e.type == "diagnostic"]
    assert any(w.payload.severity == "warning" for w in warnings)
