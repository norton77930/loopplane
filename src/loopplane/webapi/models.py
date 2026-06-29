"""Public-safe, metadata-only request/response models for the web/API host (011).

Response bodies never carry conversation content: history is projected to
``{role, block_count}`` only — never the raw ``ContentBlock`` text or tool I/O
(FR-016, NFR-006).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from loopplane.host import RunOutcome
from loopplane.host.capabilities import (
    ManagedMcpConfiguration,
    ManagedMemoryEntry,
    ManagedSchedule,
    ManagedSkill,
    ModelDefault,
    WorkspaceContext,
)
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
    # 045 — optional JSON schema constraining the response (structured output);
    # rejected upfront if the selected model does not support it.
    output_schema: dict[str, object] | None = None


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


class ForkSessionRequest(BaseModel):
    sequence: int = Field(ge=0)
    title: str | None = None
    model: str | None = None

    @field_validator("title")
    @classmethod
    def _trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class BulkDeleteRequest(BaseModel):
    session_ids: list[str] = Field(min_length=1)
    confirm: bool

    @field_validator("confirm")
    @classmethod
    def _confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("confirm must be true")
        return value


class SessionAnswer(BaseModel):
    allow: bool
    scope: Literal["once", "session"] = "once"
    reason: str | None = None


class QuestionAnswer(BaseModel):
    answers: list[str]


class LiveTicketView(BaseModel):
    ticket: str
    session_id: str
    expires_at: datetime
    issued_at: datetime
    capabilities: list[str]


class LiveClientMessage(BaseModel):
    type: Literal["submit", "abort", "approval_decision", "question_answer", "ack"]
    client_message_id: str | None = None
    sequence: int | None = None
    payload: dict[str, object] = Field(default_factory=dict)


# --- responses (metadata-only) -----------------------------------------------


class HistoryEntryView(BaseModel):
    """A history entry projected to metadata only — a role and a block count,
    never the block content (FR-016)."""

    role: str
    block_count: int


class SessionCostView(BaseModel):
    """A session's accumulated USD (064 cost surfacing). ``usd_spent`` is the exact
    Decimal string-encoded, or ``None`` ("not tracked") when no budget is configured."""

    session_id: str
    usd_spent: str | None

    @classmethod
    def of(cls, session_id: str, spent: Decimal | None) -> SessionCostView:
        return cls(
            session_id=session_id, usd_spent=None if spent is None else str(spent)
        )


class MonthlyCostView(BaseModel):
    """A principal's current-month accumulated USD (064). ``usd_spent`` is the exact
    Decimal string-encoded, or ``None`` ("not tracked") when no ledger is configured."""

    principal_id: str
    month: str
    usd_spent: str | None

    @classmethod
    def of(
        cls, principal_id: str, month: str, spent: Decimal | None
    ) -> MonthlyCostView:
        return cls(
            principal_id=principal_id,
            month=month,
            usd_spent=None if spent is None else str(spent),
        )


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
    model: str | None = None
    starred: bool = False
    forked_from_session_id: str | None = None
    forked_from_sequence: int | None = None
    search_snippet: str | None = None

    @classmethod
    def from_summary(cls, summary: _SummaryLike) -> SessionSummaryView:
        return cls(
            session_id=summary.session_id,
            label=summary.label,
            last_active_at=summary.last_active_at,
            created_at=summary.created_at,
            model=getattr(summary, "model", None),
            starred=getattr(summary, "starred", False),
            forked_from_session_id=getattr(summary, "forked_from_session_id", None),
            forked_from_sequence=getattr(summary, "forked_from_sequence", None),
            search_snippet=getattr(summary, "search_snippet", None),
        )


class OpenedSession(BaseModel):
    session_id: str


class BulkDeleteResult(BaseModel):
    deleted: list[str]


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


# --- 075: capability management views ----------------------------------------


class ManagedMemoryView(BaseModel):
    id: str
    name: str
    kind: str
    description: str
    snippet: str
    status: str
    updated_at: datetime | None = None

    @classmethod
    def from_entry(cls, entry: ManagedMemoryEntry) -> ManagedMemoryView:
        return cls(**entry.__dict__)


class ManagedSkillView(BaseModel):
    id: str
    name: str
    description: str
    source: str
    status: str
    problem: str | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_skill(cls, skill: ManagedSkill) -> ManagedSkillView:
        return cls(**skill.__dict__)


class ManagedMcpConfigurationView(BaseModel):
    id: str
    name: str
    status: str
    tool_count: int
    tools: list[str]
    problem: str | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_config(
        cls, config: ManagedMcpConfiguration
    ) -> ManagedMcpConfigurationView:
        return cls(
            id=config.id,
            name=config.name,
            status=config.status,
            tool_count=config.tool_count,
            tools=list(config.tools),
            problem=config.problem,
            updated_at=config.updated_at,
        )


class WorkspaceContextView(BaseModel):
    id: str
    name: str
    description: str
    workspace_label: str
    status: str
    updated_at: datetime | None = None

    @classmethod
    def from_context(cls, context: WorkspaceContext) -> WorkspaceContextView:
        return cls(**context.__dict__)


class ManagedScheduleView(BaseModel):
    id: str
    name: str
    description: str
    trigger: str
    enabled: bool
    status: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    problem: str | None = None

    @classmethod
    def from_schedule(cls, schedule: ManagedSchedule) -> ManagedScheduleView:
        return cls(**schedule.__dict__)


class ModelDefaultView(BaseModel):
    model_id: str | None
    label: str | None
    status: str
    updated_at: datetime | None = None

    @classmethod
    def from_default(cls, default: ModelDefault) -> ModelDefaultView:
        return cls(**default.__dict__)


class MemoryWriteRequest(BaseModel):
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    content: str

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("name must not be blank")
        return trimmed


# --- 028: model catalog + uploads (metadata-only) ----------------------------


class ModelInfo(BaseModel):
    """An available model the host offers — metadata only, never an api key."""

    id: str
    label: str
    accepts_media: bool = False  # 036 — whether the model accepts image input
    # 045 — whether the model supports native structured output
    supports_structured_output: bool = False


class UploadResult(BaseModel):
    reference: str
    name: str


# --- 065: backend-semantic slash commands ------------------------------------


class CommandRequest(BaseModel):
    """A backend command to run (065): a leading-``/`` command line + an optional
    session to scope session commands (``/cost``, ``/compact``)."""

    command: str
    session_id: str | None = None


class CommandResultView(BaseModel):
    """A normalized, public-safe command result (065)."""

    kind: str
    text: str
