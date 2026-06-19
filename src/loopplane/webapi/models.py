"""Public-safe, metadata-only request/response models for the web/API host (011).

Response bodies never carry conversation content: history is projected to
``{role, block_count}`` only — never the raw ``ContentBlock`` text or tool I/O
(FR-016, NFR-006).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from loopplane.host import RunOutcome
from loopplane.host.inspect import (
    McpServerInfo,
    MemoryEntryInfo,
    SkillInfo,
    ToolInfo,
)


class _SummaryLike(Protocol):
    """The public-safe shape read from a host ``SessionSummary`` — declared
    structurally so the layer reads it without importing a runtime-internal
    module (boundary discipline)."""

    @property
    def session_id(self) -> str: ...

    @property
    def label(self) -> str | None: ...

    @property
    def created_at(self) -> datetime: ...

    @property
    def last_active_at(self) -> datetime: ...


# --- requests ----------------------------------------------------------------


class UploadRef(BaseModel):
    """A reference to an uploaded file a turn carries (036). Each is resolved
    through the per-principal ``UploadStore`` (028); an image upload is assembled
    into an ``ImageBlock`` on the user message, a non-image stays
    ``read_upload``-readable."""

    reference: str = Field(min_length=1)


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = (
        None  # 028 — optional model id; routed to the chosen host (one per run)
    )
    uploads: list[
        UploadRef
    ] = []  # 036 — optional upload refs; image uploads become leading ImageBlocks


class RenameRequest(BaseModel):
    """A session rename (030): a non-blank title (trimmed)."""

    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title must not be blank")
        return trimmed


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
    last_active_at: datetime
    created_at: datetime

    @classmethod
    def from_summary(cls, summary: _SummaryLike) -> SessionSummaryView:
        return cls(
            session_id=summary.session_id,
            label=summary.label,
            last_active_at=summary.last_active_at,
            created_at=summary.created_at,
        )


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


# --- 027: read-only inspection views (metadata-only) -------------------------


class SkillView(BaseModel):
    name: str
    description: str
    autonomous: bool
    approval_required: bool
    source: str

    @classmethod
    def from_info(cls, info: SkillInfo) -> SkillView:
        return cls(
            name=info.name,
            description=info.description,
            autonomous=info.autonomous,
            approval_required=info.approval_required,
            source=info.source,
        )


class SkillsResponse(BaseModel):
    skills: list[SkillView]
    problems: list[str]


class ToolView(BaseModel):
    name: str
    description: str
    read_only: bool
    source: str

    @classmethod
    def from_info(cls, info: ToolInfo) -> ToolView:
        return cls(
            name=info.name,
            description=info.description,
            read_only=info.read_only,
            source=info.source,
        )


class McpServerView(BaseModel):
    name: str
    tools: list[str]

    @classmethod
    def from_info(cls, info: McpServerInfo) -> McpServerView:
        return cls(name=info.name, tools=list(info.tools))


class MemoryEntryView(BaseModel):
    type: str
    name: str
    description: str
    snippet: str

    @classmethod
    def from_info(cls, info: MemoryEntryInfo) -> MemoryEntryView:
        return cls(
            type=info.type,
            name=info.name,
            description=info.description,
            snippet=info.snippet,
        )


# --- 028: model catalog + uploads (metadata-only) ----------------------------


class ModelInfo(BaseModel):
    """An available model the host offers — metadata only, never an api key."""

    id: str
    label: str
    accepts_media: bool = False  # 036 — whether the model accepts image input


class UploadResult(BaseModel):
    reference: str
    name: str
