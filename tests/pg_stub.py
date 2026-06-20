"""An offline, in-memory psycopg stub for the PostgresCheckpointStore tests (060).

Faithfully models the small set of SQL the backend issues (CREATE TABLE / INSERT /
the two SELECTs / DELETE) over an in-memory row store keyed by ``conninfo``, so the
checkpoint contract suite runs against Postgres with NO running database. Use a
unique ``conninfo`` per test (e.g. from ``tmp_path``) so stores do not bleed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

# conninfo -> list of (session_id, sequence, recorded_at, data) rows
_STORES: dict[str, list[tuple[Any, ...]]] = {}


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class _FakeConnection:
    def __init__(self, store: list[tuple[Any, ...]]) -> None:
        self._store = store

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeCursor:
        args = params or ()
        if sql.startswith("CREATE TABLE"):
            return _FakeCursor([])
        if sql.startswith("INSERT INTO records"):
            self._store.append(tuple(args))
            return _FakeCursor([])
        if sql.startswith("SELECT data FROM records WHERE session_id"):
            sid = args[0]
            matched = sorted(
                (r for r in self._store if r[0] == sid), key=lambda r: r[1]
            )
            return _FakeCursor([(r[3],) for r in matched])
        if sql.startswith("SELECT session_id, recorded_at, data"):
            matched = sorted(self._store, key=lambda r: (r[0], r[1]))
            return _FakeCursor([(r[0], r[2], r[3]) for r in matched])
        if sql.startswith("DELETE FROM records WHERE session_id"):
            sid = args[0]
            self._store[:] = [r for r in self._store if r[0] != sid]
            return _FakeCursor([])
        raise AssertionError(f"unexpected SQL in the psycopg stub: {sql!r}")

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


def patch_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``psycopg.connect`` to the in-memory stub (offline; no real DB)."""
    import psycopg

    def fake_connect(conninfo: str, *args: Any, **kwargs: Any) -> _FakeConnection:
        return _FakeConnection(_STORES.setdefault(conninfo, []))

    monkeypatch.setattr(psycopg, "connect", fake_connect)


def corrupt(conninfo: str, session_id: str, sequence: int = 9999) -> None:
    """Inject a corrupt data row directly into the in-memory store."""
    _STORES.setdefault(conninfo, []).append(
        (
            session_id,
            sequence,
            datetime(2026, 6, 13, 12, tzinfo=UTC).isoformat(),
            "{this is not valid json",
        )
    )
