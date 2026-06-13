"""Contract tests for Human Approval (contracts/approval.md).

Asserts denial-as-data with reasons (FR-111), the ask round-trip (FR-112),
session-scoped memory (FR-113), persistent-rule precedence (FR-114),
reviewer-disconnect denying all pending requests (FR-115), and the question
round-trip with exactly-one resolution (FR-116).
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from loopplane.approval import (
    HumanApproval,
    InteractionBroker,
    PermissionRule,
    PolicyAllow,
    PolicyDeny,
    PolicyVerdict,
    resolve_rules,
)
from loopplane.context import RunContext
from loopplane.events import EventSequencer, Question, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.model import ToolCallRequest, ToolDescriptor

pytestmark = pytest.mark.anyio


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]

    def of_type(self, event_type: str) -> list[RuntimeEvent]:
        return [event for event in self.events if event.type == event_type]


def _broker(sink: _Collector) -> InteractionBroker:
    emitter = EventEmitter(
        session_id="session-1", sequencer=EventSequencer(), sink=sink
    )
    return InteractionBroker(emitter=emitter)


def _context(tmp_path: Path, broker: InteractionBroker | None = None) -> RunContext:
    return RunContext(
        session_id="session-1", working_scope=tmp_path, interactions=broker
    )


def _call(tool_name: str = "echo") -> ToolCallRequest:
    return ToolCallRequest(call_id="c1", tool_name=tool_name, input={"text": "x"})


def _descriptor(tool_name: str = "echo") -> ToolDescriptor:
    return ToolDescriptor(
        name=tool_name, description="d", input_schema={"type": "object"}
    )


def _emitter(sink: _Collector) -> EventEmitter:
    return EventEmitter(session_id="session-1", sequencer=EventSequencer(), sink=sink)


async def _decide(
    approval: HumanApproval,
    context: RunContext,
    sink: _Collector,
    tool_name: str = "echo",
) -> PolicyVerdict:
    return await approval(
        _call(tool_name), _descriptor(tool_name), context, _emitter(sink)
    )


# --- rule precedence (FR-114) -------------------------------------------------


def test_within_one_scope_deny_overrides_allow() -> None:
    rules = [
        PermissionRule(matcher="echo", effect="allow", scope="project"),
        PermissionRule(matcher="echo", effect="deny", scope="project"),
    ]
    assert resolve_rules(rules, "echo") == "deny"


def test_more_local_scope_overrides_broader_scope() -> None:
    rules = [
        PermissionRule(matcher="echo", effect="deny", scope="user"),
        PermissionRule(matcher="echo", effect="allow", scope="session-local"),
    ]
    assert resolve_rules(rules, "echo") == "allow"

    rules = [
        PermissionRule(matcher="echo", effect="allow", scope="project"),
        PermissionRule(matcher="echo", effect="deny", scope="session-local"),
    ]
    assert resolve_rules(rules, "echo") == "deny"


def test_rules_match_by_tool_name_pattern() -> None:
    rules = [PermissionRule(matcher="mcp:*", effect="deny", scope="user")]
    assert resolve_rules(rules, "mcp:server:tool") == "deny"
    assert resolve_rules(rules, "internal-tool") is None


def test_no_matching_rule_falls_through() -> None:
    assert resolve_rules([], "echo") is None


# --- denial semantics (FR-111) -------------------------------------------------


async def test_deny_rule_yields_denial_with_a_reason(tmp_path: Path) -> None:
    sink = _Collector()
    approval = HumanApproval(
        rules=[PermissionRule(matcher="echo", effect="deny", scope="project")]
    )

    verdict = await _decide(approval, _context(tmp_path), sink)

    assert isinstance(verdict, PolicyDeny)
    assert verdict.reason  # a default reason is supplied when none is given


async def test_ask_without_a_reviewer_resolves_as_deny(tmp_path: Path) -> None:
    sink = _Collector()
    approval = HumanApproval(rules=[])  # no rule -> fall through to escalation

    verdict = await _decide(approval, _context(tmp_path, broker=None), sink)

    assert isinstance(verdict, PolicyDeny)
    assert "no reviewer available" in verdict.reason
    assert sink.types == []  # no escalation happened


# --- ask escalation round-trip (FR-112, FR-113) --------------------------------


async def test_ask_round_trip_allow_once(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()
    context = _context(tmp_path, broker)
    approval = HumanApproval(rules=[])

    verdicts: list[PolicyVerdict] = []

    async def decide() -> None:
        verdicts.append(await _decide(approval, context, sink))

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(decide)
        with anyio.fail_after(5):
            while not sink.of_type("approval-requested"):
                await anyio.lowlevel.checkpoint()
        requested = sink.of_type("approval-requested")[0]
        assert requested.payload.tool_name == "echo"
        assert broker.resolve_approval(
            requested.payload.request_id, decision="allow", scope="once"
        )

    assert verdicts == [PolicyAllow()]
    resolved = sink.of_type("approval-resolved")[0]
    assert resolved.payload.request_id == requested.payload.request_id
    assert resolved.payload.decision == "allow"
    assert resolved.payload.scope == "once"
    assert resolved.payload.resolution_source == "reviewer"
    # "once" leaves no session memory behind
    assert context.session_approval_memory == {}


async def test_session_scoped_approval_is_remembered_and_not_re_asked(
    tmp_path: Path,
) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()
    context = _context(tmp_path, broker)
    approval = HumanApproval(rules=[])

    async with anyio.create_task_group() as task_group:

        async def decide_first() -> None:
            verdict = await _decide(approval, context, sink)
            assert verdict == PolicyAllow()

        task_group.start_soon(decide_first)
        with anyio.fail_after(5):
            while not sink.of_type("approval-requested"):
                await anyio.lowlevel.checkpoint()
        request_id = sink.of_type("approval-requested")[0].payload.request_id
        broker.resolve_approval(request_id, decision="allow", scope="session")

    assert context.session_approval_memory == {"echo": "allow"}

    # The same tool is not re-asked for the remainder of the session.
    verdict = await _decide(approval, context, sink)
    assert verdict == PolicyAllow()
    assert len(sink.of_type("approval-requested")) == 1


async def test_session_scoped_denial_is_also_remembered(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()
    context = _context(tmp_path, broker)
    approval = HumanApproval(rules=[])

    async with anyio.create_task_group() as task_group:

        async def decide_first() -> None:
            verdict = await _decide(approval, context, sink)
            assert isinstance(verdict, PolicyDeny)

        task_group.start_soon(decide_first)
        with anyio.fail_after(5):
            while not sink.of_type("approval-requested"):
                await anyio.lowlevel.checkpoint()
        request_id = sink.of_type("approval-requested")[0].payload.request_id
        broker.resolve_approval(
            request_id, decision="deny", scope="session", reason="dangerous"
        )

    verdict = await _decide(approval, context, sink)
    assert isinstance(verdict, PolicyDeny)
    assert len(sink.of_type("approval-requested")) == 1


async def test_unknown_or_repeated_resolutions_are_ignored(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()

    assert (
        broker.resolve_approval("never-issued", decision="allow", scope="once") is False
    )


# --- disconnect (FR-115) --------------------------------------------------------


async def test_reviewer_disconnect_denies_all_pending_requests(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()
    context = _context(tmp_path, broker)
    approval = HumanApproval(rules=[])

    verdicts: list[PolicyVerdict] = []

    async def decide(tool_name: str) -> None:
        verdicts.append(await _decide(approval, context, sink, tool_name))

    with anyio.fail_after(5):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(decide, "tool-a")
            task_group.start_soon(decide, "tool-b")
            while len(sink.of_type("approval-requested")) < 2:
                await anyio.lowlevel.checkpoint()
            broker.on_disconnect()

    assert len(verdicts) == 2
    assert all(isinstance(verdict, PolicyDeny) for verdict in verdicts)
    resolved = sink.of_type("approval-resolved")
    assert len(resolved) == 2
    assert {event.payload.resolution_source for event in resolved} == {"disconnect"}


# --- non-permission questions (FR-116) -------------------------------------------


async def test_question_round_trip_with_exactly_one_resolution(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()

    answers: list[list[str] | None] = []

    async def ask() -> None:
        answers.append(
            await broker.ask_question(
                [Question(text="Which path?", options=["a", "b"])]
            )
        )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(ask)
        with anyio.fail_after(5):
            while not sink.of_type("question-asked"):
                await anyio.lowlevel.checkpoint()
        request_id = sink.of_type("question-asked")[0].payload.request_id
        assert broker.answer_question(request_id, ["a"]) is True
        # exactly one resolution: the second attempt is rejected
        assert broker.answer_question(request_id, ["b"]) is False

    assert answers == [["a"]]
    answered = sink.of_type("question-answered")
    assert len(answered) == 1
    assert answered[0].payload.answers == ["a"]


async def test_disconnect_cancels_pending_questions(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)
    broker.attach_reviewer()

    answers: list[list[str] | None] = []

    async def ask() -> None:
        answers.append(await broker.ask_question([Question(text="anyone there?")]))

    with anyio.fail_after(5):
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(ask)
            while not sink.of_type("question-asked"):
                await anyio.lowlevel.checkpoint()
            broker.on_disconnect()

    assert answers == [None]


async def test_question_without_a_reviewer_returns_none(tmp_path: Path) -> None:
    sink = _Collector()
    broker = _broker(sink)  # reviewer never attached

    assert await broker.ask_question([Question(text="hello?")]) is None
    assert sink.types == []
