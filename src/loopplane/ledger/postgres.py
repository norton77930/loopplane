"""PostgreSQL USD-ledger storage (optional backend; G22 Phase C, ADR 0010): the running
USD total per ``(principal_id, month)`` in a PostgreSQL database, selected by the host
(a DSN / ``conninfo``).

The ONLY cross-PROCESS-atomic backend: ``add`` is a single
``INSERT … ON CONFLICT … DO UPDATE … RETURNING`` so concurrent adds across sessions AND
processes never lose an increment. ``usd_total`` is ``NUMERIC`` (exact decimal; psycopg
maps NUMERIC ↔ Decimal; never float). Requires the ``loopplane[postgres]`` extra
(``psycopg``); the import is **deferred to construction** so ``loopplane.ledger``
imports without it. Per **ADR 0008** (the sync thread-bridge): async ``add`` off-loads
the (sync) psycopg work via ``anyio.to_thread``; sync ``get`` calls psycopg directly.
The DSN/credential is held but never logged or echoed. Implements the ``UsdLedger``
Protocol
(``base.py``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import anyio

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS ledger ("
    "principal_id TEXT NOT NULL, "
    "month TEXT NOT NULL, "
    "usd_total NUMERIC NOT NULL, "
    "PRIMARY KEY (principal_id, month))"
)


def _require_psycopg() -> Any:
    """The psycopg module, or a clear error naming the extra when it is absent."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised via a simulated absence
        raise RuntimeError(
            "PostgresUsdLedger requires psycopg; install loopplane[postgres]"
        ) from exc
    return psycopg


class PostgresUsdLedger:
    def __init__(self, conninfo: str) -> None:
        self._psycopg = _require_psycopg()
        self._conninfo = conninfo  # a DSN/credential — never logged or echoed

    def _connect(self) -> Any:
        connection = self._psycopg.connect(self._conninfo)
        connection.execute(_SCHEMA)
        connection.commit()
        return connection

    def _add_sync(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
        connection = self._connect()
        try:
            row = connection.execute(
                "INSERT INTO ledger(principal_id, month, usd_total) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (principal_id, month) DO UPDATE "
                "SET usd_total = ledger.usd_total + EXCLUDED.usd_total "
                "RETURNING usd_total",
                (principal_id, month, usd),
            ).fetchone()
            connection.commit()
        finally:
            connection.close()
        return Decimal(row[0])

    async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
        """A single atomic upsert (cross-process safe), off-loaded to a worker thread
        (ADR 0008); returns the new total."""
        return await anyio.to_thread.run_sync(self._add_sync, principal_id, month, usd)

    def get(self, principal_id: str, month: str) -> Decimal:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT usd_total FROM ledger WHERE principal_id = %s AND month = %s",
                (principal_id, month),
            ).fetchone()
        finally:
            connection.close()
        return Decimal(row[0]) if row is not None else Decimal(0)
