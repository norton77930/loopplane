"""An offline, in-memory psycopg stub for the PostgresUsdLedger tests (062).

Faithfully models the SQL the backend issues — CREATE TABLE / the atomic
``INSERT … ON CONFLICT … DO UPDATE SET usd_total = ledger.usd_total + EXCLUDED.usd_total
RETURNING usd_total`` accumulate-and-return / SELECT — over an in-memory
``(principal_id, month) -> Decimal`` store keyed by ``conninfo``, with no running DB.
The upsert mutation is guarded by a process-wide lock so it models the real DB's
row-level atomicity even under concurrent ``anyio.to_thread`` adds. Use a unique
``conninfo`` per
test (e.g. from ``tmp_path``) so stores do not bleed.
"""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

import pytest

# conninfo -> {(principal_id, month): Decimal}
_STORES: dict[str, dict[tuple[str, str], Decimal]] = {}
_LOCK = threading.Lock()  # models the DB's atomic upsert across to_thread workers


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class _FakeConnection:
    def __init__(self, store: dict[tuple[str, str], Decimal]) -> None:
        self._store = store

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> _FakeCursor:
        args = params or ()
        if sql.startswith("CREATE TABLE"):
            return _FakeCursor([])
        if sql.startswith("INSERT INTO ledger"):
            principal_id, month, usd = args
            with _LOCK:  # atomic read-modify-write, like the DB's ON CONFLICT upsert
                key = (principal_id, month)
                new_total = self._store.get(key, Decimal(0)) + Decimal(usd)
                self._store[key] = new_total
            return _FakeCursor([(new_total,)])
        if sql.startswith("SELECT usd_total FROM ledger"):
            principal_id, month = args
            value = self._store.get((principal_id, month))
            return _FakeCursor([(value,)] if value is not None else [])
        raise AssertionError(f"unexpected SQL in the usd-ledger stub: {sql!r}")

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


def patch_psycopg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``psycopg.connect`` to the in-memory stub (offline; no real DB)."""
    import psycopg

    def fake_connect(conninfo: str, *args: Any, **kwargs: Any) -> _FakeConnection:
        return _FakeConnection(_STORES.setdefault(conninfo, {}))

    monkeypatch.setattr(psycopg, "connect", fake_connect)
