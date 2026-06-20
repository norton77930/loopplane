"""The event envelope and the closed vocabulary (contracts/runtime-events.md;
FR-060–FR-062).

The only language the Agent Loop speaks to the outside world. One
vocabulary-wide schema version; evolution within a version is additive only
(research A4; FR-065).
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from loopplane.errors import NormalizedError
from loopplane.model.boundary import TokenUsage
from loopplane.model.content import ContentBlock, OutputBlock

SCHEMA_VERSION: Final[int] = 1

RUNTIME_EVENT_TYPES: Final[tuple[str, ...]] = (
    "user-input",
    "assistant-output-increment",
    "assistant-reasoning-increment",
    "turn-completed",
    "tool-call-started",
    "tool-call-completed",
    "approval-requested",
    "approval-resolved",
    "question-asked",
    "question-answered",
    "replay-started",
    "replay-completed",
    "diagnostic",
    "run-terminated",
)


class _EventModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class _Envelope(_EventModel):
    schema_version: int = SCHEMA_VERSION
    session_id: str
    sequence: int
    occurred_at: AwareDatetime
    replay: bool = False


class UserInputPayload(_EventModel):
    blocks: list[ContentBlock]


class UserInputEvent(_Envelope):
    type: Literal["user-input"] = "user-input"
    payload: UserInputPayload


class AssistantOutputIncrementPayload(_EventModel):
    text: str
    turn_index: int


class AssistantOutputIncrementEvent(_Envelope):
    type: Literal["assistant-output-increment"] = "assistant-output-increment"
    payload: AssistantOutputIncrementPayload


class AssistantReasoningIncrementPayload(_EventModel):
    text: str
    turn_index: int


class AssistantReasoningIncrementEvent(_Envelope):
    type: Literal["assistant-reasoning-increment"] = "assistant-reasoning-increment"
    payload: AssistantReasoningIncrementPayload


class TurnCompletedPayload(_EventModel):
    turn_index: int
    stop_reason: str
    usage: TokenUsage


class TurnCompletedEvent(_Envelope):
    type: Literal["turn-completed"] = "turn-completed"
    payload: TurnCompletedPayload


class ToolCallStartedPayload(_EventModel):
    call_id: str
    tool_name: str
    input: dict[str, object]


class ToolCallStartedEvent(_Envelope):
    type: Literal["tool-call-started"] = "tool-call-started"
    payload: ToolCallStartedPayload


class ToolCallCompletedPayload(_EventModel):
    call_id: str
    outcome: Literal["success", "failure"]
    outputs: list[OutputBlock] = []
    artifact_reference: str | None = None
    error: NormalizedError | None = None
    duration_seconds: float


class ToolCallCompletedEvent(_Envelope):
    type: Literal["tool-call-completed"] = "tool-call-completed"
    payload: ToolCallCompletedPayload


class ApprovalRequestedPayload(_EventModel):
    request_id: str
    call_id: str
    tool_name: str
    input_summary: str


class ApprovalRequestedEvent(_Envelope):
    type: Literal["approval-requested"] = "approval-requested"
    payload: ApprovalRequestedPayload


class ApprovalResolvedPayload(_EventModel):
    request_id: str
    decision: Literal["allow", "deny"]
    scope: Literal["once", "session"]
    resolution_source: Literal["reviewer", "rule", "session-memory", "disconnect"]


class ApprovalResolvedEvent(_Envelope):
    type: Literal["approval-resolved"] = "approval-resolved"
    payload: ApprovalResolvedPayload


class Question(_EventModel):
    text: str
    options: list[str] = []


class QuestionAskedPayload(_EventModel):
    request_id: str
    questions: list[Question]


class QuestionAskedEvent(_Envelope):
    type: Literal["question-asked"] = "question-asked"
    payload: QuestionAskedPayload


class QuestionAnsweredPayload(_EventModel):
    request_id: str
    answers: list[str]


class QuestionAnsweredEvent(_Envelope):
    type: Literal["question-answered"] = "question-answered"
    payload: QuestionAnsweredPayload


class ReplayStartedPayload(_EventModel):
    count: int


class ReplayStartedEvent(_Envelope):
    type: Literal["replay-started"] = "replay-started"
    payload: ReplayStartedPayload


class ReplayCompletedPayload(_EventModel):
    count: int


class ReplayCompletedEvent(_Envelope):
    type: Literal["replay-completed"] = "replay-completed"
    payload: ReplayCompletedPayload


class DiagnosticPayload(_EventModel):
    severity: Literal["info", "warning", "error"]
    category: str
    message: str


class DiagnosticEvent(_Envelope):
    type: Literal["diagnostic"] = "diagnostic"
    payload: DiagnosticPayload


TerminationReason = Literal[
    "natural-completion",
    "turn-budget-exhausted",
    "cancelled",
    "unrecoverable-error",
    "budget-exceeded",
]


class RunTerminatedPayload(_EventModel):
    reason: TerminationReason
    turns_taken: int


class RunTerminatedEvent(_Envelope):
    type: Literal["run-terminated"] = "run-terminated"
    payload: RunTerminatedPayload


RuntimeEvent = Annotated[
    UserInputEvent
    | AssistantOutputIncrementEvent
    | AssistantReasoningIncrementEvent
    | TurnCompletedEvent
    | ToolCallStartedEvent
    | ToolCallCompletedEvent
    | ApprovalRequestedEvent
    | ApprovalResolvedEvent
    | QuestionAskedEvent
    | QuestionAnsweredEvent
    | ReplayStartedEvent
    | ReplayCompletedEvent
    | DiagnosticEvent
    | RunTerminatedEvent,
    Field(discriminator="type"),
]
