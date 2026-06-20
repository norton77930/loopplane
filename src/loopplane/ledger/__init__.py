"""Durable per-user-monthly USD ledger (G22 Phase C; ADR 0010).

A ``UsdLedger`` Protocol keyed by ``(principal_id, month)`` with an atomic per-key
increment, plus File / SQLite / Postgres backends (mirroring ``loopplane.checkpoint``).
Pure storage — the per-user-monthly cap ENFORCEMENT that consumes it lives in
``loopplane.budget`` (unit 063). Importing this package does not require the
``loopplane[postgres]`` extra (the ``psycopg`` import is deferred to construction).
"""

from loopplane.ledger.base import UsdLedger
from loopplane.ledger.file import FileUsdLedger
from loopplane.ledger.postgres import PostgresUsdLedger
from loopplane.ledger.sqlite import SqliteUsdLedger

__all__ = ["FileUsdLedger", "PostgresUsdLedger", "SqliteUsdLedger", "UsdLedger"]
