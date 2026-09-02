"""Offline in-memory psycopg stub for PostgresAdmissionStore (085)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

_LOCK = threading.RLock()
# conninfo -> {principals: set[str], grants: dict[grant_id, tuple]}
_STORES: dict[str, dict[str, Any]] = {}


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _FakeConnection:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with _LOCK:
            yield

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeCursor:
        with _LOCK:
            return self._execute(sql, params)

    def _execute(self, sql: str, params: tuple[Any, ...] | None) -> _FakeCursor:
        args = params or ()
        if sql.startswith("CREATE TABLE"):
            return _FakeCursor([])
        if sql.startswith("INSERT INTO admission_principals"):
            self._store["principals"].add(args[0])
            return _FakeCursor([])
        if sql.startswith("SELECT principal_id FROM admission_principals"):
            pid = args[0]
            if pid in self._store["principals"]:
                return _FakeCursor([(pid,)])
            return _FakeCursor([])
        if sql.startswith("DELETE FROM admission_grants WHERE principal_id"):
            principal_id, now = args[0], args[1]
            grants: dict[str, tuple[Any, ...]] = self._store["grants"]
            drop = [
                gid
                for gid, row in grants.items()
                if row[1] == principal_id and row[3] <= now
            ]
            for gid in drop:
                del grants[gid]
            return _FakeCursor([])
        if sql.startswith("SELECT reserves_outstanding"):
            principal_id = args[0]
            rows = [
                (row[4],)
                for row in self._store["grants"].values()
                if row[1] == principal_id
            ]
            return _FakeCursor(rows)
        if sql.startswith("INSERT INTO admission_grants"):
            grant_id, principal_id, holder_id, expires_at, outstanding = args
            self._store["grants"][grant_id] = (
                grant_id,
                principal_id,
                holder_id,
                expires_at,
                outstanding,
            )
            return _FakeCursor([])
        if sql.startswith("UPDATE admission_grants SET expires_at"):
            expires_at, grant_id, holder_id, now = args
            row = self._store["grants"].get(grant_id)
            if row is None or row[2] != holder_id or row[3] <= now:
                return _FakeCursor([])
            self._store["grants"][grant_id] = (
                row[0],
                row[1],
                row[2],
                expires_at,
                row[4],
            )
            return _FakeCursor([(grant_id,)])
        if sql.startswith("DELETE FROM admission_grants WHERE grant_id"):
            grant_id, holder_id = args
            row = self._store["grants"].get(grant_id)
            if row is not None and row[2] == holder_id:
                del self._store["grants"][grant_id]
            return _FakeCursor([])
        raise AssertionError(f"unexpected SQL in the admission stub: {sql!r}")

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


def patch_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    def fake_connect(conninfo: str, *args: Any, **kwargs: Any) -> _FakeConnection:
        store = _STORES.setdefault(conninfo, {"principals": set(), "grants": {}})
        return _FakeConnection(store)

    monkeypatch.setattr(psycopg, "connect", fake_connect)
