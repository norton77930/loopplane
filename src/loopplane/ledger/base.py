"""The USD-ledger boundary (G22 Phase C; ADR 0010): a Protocol over a durable,
per-``(principal_id, month)`` USD accumulator. Implementations: ``FileUsdLedger`` (the
default, ``file.py``), ``SqliteUsdLedger`` (``sqlite.py``), and ``PostgresUsdLedger``
(``postgres.py``).

A sibling to ``loopplane.checkpoint`` — deliberately **not** new methods on the
append-only, session-keyed ``CheckpointStore`` (the wrong shape for an atomic
cross-session counter). Money is exact :class:`decimal.Decimal` (never float).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class UsdLedger(Protocol):
    """A durable per-``(principal_id, month)`` USD accumulator behind a storage-agnostic
    seam (ADR 0010)."""

    async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
        """Atomically add ``usd`` to the running total for ``(principal_id, month)`` and
        return the **new post-increment total**. The read-modify-write is atomic per
        ``(principal_id, month)`` across sessions, so concurrent adds never lose an
        increment. ``month`` is an opaque caller-derived ``"YYYY-MM"`` string (the
        ledger holds no clock); ``usd`` is exact :class:`~decimal.Decimal`. Returning
        the new total lets a caller cap-check in one round-trip without a separate read.
        """
        ...

    def get(self, principal_id: str, month: str) -> Decimal:
        """The accumulated USD for ``(principal_id, month)``; an unseen key yields
        ``Decimal(0)``."""
        ...
