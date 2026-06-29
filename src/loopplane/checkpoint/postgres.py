"""PostgreSQL checkpoint storage (optional backend): the same append-only session
records in a PostgreSQL database, selected by the host (a DSN / ``conninfo``).

Requires the ``loopplane[postgres]`` extra (``psycopg``); the import is **deferred
to construction** so ``loopplane.checkpoint`` imports without it and the default
File/SQLite backends are unaffected. It **reuses** the ``records.py`` encoding
(``serialize_record`` / ``deserialize_record`` / ``SessionMetaRecord``) so all
backends share one record format and one corrupt-record story (FR-083 parity), and
mirrors ``SqliteCheckpointStore``'s contract exactly.

Per **ADR 0008** (the *sync thread-bridge*): the sync ``CheckpointStore`` Protocol
is **unchanged** — the async methods (``append`` / ``set_title``) off-load the
(sync) psycopg work to a worker thread via ``anyio.to_thread``; the sync methods
(``load`` / ``list_sessions`` / ``delete_session``) call psycopg directly, like the
SQLite backend. The DSN/credential is held but never logged or echoed. Implements
the ``CheckpointStore`` Protocol (``base.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import groupby
from operator import itemgetter
from typing import Any

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
    "sequence BIGINT NOT NULL, "
    "recorded_at TEXT NOT NULL, "
    "data TEXT NOT NULL, "
    "PRIMARY KEY (session_id, sequence))"
)


def _require_psycopg() -> Any:
    """The psycopg module, or a clear error naming the extra when it is absent."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised via a simulated absence
        raise RuntimeError(
            "PostgresCheckpointStore requires psycopg; install loopplane[postgres]"
        ) from exc
    return psycopg


class PostgresCheckpointStore:
    def __init__(self, conninfo: str) -> None:
        self._psycopg = _require_psycopg()
        self._conninfo = conninfo  # a DSN/credential — never logged or echoed
        self._locks: dict[str, anyio.Lock] = {}

    def _lock(self, session_id: str) -> anyio.Lock:
        return self._locks.setdefault(session_id, anyio.Lock())

    def _connect(self) -> Any:
        connection = self._psycopg.connect(self._conninfo)
        connection.execute(_SCHEMA)
        connection.commit()
        return connection

    def _append_sync(self, record: CheckpointRecord, line: str) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO records(session_id, sequence, recorded_at, data) "
                "VALUES (%s, %s, %s, %s)",
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

    async def append(self, record: CheckpointRecord) -> None:
        """Insert one record and commit before returning (FR-080, FR-084); the
        sync psycopg work is off-loaded to a worker thread (ADR 0008)."""
        line = serialize_record(record)
        async with self._lock(record.session_id):
            await anyio.to_thread.run_sync(self._append_sync, record, line)

    def load(self, session_id: str) -> tuple[list[CheckpointRecord], list[str]]:
        """The session's records ordered by sequence; corrupt rows are skipped and
        reported, mirroring the other backends (FR-083). A never-written store is an
        empty result (the table is created on connect)."""
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT data FROM records WHERE session_id = %s ORDER BY sequence",
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
        """Identity + recency, newest first (FR-085); ``last_active_at`` is the
        session's latest ``recorded_at``."""
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
                ),
            )
        )

    async def set_title(self, session_id: str, title: str) -> None:
        """Append a fresh session-meta carrying the new title (030); latest wins. A
        no-op on an unknown session."""
        await self.update_session_metadata(session_id, label=title)

    def delete_session(self, session_id: str) -> None:
        """Remove all rows for the session; idempotent if absent (030)."""
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM records WHERE session_id = %s", (session_id,)
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
