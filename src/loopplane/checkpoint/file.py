"""Filesystem checkpoint storage (the default backend): append-only line-oriented JSON
records per session under a host-overridable base directory (research R6, A10).

Appends are flushed before they return (FR-080) and serialized by a per-session lock
(FR-084). Loading skips corrupt lines (FR-083); listing a missing root yields an empty
result (FR-085). Implements the ``CheckpointStore`` Protocol (``base.py``).
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
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

_RECORD_FILE = "records.jsonl"


class FileCheckpointStore:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._locks: dict[str, anyio.Lock] = {}

    def _record_file(self, session_id: str) -> Path:
        return self._base / session_id / _RECORD_FILE

    def _lock(self, session_id: str) -> anyio.Lock:
        return self._locks.setdefault(session_id, anyio.Lock())

    async def append(self, record: CheckpointRecord) -> None:
        """Append one record and flush before returning (FR-080, FR-084)."""
        line = serialize_record(record)
        async with self._lock(record.session_id):
            path = self._record_file(record.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()

    def load(self, session_id: str) -> tuple[list[CheckpointRecord], list[str]]:
        """Read the record stream in order; corrupt lines are skipped and
        reported, everything else loads (FR-083).
        """
        path = self._record_file(session_id)
        if not path.is_file():
            return [], []
        records: list[CheckpointRecord] = []
        problems: list[str] = []
        for line_number, line in enumerate(
            path.read_text("utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            record = deserialize_record(line)
            if record is None:
                problems.append(
                    f"skipped a corrupt checkpoint record at line {line_number}"
                )
            else:
                records.append(record)
        return records, problems

    def list_sessions(self) -> list[SessionSummary]:
        """Sessions with identity and recency metadata, newest first
        (FR-085); a missing root is an empty listing, not an error.
        """
        if not self._base.is_dir():
            return []
        summaries: list[SessionSummary] = []
        for directory in sorted(self._base.iterdir()):
            path = directory / _RECORD_FILE
            if not path.is_file():
                continue
            meta = self._read_meta(path)
            if meta is None:
                continue
            last_active = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            summaries.append(
                SessionSummary(
                    session_id=directory.name,
                    label=meta.payload.label,
                    created_at=meta.payload.created_at,
                    last_active_at=last_active,
                    principal_id=meta.payload.principal_id,
                )
            )
        return sorted(
            summaries, key=lambda summary: summary.last_active_at, reverse=True
        )

    async def set_title(self, session_id: str, title: str) -> None:
        """Append a fresh session-meta carrying the new title (030); latest
        wins. A no-op on an unknown session."""
        records, _ = self.load(session_id)
        original = next(
            (r for r in records if isinstance(r, SessionMetaRecord)), None
        )
        if original is None:
            return
        next_sequence = max((r.sequence for r in records), default=-1) + 1
        await self.append(
            SessionMetaRecord(
                session_id=session_id,
                sequence=next_sequence,
                recorded_at=datetime.now(UTC),
                payload=SessionMetaPayload(
                    created_at=original.payload.created_at,
                    label=title,
                    principal_id=original.payload.principal_id,
                ),
            )
        )

    def delete_session(self, session_id: str) -> None:
        """Remove the session's directory; idempotent if absent (030)."""
        directory = self._base / session_id
        if directory.is_dir():
            shutil.rmtree(directory)

    @staticmethod
    def _read_meta(path: Path) -> SessionMetaRecord | None:
        # The LATEST session-meta wins, so a rename (an appended meta) shows in
        # the listing (030); rebuild already applies the same last-wins rule.
        found: SessionMetaRecord | None = None
        for line in path.read_text("utf-8").splitlines():
            record = deserialize_record(line)
            if isinstance(record, SessionMetaRecord):
                found = record
        return found
