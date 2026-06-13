"""The pending-interaction registry and the human round-trips (FR-012,
FR-112, FR-115, FR-116).

One broker per session: approvals and questions share the same matching
machinery — unique request ids, exactly one resolution each, and disconnect
resolving everything pending.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import anyio

from loopplane.events.emitter import EventEmitter
from loopplane.events.envelope import Question

ResolutionSource = Literal["reviewer", "rule", "session-memory", "disconnect"]


@dataclass(frozen=True)
class ApprovalResolution:
    decision: Literal["allow", "deny"]
    scope: Literal["once", "session"]
    reason: str | None
    source: ResolutionSource


@dataclass
class _PendingApproval:
    event: anyio.Event = field(default_factory=anyio.Event)
    resolution: ApprovalResolution | None = None


@dataclass
class _PendingQuestion:
    event: anyio.Event = field(default_factory=anyio.Event)
    answers: list[str] | None = None


class InteractionBroker:
    def __init__(self, *, emitter: EventEmitter) -> None:
        self._emitter = emitter
        self._reviewer_attached = False
        self._approvals: dict[str, _PendingApproval] = {}
        self._questions: dict[str, _PendingQuestion] = {}

    @property
    def reviewer_attached(self) -> bool:
        return self._reviewer_attached

    def attach_reviewer(self) -> None:
        self._reviewer_attached = True

    def on_disconnect(self) -> None:
        """Resolve everything pending: approvals deny, questions cancel
        (FR-115); nothing ever hangs.
        """
        self._reviewer_attached = False
        for pending in self._approvals.values():
            if pending.resolution is None:
                pending.resolution = ApprovalResolution(
                    decision="deny",
                    scope="once",
                    reason="reviewer disconnected",
                    source="disconnect",
                )
                pending.event.set()
        for question in self._questions.values():
            if not question.event.is_set():
                question.event.set()

    async def request_approval(
        self, *, call_id: str, tool_name: str, input_summary: str
    ) -> ApprovalResolution:
        """Escalate an "ask" to the reviewer and hold until it resolves
        (FR-112). The resolution event is emitted from this side so it always
        follows its request in the stream.
        """
        request_id = uuid.uuid4().hex
        pending = _PendingApproval()
        self._approvals[request_id] = pending
        await self._emitter.approval_requested(
            request_id=request_id,
            call_id=call_id,
            tool_name=tool_name,
            input_summary=input_summary,
        )
        await pending.event.wait()
        del self._approvals[request_id]
        resolution = pending.resolution
        assert resolution is not None
        await self._emitter.approval_resolved(
            request_id=request_id,
            decision=resolution.decision,
            scope=resolution.scope,
            resolution_source=resolution.source,
        )
        return resolution

    def resolve_approval(
        self,
        request_id: str,
        *,
        decision: Literal["allow", "deny"],
        scope: Literal["once", "session"],
        reason: str | None = None,
    ) -> bool:
        """Apply at most one resolution per request (FR-012); unknown or
        already-resolved ids are rejected.
        """
        pending = self._approvals.get(request_id)
        if pending is None or pending.resolution is not None:
            return False
        pending.resolution = ApprovalResolution(
            decision=decision, scope=scope, reason=reason, source="reviewer"
        )
        pending.event.set()
        return True

    async def ask_question(self, questions: Sequence[Question]) -> list[str] | None:
        """Ask the user a non-permission question (FR-116); None means no
        user is available or the question was cancelled by disconnect.
        """
        if not self._reviewer_attached:
            return None
        request_id = uuid.uuid4().hex
        pending = _PendingQuestion()
        self._questions[request_id] = pending
        await self._emitter.question_asked(request_id, questions)
        await pending.event.wait()
        del self._questions[request_id]
        if pending.answers is not None:
            await self._emitter.question_answered(request_id, pending.answers)
        return pending.answers

    def answer_question(self, request_id: str, answers: Sequence[str]) -> bool:
        pending = self._questions.get(request_id)
        if pending is None or pending.event.is_set():
            return False
        pending.answers = list(answers)
        pending.event.set()
        return True
