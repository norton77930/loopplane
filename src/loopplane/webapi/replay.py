"""Durable event replay storage for session SSE reconnect (071).

The replay store persists already-serialized public SSE frames. It is a web/API
transport boundary, not a Runtime Event Bus owner.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import anyio

_RECORD_FILE = "event-replay.jsonl"
_CORRUPT_PROBLEM = "skipped a corrupt event replay record"
_UNAVAILABLE_PROBLEM = "event replay store unavailable"
_SQL_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS event_replay_records ("
    "session_id TEXT NOT NULL, "
    "sequence INTEGER NOT NULL, "
    "principal_id TEXT NOT NULL, "
    "recorded_at TEXT NOT NULL, "
    "frame TEXT NOT NULL, "
    "PRIMARY KEY (session_id, sequence))"
)
_PG_SCHEMA = _SQL_SCHEMA.replace("sequence INTEGER", "sequence BIGINT")


def _frame_sequence(frame: str) -> int | None:
    if not frame.startswith("id: "):
        return None
    newline = frame.find("\n")
    if newline == -1:
        return None
    try:
        return int(frame[4:newline])
    except ValueError:
        return None


@dataclass(frozen=True)
class EventReplayRecord:
    session_id: str
    sequence: int
    principal_id: str
    frame: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.principal_id:
            raise ValueError("principal_id must be non-empty")
        if not self.frame:
            raise ValueError("frame must be non-empty")
        if _frame_sequence(self.frame) != self.sequence:
            raise ValueError("frame id must match sequence")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")


class EventReplayStore(Protocol):
    async def append(self, record: EventReplayRecord) -> None:
        """Persist one replay record."""
        ...

    def load_after(
        self,
        session_id: str,
        principal_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> tuple[list[EventReplayRecord], list[str]]:
        """Load retained records after ``sequence`` for the principal-owned session."""
        ...

    def delete_session(self, session_id: str) -> None:
        """Remove replay records for a session."""
        ...


def _encode(record: EventReplayRecord) -> str:
    data = asdict(record)
    data["recorded_at"] = record.recorded_at.isoformat()
    return json.dumps(data, sort_keys=True)


def _decode(line: str) -> EventReplayRecord | None:
    try:
        document = json.loads(line)
        if not isinstance(document, dict):
            return None
        recorded_at = datetime.fromisoformat(str(document["recorded_at"]))
        return EventReplayRecord(
            session_id=str(document["session_id"]),
            sequence=int(document["sequence"]),
            principal_id=str(document["principal_id"]),
            frame=str(document["frame"]),
            recorded_at=recorded_at,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _record_from_row(
    session_id: object,
    sequence: object,
    principal_id: object,
    recorded_at: object,
    frame: object,
) -> EventReplayRecord | None:
    try:
        return EventReplayRecord(
            session_id=str(session_id),
            sequence=int(str(sequence)),
            principal_id=str(principal_id),
            frame=str(frame),
            recorded_at=datetime.fromisoformat(str(recorded_at)),
        )
    except (TypeError, ValueError):
        return None


def _require_psycopg() -> Any:
    """The psycopg module, or a clear error naming the optional extra."""

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised via simulated absence
        raise RuntimeError(
            "PostgresEventReplayStore requires psycopg; install loopplane[postgres]"
        ) from exc
    return psycopg


class FileEventReplayStore:
    def __init__(self, base_dir: Path, *, max_events_per_session: int) -> None:
        if max_events_per_session <= 0:
            raise ValueError("max_events_per_session must be positive")
        self._base = base_dir
        self._max_events = max_events_per_session
        self._locks: dict[str, anyio.Lock] = {}

    def _record_file(self, session_id: str) -> Path:
        return self._base / session_id / _RECORD_FILE

    def _lock(self, session_id: str) -> anyio.Lock:
        return self._locks.setdefault(session_id, anyio.Lock())

    async def append(self, record: EventReplayRecord) -> None:
        async with self._lock(record.session_id):
            path = self._record_file(record.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(_encode(record) + "\n")
                handle.flush()
            self._compact(record.session_id)

    def load_after(
        self,
        session_id: str,
        principal_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> tuple[list[EventReplayRecord], list[str]]:
        if limit <= 0:
            return [], []
        try:
            records, problems = self._load_all(session_id)
        except OSError:
            return [], [_UNAVAILABLE_PROBLEM]
        deduped: dict[int, EventReplayRecord] = {}
        for record in records:
            if record.principal_id == principal_id:
                deduped[record.sequence] = record
        out = [record for seq, record in sorted(deduped.items()) if seq > sequence][
            :limit
        ]
        return out, problems

    def delete_session(self, session_id: str) -> None:
        directory = self._base / session_id
        if directory.is_dir():
            shutil.rmtree(directory)

    def _load_all(self, session_id: str) -> tuple[list[EventReplayRecord], list[str]]:
        path = self._record_file(session_id)
        if not path.is_file():
            return [], []
        records: list[EventReplayRecord] = []
        problems: list[str] = []
        for line in path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            record = _decode(line)
            if record is None:
                problems.append(_CORRUPT_PROBLEM)
            else:
                records.append(record)
        return records, problems

    def _compact(self, session_id: str) -> None:
        path = self._record_file(session_id)
        records, _ = self._load_all(session_id)
        deduped = {record.sequence: record for record in records}
        retained = [record for _, record in sorted(deduped.items())][
            -self._max_events :
        ]
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in retained:
                handle.write(_encode(record) + "\n")


class SqliteEventReplayStore:
    def __init__(self, db_path: Path, *, max_events_per_session: int) -> None:
        if max_events_per_session <= 0:
            raise ValueError("max_events_per_session must be positive")
        self._db_path = db_path
        self._max_events = max_events_per_session
        self._locks: dict[str, anyio.Lock] = {}

    def _lock(self, session_id: str) -> anyio.Lock:
        return self._locks.setdefault(session_id, anyio.Lock())

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.execute(_SQL_SCHEMA)
        return connection

    async def append(self, record: EventReplayRecord) -> None:
        async with self._lock(record.session_id):
            connection = self._connect()
            try:
                connection.execute(
                    "INSERT OR REPLACE INTO event_replay_records"
                    "(session_id, sequence, principal_id, recorded_at, frame) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        record.session_id,
                        record.sequence,
                        record.principal_id,
                        record.recorded_at.isoformat(),
                        record.frame,
                    ),
                )
                connection.execute(
                    "DELETE FROM event_replay_records "
                    "WHERE session_id = ? AND sequence NOT IN ("
                    "SELECT sequence FROM event_replay_records "
                    "WHERE session_id = ? ORDER BY sequence DESC LIMIT ?)",
                    (record.session_id, record.session_id, self._max_events),
                )
                connection.commit()
            finally:
                connection.close()

    def load_after(
        self,
        session_id: str,
        principal_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> tuple[list[EventReplayRecord], list[str]]:
        if limit <= 0:
            return [], []
        if not self._db_path.is_file():
            return [], []
        try:
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT session_id, sequence, principal_id, recorded_at, frame "
                    "FROM event_replay_records "
                    "WHERE session_id = ? AND principal_id = ? AND sequence > ? "
                    "ORDER BY sequence LIMIT ?",
                    (session_id, principal_id, sequence, limit),
                ).fetchall()
            finally:
                connection.close()
        except (OSError, sqlite3.Error):
            return [], [_UNAVAILABLE_PROBLEM]
        records: list[EventReplayRecord] = []
        problems: list[str] = []
        for row in rows:
            record = _record_from_row(*row)
            if record is None:
                problems.append(_CORRUPT_PROBLEM)
            else:
                records.append(record)
        return records, problems

    def delete_session(self, session_id: str) -> None:
        if not self._db_path.is_file():
            return
        with suppress(OSError, sqlite3.Error):
            connection = self._connect()
            try:
                connection.execute(
                    "DELETE FROM event_replay_records WHERE session_id = ?",
                    (session_id,),
                )
                connection.commit()
            finally:
                connection.close()


class PostgresEventReplayStore:
    def __init__(self, conninfo: str, *, max_events_per_session: int) -> None:
        if max_events_per_session <= 0:
            raise ValueError("max_events_per_session must be positive")
        self._psycopg = _require_psycopg()
        self._conninfo = conninfo
        self._max_events = max_events_per_session
        self._locks: dict[str, anyio.Lock] = {}

    def _lock(self, session_id: str) -> anyio.Lock:
        return self._locks.setdefault(session_id, anyio.Lock())

    def _connect(self) -> Any:
        connection = self._psycopg.connect(self._conninfo)
        connection.execute(_PG_SCHEMA)
        connection.commit()
        return connection

    def _append_sync(self, record: EventReplayRecord) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO event_replay_records"
                "(session_id, sequence, principal_id, recorded_at, frame) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (session_id, sequence) DO UPDATE "
                "SET principal_id = EXCLUDED.principal_id, "
                "recorded_at = EXCLUDED.recorded_at, "
                "frame = EXCLUDED.frame",
                (
                    record.session_id,
                    record.sequence,
                    record.principal_id,
                    record.recorded_at.isoformat(),
                    record.frame,
                ),
            )
            connection.execute(
                "DELETE FROM event_replay_records "
                "WHERE session_id = %s AND sequence NOT IN ("
                "SELECT sequence FROM event_replay_records "
                "WHERE session_id = %s ORDER BY sequence DESC LIMIT %s)",
                (record.session_id, record.session_id, self._max_events),
            )
            connection.commit()
        finally:
            connection.close()

    async def append(self, record: EventReplayRecord) -> None:
        async with self._lock(record.session_id):
            await anyio.to_thread.run_sync(self._append_sync, record)

    def load_after(
        self,
        session_id: str,
        principal_id: str,
        sequence: int,
        *,
        limit: int,
    ) -> tuple[list[EventReplayRecord], list[str]]:
        if limit <= 0:
            return [], []
        try:
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT session_id, sequence, principal_id, recorded_at, frame "
                    "FROM event_replay_records "
                    "WHERE session_id = %s AND principal_id = %s AND sequence > %s "
                    "ORDER BY sequence LIMIT %s",
                    (session_id, principal_id, sequence, limit),
                ).fetchall()
            finally:
                connection.close()
        except Exception:
            return [], [_UNAVAILABLE_PROBLEM]
        records: list[EventReplayRecord] = []
        problems: list[str] = []
        for row in rows:
            record = _record_from_row(*row)
            if record is None:
                problems.append(_CORRUPT_PROBLEM)
            else:
                records.append(record)
        return records, problems

    def delete_session(self, session_id: str) -> None:
        with suppress(Exception):
            connection = self._connect()
            try:
                connection.execute(
                    "DELETE FROM event_replay_records WHERE session_id = %s",
                    (session_id,),
                )
                connection.commit()
            finally:
                connection.close()
