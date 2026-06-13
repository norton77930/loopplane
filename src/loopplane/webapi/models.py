"""Public-safe, metadata-only request/response models for the web/API host (011).

Response bodies never carry conversation content: history is projected to
``{role, block_count}`` only — never the raw ``ContentBlock`` text or tool I/O
(FR-016, NFR-006).
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from loopplane.host import RunOutcome


class _SummaryLike(Protocol):
    """The public-safe shape read from a host ``SessionSummary`` — declared
    structurally so the layer reads it without importing a runtime-internal
    module (boundary discipline)."""

    @property
    def session_id(self) -> str: ...

    @property
    def label(self) -> str | None: ...


# --- requests ----------------------------------------------------------------


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1)


class SessionAnswer(BaseModel):
    allow: bool
    scope: Literal["once", "session"] = "once"
    reason: str | None = None


class QuestionAnswer(BaseModel):
    answers: list[str]


# --- responses (metadata-only) -----------------------------------------------


class HistoryEntryView(BaseModel):
    """A history entry projected to metadata only — a role and a block count,
    never the block content (FR-016)."""

    role: str
    block_count: int


class RunResult(BaseModel):
    session_id: str
    termination_reason: str
    turns_taken: int
    history: list[HistoryEntryView]
    consumer_failures: list[str]

    @classmethod
    def from_outcome(cls, outcome: RunOutcome) -> RunResult:
        return cls(
            session_id=outcome.session_id,
            termination_reason=outcome.termination_reason,
            turns_taken=outcome.turns_taken,
            history=[
                HistoryEntryView(role=entry.role, block_count=len(entry.blocks))
                for entry in outcome.history
            ],
            consumer_failures=list(outcome.consumer_failures),
        )


class SessionSummaryView(BaseModel):
    session_id: str
    label: str | None

    @classmethod
    def from_summary(cls, summary: _SummaryLike) -> SessionSummaryView:
        return cls(session_id=summary.session_id, label=summary.label)


class OpenedSession(BaseModel):
    session_id: str


class Resolved(BaseModel):
    resolved: bool


class ArtifactContent(BaseModel):
    reference: str
    content: str


class ErrorResponse(BaseModel):
    """The one public-safe error envelope: a fixed ``detail`` string, never a
    stack trace, internal name, path, secret, or the supplied credential."""

    detail: str
