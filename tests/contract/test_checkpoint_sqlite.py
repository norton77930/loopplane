"""Shared contract suite over both checkpoint backends (contracts/checkpoint-store.md).

One parametrized suite drives ``FileCheckpointStore`` and ``SqliteCheckpointStore``
through the ``CheckpointStore`` Protocol, asserting that append/load ordering, value
round-trip, corrupt-record skipping, missing-store empty listing, recency-ordered
listing, and per-session append serialization are equivalent across both backends
(FR-006, FR-007). Backend-specific mechanics (how a corrupt record is injected) live in
the parametrized fixture; every test body is backend-agnostic.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
import pytest

from loopplane.checkpoint import (
    CheckpointStore,
    FileCheckpointStore,
    PostgresCheckpointStore,
    SessionMetaRecord,
    SqliteCheckpointStore,
    UserInputRecord,
    rebuild_session,
)
from loopplane.model.content import TextBlock
from tests import pg_stub

pytestmark = pytest.mark.anyio

_T0 = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)


def _meta(
    session_id: str,
    sequence: int = 1,
    recorded_at: datetime = _T0,
    principal_id: str | None = None,
) -> SessionMetaRecord:
    return SessionMetaRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=recorded_at,
        payload={
            "created_at": recorded_at,
            "label": "test session",
            "principal_id": principal_id,
        },
    )


def _user(
    session_id: str, sequence: int, text: str, recorded_at: datetime = _T0
) -> UserInputRecord:
    return UserInputRecord(
        session_id=session_id,
        sequence=sequence,
        recorded_at=recorded_at,
        payload={"blocks": [TextBlock(text=text)]},
    )


@dataclass
class _Backend:
    """A backend under test: a factory for a fresh store on the same backing, plus a
    backend-specific way to inject a corrupt record into a session."""

    open: Callable[[], CheckpointStore]
    corrupt: Callable[[str], None]


@pytest.fixture(params=["file", "sqlite", "postgres"])
def backend(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> _Backend:
    if request.param == "file":

        def corrupt_file(session_id: str) -> None:
            record_file = next((tmp_path / session_id).glob("*.jsonl"))
            with record_file.open("a", encoding="utf-8") as handle:
                handle.write("{this is not valid json\n")

        return _Backend(
            open=lambda: FileCheckpointStore(tmp_path), corrupt=corrupt_file
        )

    if request.param == "postgres":
        pytest.importorskip("psycopg")
        pg_stub.patch_psycopg(monkeypatch)
        conninfo = f"postgresql://stub/{tmp_path.name}"
        return _Backend(
            open=lambda: PostgresCheckpointStore(conninfo),
            corrupt=lambda session_id: pg_stub.corrupt(conninfo, session_id),
        )

    db_path = tmp_path / "checkpoints.sqlite3"

    def corrupt_sqlite(session_id: str) -> None:
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                "INSERT INTO records(session_id, sequence, recorded_at, data) "
                "VALUES (?, ?, ?, ?)",
                (session_id, 9999, _T0.isoformat(), "{this is not valid json"),
            )
            connection.commit()
        finally:
            connection.close()

    return _Backend(open=lambda: SqliteCheckpointStore(db_path), corrupt=corrupt_sqlite)


async def test_append_then_load_returns_records_in_order(backend: _Backend) -> None:
    store = backend.open()
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "hello"))
    await store.append(_user("s1", 3, "again"))

    records, problems = backend.open().load("s1")

    assert problems == []
    assert [r.record_kind for r in records] == [
        "session-meta",
        "user-input",
        "user-input",
    ]
    assert [r.sequence for r in records] == [1, 2, 3]


async def test_load_round_trips_record_values(backend: _Backend) -> None:
    store = backend.open()
    await store.append(_meta("s1"))
    original = _user("s1", 2, "round trip")
    await store.append(original)

    records, _ = backend.open().load("s1")

    assert records[1] == original


async def test_corrupt_record_is_skipped_and_reported(backend: _Backend) -> None:
    store = backend.open()
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "first"))
    backend.corrupt("s1")
    await store.append(_user("s1", 3, "second"))

    records, problems = backend.open().load("s1")

    assert len(problems) == 1
    assert [r.record_kind for r in records] == [
        "session-meta",
        "user-input",
        "user-input",
    ]


def test_missing_store_is_empty(backend: _Backend) -> None:
    store = backend.open()  # nothing written yet
    assert store.load("nope") == ([], [])
    assert store.list_sessions() == []


async def test_lists_sessions_most_recent_first(backend: _Backend) -> None:
    store = backend.open()
    await store.append(_meta("older", 1, _T0))
    await anyio.sleep(0.02)
    await store.append(_meta("newer", 1, _T0 + timedelta(seconds=1)))
    await anyio.sleep(0.02)
    await store.append(_user("older", 2, "a late message", _T0 + timedelta(seconds=2)))

    summaries = store.list_sessions()

    assert [summary.session_id for summary in summaries] == ["older", "newer"]
    assert summaries[0].label == "test session"
    assert summaries[0].created_at == _T0


async def test_concurrent_appends_to_one_session_all_land(backend: _Backend) -> None:
    store = backend.open()
    await store.append(_meta("s1"))

    async def writer(start: int) -> None:
        for offset in range(25):
            await store.append(_user("s1", start + offset, f"m{start + offset}"))

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(writer, 100)
        task_group.start_soon(writer, 200)

    records, problems = backend.open().load("s1")

    assert problems == []
    assert len(records) == 51  # meta + 2 * 25


async def test_list_sessions_surfaces_principal_id(backend: _Backend) -> None:
    store = backend.open()
    await store.append(_meta("s1", principal_id="alice"))

    (summary,) = backend.open().list_sessions()

    assert summary.principal_id == "alice"


async def test_set_title_latest_wins(backend: _Backend) -> None:
    # 030: rename appends a fresh session-meta; the latest title wins in the
    # listing and on rebuild, with creation time + owner preserved.
    store = backend.open()
    await store.append(_meta("s1", principal_id="alice"))
    await store.set_title("s1", "First")
    await store.set_title("s1", "Second")

    (summary,) = backend.open().list_sessions()
    assert summary.label == "Second"
    assert summary.created_at == _T0
    assert summary.principal_id == "alice"

    records, _ = backend.open().load("s1")
    assert rebuild_session(records).label == "Second"


async def test_delete_session_removes_and_is_idempotent(backend: _Backend) -> None:
    # 030: deletion is durable and idempotent on an unknown id.
    store = backend.open()
    await store.append(_meta("s1"))
    await store.append(_user("s1", 2, "hello"))
    assert [s.session_id for s in backend.open().list_sessions()] == ["s1"]

    backend.open().delete_session("s1")
    assert backend.open().list_sessions() == []
    assert backend.open().load("s1") == ([], [])

    backend.open().delete_session("s1")  # idempotent — no error on a second delete
