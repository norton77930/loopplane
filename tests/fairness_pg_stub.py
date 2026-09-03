"""Offline in-memory psycopg stub for PostgresTurnPermitStore (086)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

_LOCK = threading.RLock()
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
        if sql.startswith("INSERT INTO turn_meta"):
            self._store["meta"].setdefault("last_started", None)
            self._store["meta"].setdefault("consecutive", 0)
            return _FakeCursor([])
        if sql.startswith("SELECT id FROM turn_meta"):
            return _FakeCursor([(1,)])
        if sql.startswith("SELECT last_started, consecutive"):
            meta = self._store["meta"]
            return _FakeCursor([(meta.get("last_started"), meta.get("consecutive", 0))])
        if sql.startswith("SELECT permit_id, principal_id, holder_id, expires_at"):
            return _FakeCursor(list(self._store["permits"].values()))
        if sql.startswith("SELECT waiter_id, principal_id"):
            rows = list(self._store["waiters"].values())
            rows.sort(key=lambda row: (row[6], row[0]))
            return _FakeCursor(rows)
        if sql.startswith("DELETE FROM turn_waiters"):
            self._store["waiters"].clear()
            return _FakeCursor([])
        if sql.startswith("DELETE FROM turn_permits"):
            self._store["permits"].clear()
            return _FakeCursor([])
        if sql.startswith("UPDATE turn_meta SET last_started"):
            self._store["meta"]["last_started"] = args[0]
            self._store["meta"]["consecutive"] = args[1]
            return _FakeCursor([])
        if sql.startswith("INSERT INTO turn_permits"):
            permit_id, principal_id, holder_id, expires_at = args
            self._store["permits"][permit_id] = (
                permit_id,
                principal_id,
                holder_id,
                expires_at,
            )
            return _FakeCursor([])
        if sql.startswith("INSERT INTO turn_waiters"):
            (
                waiter_id,
                principal_id,
                holder_id,
                active_cap,
                consecutive_cap,
                ttl_seconds,
                enqueued_at,
            ) = args
            self._store["waiters"][waiter_id] = (
                waiter_id,
                principal_id,
                holder_id,
                active_cap,
                consecutive_cap,
                ttl_seconds,
                enqueued_at,
            )
            return _FakeCursor([])
        if sql.startswith("UPDATE turn_permits SET expires_at"):
            expires_at, permit_id, holder_id, now = args
            row = self._store["permits"].get(permit_id)
            if row is None or row[2] != holder_id or row[3] <= now:
                return _FakeCursor([])
            self._store["permits"][permit_id] = (row[0], row[1], row[2], expires_at)
            return _FakeCursor([(permit_id,)])
        raise AssertionError(f"unexpected SQL in the fairness stub: {sql!r}")

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


def patch_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    def fake_connect(conninfo: str, *args: Any, **kwargs: Any) -> _FakeConnection:
        store = _STORES.setdefault(
            conninfo,
            {
                "meta": {"last_started": None, "consecutive": 0},
                "permits": {},
                "waiters": {},
            },
        )
        return _FakeConnection(store)

    monkeypatch.setattr(psycopg, "connect", fake_connect)
