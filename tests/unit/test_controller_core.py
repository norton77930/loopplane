"""Direct unit tests for the controller package's harness-free public surface
(contracts/run-lifecycle.md): session-state wire values and the frozen
consumer-request models.

Dispatcher and BatchingSink behavior is covered by
tests/contract/test_run_lifecycle.py; this file only pins the contract shapes
that need no runtime harness.
"""

from __future__ import annotations

import typing
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic import ValidationError

import loopplane.controller as controller
from loopplane.checkpoint import (
    AssistantMessageRecord,
    FileCheckpointStore,
    SessionMetaRecord,
    TerminationRecord,
    UserInputRecord,
)
from loopplane.controller import (
    ApprovalDecision,
    Cancel,
    QuestionAnswer,
    SessionState,
    SubmitInput,
)
from loopplane.controller.controller import RuntimeController
from loopplane.events import RunTerminatedEvent, RuntimeEvent
from loopplane.gateway import ToolGateway
from loopplane.model import ModelIncrement, ModelRequest, TextBlock, TextIncrement


def test_session_state_wire_values_are_stable() -> None:
    assert set(typing.get_args(SessionState)) == {
        "created",
        "active",
        "suspended",
        "terminated",
    }


def test_public_surface_exports_resolve() -> None:
    for name in controller.__all__:
        assert getattr(controller, name) is not None


def test_submit_input_is_frozen() -> None:
    request = SubmitInput(blocks=(TextBlock(text="hi"),))
    with pytest.raises(ValidationError):
        request.blocks = ()  # type: ignore[misc]


def test_approval_decision_validates_decision_and_scope() -> None:
    decision = ApprovalDecision(request_id="r1", decision="allow")
    assert decision.scope == "once"
    assert decision.reason is None
    with pytest.raises(ValidationError):
        ApprovalDecision(request_id="r1", decision="maybe")
    with pytest.raises(ValidationError):
        ApprovalDecision(request_id="r1", decision="deny", scope="forever")


def test_question_answer_requires_answers() -> None:
    answer = QuestionAnswer(request_id="q1", answers=("yes",))
    assert answer.answers == ("yes",)
    with pytest.raises(ValidationError):
        QuestionAnswer(request_id="q1")  # type: ignore[call-arg]


def test_cancel_is_a_frozen_marker() -> None:
    assert Cancel() == Cancel()


def _checkpoint_store(base_dir: Path) -> FileCheckpointStore:
    return FileCheckpointStore(base_dir / "sessions")


class _SingleTextModel:
    def context_capacity(self) -> int:
        return 100_000

    async def stream_turn(
        self, _request: ModelRequest
    ) -> AsyncIterator[ModelIncrement]:
        yield TextIncrement(text="complete")


@pytest.mark.anyio
async def test_terminal_record_is_persisted_in_append_order_before_forwarding(
    tmp_path: Path,
) -> None:
    store = _checkpoint_store(tmp_path)
    forwarded_terminal_records: list[TerminationRecord] = []

    async def sink(event: RuntimeEvent) -> None:
        if isinstance(event, RunTerminatedEvent):
            records, problems = store.load(event.session_id)
            assert problems == []
            assert isinstance(records[-1], TerminationRecord)
            forwarded_terminal_records.append(records[-1])

    runtime = RuntimeController(
        model=_SingleTextModel(),
        gateway=ToolGateway(),
        event_sink=sink,
        checkpoint_store=store,
    )
    session_id = runtime.create_session(working_scope=tmp_path)

    await runtime.drive(session_id, [TextBlock(text="hello")])

    records, problems = store.load(session_id)
    assert problems == []
    assert [type(record) for record in records] == [
        SessionMetaRecord,
        UserInputRecord,
        AssistantMessageRecord,
        TerminationRecord,
    ]
    assert [record.sequence for record in records] == [1, 2, 3, 4]
    assert forwarded_terminal_records == [records[-1]]
