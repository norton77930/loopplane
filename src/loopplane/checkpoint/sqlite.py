"""SQLite checkpoint storage (optional backend): the same append-only session
records in a local SQLite database, selected via
``StorageConfig(checkpoint_backend="sqlite")``.

Standard-library ``sqlite3`` only — no new dependency, fully offline. It **reuses**
the ``records.py`` encoding (``serialize_record`` / ``deserialize_record`` /
``SessionMetaRecord``) so both backends share one record format and one
corrupt-record story (FR-083 parity). Appends commit before returning (FR-080) and
are serialized per session (FR-084).

Unlike the filesystem backend, ``SessionSummary.last_active_at`` derives from the
session's latest ``recorded_at`` (SQLite has no per-session file mtime); it still
represents most-recent activity (contracts/checkpoint-store.md). Implements the
``CheckpointStore`` Protocol (``base.py``).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from itertools import groupby
from operator import itemgetter
from pathlib import Path

import anyio

from loopplane.checkpoint.base import SessionSummary
from loopplane.checkpoint.records import (
    CheckpointRecord,
    SessionMetaPayload,
    SessionMetaRecord,
    deserialize_record,
    serialize_record,
)

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS records ("
    "session_id TEXT NOT NULL, "
    "sequence INTEGER NOT NULL, "
    "recorded_at TEXT NOT NULL, "
    "data TEXT NOT NULL, "
    "PRIMARY KEY (session_id, sequence))"
)


class SqliteCheckpointStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._locks: dict[str, anyio.Lock] = {}

    def _lock(self, session_id: str) -> anyio.Lock:
        return self._locks.setdefault(session_id, anyio.Lock())

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.execute(_SCHEMA)
        return connection

    async def append(self, record: CheckpointRecord) -> None:
        """Insert one record and commit before returning (FR-080, FR-084)."""
        line = serialize_record(record)
        async with self._lock(record.session_id):
            connection = self._connect()
            try:
                connection.execute(
                    "INSERT INTO records(session_id, sequence, recorded_at, data) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        record.session_id,
                        record.sequence,
                        record.recorded_at.isoformat(),
                        line,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def load(self, session_id: str) -> tuple[list[CheckpointRecord], list[str]]:
        """The session's records ordered by sequence; corrupt rows are skipped
        and reported, mirroring the filesystem backend (FR-083).
        """
        if not self._db_path.is_file():
            return [], []
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT data FROM records WHERE session_id = ? ORDER BY sequence",
                (session_id,),
            ).fetchall()
        finally:
            connection.close()
        records: list[CheckpointRecord] = []
        problems: list[str] = []
        for (data,) in rows:
            record = deserialize_record(data)
            if record is None:
                problems.append(
                    f"skipped a corrupt checkpoint record in session {session_id}"
                )
            else:
                records.append(record)
        return records, problems

    def list_sessions(self) -> list[SessionSummary]:
        """Identity and recency, newest first (FR-085); a missing database is an
        empty listing, not an error. ``last_active_at`` is the session's latest
        ``recorded_at``.
        """
        if not self._db_path.is_file():
            return []
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT session_id, recorded_at, data FROM records "
                "ORDER BY session_id, sequence"
            ).fetchall()
        finally:
            connection.close()
        summaries: list[SessionSummary] = []
        for session_id, group in groupby(rows, key=itemgetter(0)):
            meta: SessionMetaRecord | None = None
            last_active: datetime | None = None
            for _session_id, recorded_at, data in group:
                moment = datetime.fromisoformat(recorded_at)
                if last_active is None or moment > last_active:
                    last_active = moment
                record = deserialize_record(data)
                if isinstance(record, SessionMetaRecord):
                    meta = record  # the latest session-meta wins (030)
            if meta is None or last_active is None:
                continue
            summaries.append(
                SessionSummary(
                    session_id=session_id,
                    label=meta.payload.label,
                    created_at=meta.payload.created_at,
                    last_active_at=last_active,
                    principal_id=meta.payload.principal_id,
                    model=meta.payload.model,
                    starred=meta.payload.starred,
                    forked_from_session_id=meta.payload.forked_from_session_id,
                    forked_from_sequence=meta.payload.forked_from_sequence,
                    context_id=meta.payload.context_id,
                    context_name=meta.payload.context_name,
                    context_workspace_label=meta.payload.context_workspace_label,
                    context_status=meta.payload.context_status,
                )
            )
        return sorted(
            summaries, key=lambda summary: summary.last_active_at, reverse=True
        )

    async def create_session_metadata(
        self,
        session_id: str,
        *,
        created_at: datetime,
        label: str | None = None,
        principal_id: str | None = None,
        model: str | None = None,
        forked_from_session_id: str | None = None,
        forked_from_sequence: int | None = None,
    ) -> None:
        records, _ = self.load(session_id)
        if records:
            return
        await self.append(
            SessionMetaRecord(
                session_id=session_id,
                sequence=1,
                recorded_at=datetime.now(UTC),
                payload=SessionMetaPayload(
                    created_at=created_at,
                    label=label,
                    principal_id=principal_id,
                    model=model,
                    forked_from_session_id=forked_from_session_id,
                    forked_from_sequence=forked_from_sequence,
                ),
            )
        )

    async def update_session_metadata(
        self,
        session_id: str,
        *,
        label: str | None = None,
        model: str | None = None,
        starred: bool | None = None,
        forked_from_session_id: str | None = None,
        forked_from_sequence: int | None = None,
        context_id: str | None = None,
        context_name: str | None = None,
        context_workspace_label: str | None = None,
        context_status: str | None = None,
    ) -> None:
        records, _ = self.load(session_id)
        original = self._latest_meta(records)
        if original is None:
            return
        payload = original.payload
        next_sequence = max((r.sequence for r in records), default=-1) + 1
        await self.append(
            SessionMetaRecord(
                session_id=session_id,
                sequence=next_sequence,
                recorded_at=datetime.now(UTC),
                payload=SessionMetaPayload(
                    created_at=payload.created_at,
                    label=payload.label if label is None else label,
                    principal_id=payload.principal_id,
                    model=payload.model if model is None else model,
                    starred=payload.starred if starred is None else starred,
                    forked_from_session_id=(
                        payload.forked_from_session_id
                        if forked_from_session_id is None
                        else forked_from_session_id
                    ),
                    forked_from_sequence=(
                        payload.forked_from_sequence
                        if forked_from_sequence is None
                        else forked_from_sequence
                    ),
                    context_id=payload.context_id if context_id is None else context_id,
                    context_name=(
                        payload.context_name if context_name is None else context_name
                    ),
                    context_workspace_label=(
                        payload.context_workspace_label
                        if context_workspace_label is None
                        else context_workspace_label
                    ),
                    context_status=(
                        payload.context_status
                        if context_status is None
                        else context_status
                    ),
                ),
            )
        )

    async def set_title(self, session_id: str, title: str) -> None:
        """Insert a fresh session-meta carrying the new title (030); latest
        wins. A no-op on an unknown session."""
        await self.update_session_metadata(session_id, label=title)

    def delete_session(self, session_id: str) -> None:
        """Remove all rows for the session; idempotent if absent (030)."""
        if not self._db_path.is_file():
            return
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM records WHERE session_id = ?", (session_id,)
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _latest_meta(records: list[CheckpointRecord]) -> SessionMetaRecord | None:
        found: SessionMetaRecord | None = None
        for record in records:
            if isinstance(record, SessionMetaRecord):
                found = record
        return found
