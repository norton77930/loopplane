"""Event construction and emission: stamps the envelope (session, sequence,
time) and forwards each event to an async sink.

The sink is the runtime's outbound seam: hosts and the Dispatcher supply it
(contracts/run-lifecycle.md outbound channel).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Literal

from loopplane.errors import NormalizedError
from loopplane.events.envelope import (
    ApprovalRequestedEvent,
    ApprovalRequestedPayload,
    ApprovalResolvedEvent,
    ApprovalResolvedPayload,
    AssistantOutputIncrementEvent,
    AssistantOutputIncrementPayload,
    AssistantReasoningIncrementEvent,
    AssistantReasoningIncrementPayload,
    DiagnosticEvent,
    DiagnosticPayload,
    Question,
    QuestionAnsweredEvent,
    QuestionAnsweredPayload,
    QuestionAskedEvent,
    QuestionAskedPayload,
    RunTerminatedEvent,
    RunTerminatedPayload,
    RuntimeEvent,
    TerminationReason,
    ToolCallCompletedEvent,
    ToolCallCompletedPayload,
    ToolCallStartedEvent,
    ToolCallStartedPayload,
    TurnCompletedEvent,
    TurnCompletedPayload,
    UserInputEvent,
    UserInputPayload,
)
from loopplane.events.sequencer import EventSequencer
from loopplane.model.boundary import TokenUsage
from loopplane.model.content import ContentBlock, OutputBlock

EventSink = Callable[[RuntimeEvent], Awaitable[None]]


class EventEmitter:
    def __init__(
        self, *, session_id: str, sequencer: EventSequencer, sink: EventSink
    ) -> None:
        self._session_id = session_id
        self._sequencer = sequencer
        self._sink = sink

    def _sequence(self) -> int:
        return self._sequencer.next_sequence()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    async def user_input(self, blocks: Sequence[ContentBlock]) -> None:
        await self._sink(
            UserInputEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=UserInputPayload(blocks=list(blocks)),
            )
        )

    async def output_increment(self, text: str, turn_index: int) -> None:
        await self._sink(
            AssistantOutputIncrementEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=AssistantOutputIncrementPayload(
                    text=text, turn_index=turn_index
                ),
            )
        )

    async def reasoning_increment(self, text: str, turn_index: int) -> None:
        await self._sink(
            AssistantReasoningIncrementEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=AssistantReasoningIncrementPayload(
                    text=text, turn_index=turn_index
                ),
            )
        )

    async def turn_completed(
        self, turn_index: int, stop_reason: str, usage: TokenUsage
    ) -> None:
        await self._sink(
            TurnCompletedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=TurnCompletedPayload(
                    turn_index=turn_index, stop_reason=stop_reason, usage=usage
                ),
            )
        )

    async def tool_call_started(
        self, call_id: str, tool_name: str, call_input: dict[str, object]
    ) -> None:
        await self._sink(
            ToolCallStartedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=ToolCallStartedPayload(
                    call_id=call_id, tool_name=tool_name, input=call_input
                ),
            )
        )

    async def tool_call_completed(
        self,
        *,
        call_id: str,
        outcome: Literal["success", "failure"],
        outputs: Sequence[OutputBlock],
        duration_seconds: float,
        error: NormalizedError | None = None,
        artifact_reference: str | None = None,
    ) -> None:
        await self._sink(
            ToolCallCompletedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=ToolCallCompletedPayload(
                    call_id=call_id,
                    outcome=outcome,
                    outputs=list(outputs),
                    artifact_reference=artifact_reference,
                    error=error,
                    duration_seconds=duration_seconds,
                ),
            )
        )

    async def approval_requested(
        self, *, request_id: str, call_id: str, tool_name: str, input_summary: str
    ) -> None:
        await self._sink(
            ApprovalRequestedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=ApprovalRequestedPayload(
                    request_id=request_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    input_summary=input_summary,
                ),
            )
        )

    async def approval_resolved(
        self,
        *,
        request_id: str,
        decision: Literal["allow", "deny"],
        scope: Literal["once", "session"],
        resolution_source: Literal["reviewer", "rule", "session-memory", "disconnect"],
    ) -> None:
        await self._sink(
            ApprovalResolvedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=ApprovalResolvedPayload(
                    request_id=request_id,
                    decision=decision,
                    scope=scope,
                    resolution_source=resolution_source,
                ),
            )
        )

    async def question_asked(
        self, request_id: str, questions: Sequence[Question]
    ) -> None:
        await self._sink(
            QuestionAskedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=QuestionAskedPayload(
                    request_id=request_id, questions=list(questions)
                ),
            )
        )

    async def question_answered(self, request_id: str, answers: Sequence[str]) -> None:
        await self._sink(
            QuestionAnsweredEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=QuestionAnsweredPayload(
                    request_id=request_id, answers=list(answers)
                ),
            )
        )

    async def diagnostic(
        self,
        severity: Literal["info", "warning", "error"],
        category: str,
        message: str,
    ) -> None:
        await self._sink(
            DiagnosticEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=DiagnosticPayload(
                    severity=severity, category=category, message=message
                ),
            )
        )

    async def run_terminated(self, reason: TerminationReason, turns_taken: int) -> None:
        await self._sink(
            RunTerminatedEvent(
                session_id=self._session_id,
                sequence=self._sequence(),
                occurred_at=self._now(),
                payload=RunTerminatedPayload(reason=reason, turns_taken=turns_taken),
            )
        )
