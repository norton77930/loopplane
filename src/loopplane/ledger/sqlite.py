"""SQLite USD-ledger storage (G22 Phase C, ADR 0010): the running USD total per
``(principal_id, month)`` in a local SQLite database, the :class:`~decimal.Decimal`
stored as TEXT (exact; never REAL/float, which would corrupt money). ``add``
reads-sums-upserts under a per-key lock + a transaction and returns the new total.
Standard-library
``sqlite3`` only — no new dependency, offline.

**Single-process-honest**: the in-process lock gives NO cross-process atomicity — use
:class:`~loopplane.ledger.postgres.PostgresUsdLedger` for the multi-process story.
Implements the ``UsdLedger`` Protocol (``base.py``).
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import anyio

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS ledger ("
    "principal_id TEXT NOT NULL, "
    "month TEXT NOT NULL, "
    "usd_total TEXT NOT NULL, "
    "PRIMARY KEY (principal_id, month))"
)


class SqliteUsdLedger:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._locks: dict[tuple[str, str], anyio.Lock] = {}

    def _lock(self, principal_id: str, month: str) -> anyio.Lock:
        return self._locks.setdefault((principal_id, month), anyio.Lock())

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.execute(_SCHEMA)
        return connection

    async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
        """Read-sum-upsert ``(principal_id, month)`` in one transaction under a per-key
        lock; return the new total (exact Decimal stored as TEXT)."""
        async with self._lock(principal_id, month):
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT usd_total FROM ledger WHERE principal_id = ? AND month = ?",
                    (principal_id, month),
                ).fetchone()
                new_total = (Decimal(row[0]) if row is not None else Decimal(0)) + usd
                connection.execute(
                    "INSERT INTO ledger(principal_id, month, usd_total) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(principal_id, month) DO UPDATE "
                    "SET usd_total = excluded.usd_total",
                    (principal_id, month, str(new_total)),
                )
                connection.commit()
                return new_total
            finally:
                connection.close()

    def get(self, principal_id: str, month: str) -> Decimal:
        if not self._db_path.is_file():
            return Decimal(0)
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT usd_total FROM ledger WHERE principal_id = ? AND month = ?",
                (principal_id, month),
            ).fetchone()
        finally:
            connection.close()
        return Decimal(row[0]) if row is not None else Decimal(0)
