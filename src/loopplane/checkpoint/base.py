"""The checkpoint store boundary: a Protocol over durable, append-only session records
plus the storage-agnostic ``SessionSummary`` it lists (contracts/checkpoint-store.md;
Constitution IV). Implementations: ``FileCheckpointStore`` (the default, ``file.py``)
and ``SqliteCheckpointStore`` (``sqlite.py``). The interface is single-tenant — every
operation is keyed by ``session_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from loopplane.checkpoint.records import CheckpointRecord


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    label: str | None
    created_at: datetime
    last_active_at: datetime
    principal_id: str | None = None


class CheckpointStore(Protocol):
    """Durable, append-only session records behind a storage-agnostic seam."""

    async def append(self, record: CheckpointRecord) -> None:
        """Durably persist one record, flushed/committed before returning;
        appends for one session are serialized (FR-080, FR-084)."""
        ...

    def load(self, session_id: str) -> tuple[list[CheckpointRecord], list[str]]:
        """The session's records in append order, plus reported problems (e.g.
        skipped corrupt records, FR-083); an unknown session yields ``([], [])``."""
        ...

    def list_sessions(self) -> list[SessionSummary]:
        """Identity + recency for every session, most-recent-first; a
        missing/never-written store yields an empty list (FR-085)."""
        ...

    async def set_title(self, session_id: str, title: str) -> None:
        """Update a session's title by appending a fresh session-meta record
        (append-only); the latest title wins in ``list_sessions`` and on
        rebuild. A no-op on an unknown session (030)."""
        ...

    def delete_session(self, session_id: str) -> None:
        """Durably remove a session's records; idempotent on an unknown id (030)."""
        ...
