"""Public-safe, metadata-only view models for the desktop/studio host (012).

A UI shell or terminal renders these. They never carry conversation content:
history is projected to ``{role, block_count}`` only — never the raw
``ContentBlock`` text or tool I/O (FR-030, NFR-006). Plain frozen dataclasses —
the studio is in-process, so no serialization framework is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from loopplane.host import RunOutcome


class _SummaryLike(Protocol):
    """The public-safe shape read from a host ``SessionSummary`` — declared
    structurally so the layer reads it without importing a runtime-internal
    module (boundary discipline)."""

    @property
    def session_id(self) -> str: ...

    @property
    def label(self) -> str | None: ...


@dataclass(frozen=True)
class HistoryEntryView:
    """A history entry projected to metadata only — a role and a block count,
    never the block content (FR-030)."""

    role: str
    block_count: int


@dataclass(frozen=True)
class RunResultView:
    """The metadata-only projection of a ``RunOutcome`` (a one-shot run's result
    or an interactive submit's outcome)."""

    session_id: str
    termination_reason: str
    turns_taken: int
    history: tuple[HistoryEntryView, ...]
    consumer_failures: tuple[str, ...]

    @classmethod
    def from_outcome(cls, outcome: RunOutcome) -> RunResultView:
        return cls(
            session_id=outcome.session_id,
            termination_reason=outcome.termination_reason,
            turns_taken=outcome.turns_taken,
            history=tuple(
                HistoryEntryView(role=entry.role, block_count=len(entry.blocks))
                for entry in outcome.history
            ),
            consumer_failures=tuple(outcome.consumer_failures),
        )


# An interactive submit returns the same shape as a one-shot run.
OutcomeView = RunResultView


@dataclass(frozen=True)
class SessionSummaryView:
    session_id: str
    label: str | None

    @classmethod
    def from_summary(cls, summary: _SummaryLike) -> SessionSummaryView:
        return cls(session_id=summary.session_id, label=summary.label)


ErrorKind = Literal["invalid", "conflict", "not-found", "not-available"]


@dataclass(frozen=True)
class ErrorView:
    """The one public-safe failure view — a fixed ``kind`` + ``detail`` string,
    never a stack trace, internal name, path, or secret (FR-050)."""

    kind: ErrorKind
    detail: str
