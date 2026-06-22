"""Shared helpers for event replay store tests (071)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from loopplane.webapi import EventReplayRecord, FileEventReplayStore


def replay_frame(sequence: int, data: str | None = None) -> str:
    return f"id: {sequence}\ndata: {data or f'e{sequence}'}\n\n"


def replay_record(
    sequence: int,
    *,
    session_id: str = "session-1",
    principal_id: str = "owner-1",
    frame: str | None = None,
) -> EventReplayRecord:
    return EventReplayRecord(
        session_id=session_id,
        sequence=sequence,
        principal_id=principal_id,
        frame=frame or replay_frame(sequence),
        recorded_at=datetime(2026, 6, 22, 12, 0, sequence, tzinfo=UTC),
    )


def file_replay_store(base: Path, *, max_events: int = 10) -> FileEventReplayStore:
    return FileEventReplayStore(base, max_events_per_session=max_events)
