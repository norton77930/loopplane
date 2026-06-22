"""Contract tests for the durable event replay store (071)."""

from __future__ import annotations

import builtins
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.webapi import (
    EventReplayRecord,
    EventReplayStore,
    FileEventReplayStore,
    PostgresEventReplayStore,
    SqliteEventReplayStore,
)
from tests.replay_helpers import replay_frame, replay_record

pytestmark = pytest.mark.anyio

_PUBLIC_UNAVAILABLE = "event replay store unavailable"


def _make_store(
    backend: str,
    root: Path,
    *,
    max_events: int = 10,
) -> EventReplayStore:
    if backend == "file":
        return FileEventReplayStore(root / "file", max_events_per_session=max_events)
    if backend == "sqlite":
        return SqliteEventReplayStore(
            root / "replay.sqlite", max_events_per_session=max_events
        )
    raise AssertionError(f"unknown backend: {backend}")


@pytest.fixture(params=["file", "sqlite"])
def backend(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def test_event_replay_record_validates_public_shape() -> None:
    record = replay_record(2)

    assert record.session_id == "session-1"
    assert record.sequence == 2
    assert record.principal_id == "owner-1"
    assert record.frame == replay_frame(2)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_id", ""),
        ("principal_id", ""),
        ("frame", ""),
        ("sequence", -1),
    ],
)
def test_event_replay_record_rejects_invalid_values(field: str, value: object) -> None:
    kwargs = {
        "session_id": "session-1",
        "sequence": 1,
        "principal_id": "owner-1",
        "frame": replay_frame(1),
        "recorded_at": datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC),
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        EventReplayRecord(**kwargs)


def test_event_replay_record_rejects_mismatched_frame_sequence() -> None:
    with pytest.raises(ValueError):
        replay_record(2, frame=replay_frame(3))


async def test_store_loads_records_after_cursor_in_order(
    backend: str,
    tmp_path: Path,
) -> None:
    store = _make_store(backend, tmp_path)
    await store.append(replay_record(1))
    await store.append(replay_record(2))
    await store.append(replay_record(3))

    records, problems = store.load_after("session-1", "owner-1", 1, limit=10)

    assert problems == []
    assert [record.sequence for record in records] == [2, 3]
    assert [record.frame for record in records] == [replay_frame(2), replay_frame(3)]


async def test_store_filters_by_owner(backend: str, tmp_path: Path) -> None:
    store = _make_store(backend, tmp_path)
    await store.append(replay_record(1, principal_id="owner-1"))
    await store.append(replay_record(2, principal_id="owner-2"))

    records, problems = store.load_after("session-1", "owner-1", 0, limit=10)

    assert problems == []
    assert [record.sequence for record in records] == [1]


async def test_store_unknown_session_is_empty(backend: str, tmp_path: Path) -> None:
    store = _make_store(backend, tmp_path)

    assert store.load_after("missing", "owner-1", 0, limit=10) == ([], [])


async def test_store_enforces_retention(backend: str, tmp_path: Path) -> None:
    store = _make_store(backend, tmp_path, max_events=2)
    for sequence in (1, 2, 3):
        await store.append(replay_record(sequence))

    records, problems = store.load_after("session-1", "owner-1", 0, limit=10)

    assert problems == []
    assert [record.sequence for record in records] == [2, 3]


async def test_store_returns_one_record_per_sequence(
    backend: str,
    tmp_path: Path,
) -> None:
    store = _make_store(backend, tmp_path)
    await store.append(replay_record(1, frame=replay_frame(1, "old")))
    await store.append(replay_record(1, frame=replay_frame(1, "new")))

    records, problems = store.load_after("session-1", "owner-1", 0, limit=10)

    assert problems == []
    assert [record.sequence for record in records] == [1]
    assert records[0].frame == replay_frame(1, "new")


async def test_store_delete_session_is_idempotent(
    backend: str,
    tmp_path: Path,
) -> None:
    store = _make_store(backend, tmp_path)
    await store.append(replay_record(1))

    store.delete_session("session-1")
    store.delete_session("session-1")

    assert store.load_after("session-1", "owner-1", 0, limit=10) == ([], [])


async def test_store_skips_corrupt_records(backend: str, tmp_path: Path) -> None:
    store = _make_store(backend, tmp_path)
    await store.append(replay_record(1))

    if backend == "file":
        record_file = tmp_path / "file" / "session-1" / "event-replay.jsonl"
        record_file.write_text(
            record_file.read_text("utf-8") + "{this is not json\n",
            encoding="utf-8",
        )
    else:
        connection = sqlite3.connect(tmp_path / "replay.sqlite")
        try:
            connection.execute(
                "INSERT OR REPLACE INTO event_replay_records"
                "(session_id, sequence, principal_id, recorded_at, frame) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "session-1",
                    2,
                    "owner-1",
                    datetime(2026, 6, 22, 12, 0, 2, tzinfo=UTC).isoformat(),
                    "data: no id\n\n",
                ),
            )
            connection.commit()
        finally:
            connection.close()

    records, problems = store.load_after("session-1", "owner-1", 0, limit=10)

    assert [record.sequence for record in records] == [1]
    assert problems == ["skipped a corrupt event replay record"]


async def test_file_store_read_failure_is_public_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileEventReplayStore(tmp_path / "file", max_events_per_session=10)
    await store.append(replay_record(1))
    original: Callable[..., str] = Path.read_text

    def broken_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if path.name == "event-replay.jsonl":
            raise OSError("private backend path")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", broken_read_text)

    records, problems = store.load_after("session-1", "owner-1", 0, limit=10)

    assert records == []
    assert problems == [_PUBLIC_UNAVAILABLE]


def test_sqlite_store_corrupt_database_is_public_safe(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.sqlite"
    db_path.write_text("not a sqlite database", encoding="utf-8")
    store = SqliteEventReplayStore(db_path, max_events_per_session=10)

    records, problems = store.load_after("session-1", "owner-1", 0, limit=10)

    assert records == []
    assert problems == [_PUBLIC_UNAVAILABLE]


def test_postgres_import_guard_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "psycopg":
            raise ImportError("simulated missing postgres extra")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match=r"loopplane\[postgres\]"):
        PostgresEventReplayStore(
            "postgresql://example.invalid/db", max_events_per_session=10
        )
