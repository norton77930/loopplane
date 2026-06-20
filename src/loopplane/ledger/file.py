"""Filesystem USD-ledger storage (the default backend; G22 Phase C, ADR 0010): the
running USD total per ``(principal_id, month)`` as a small JSON file under a
host-overridable base directory, the :class:`~decimal.Decimal` stored as a string
(exact; never float). ``add`` reads-sums-writes-flushes under a per-key lock.

**Single-process-honest**: the in-process lock gives NO cross-process atomicity — use
:class:`~loopplane.ledger.postgres.PostgresUsdLedger` for the multi-process story.
Implements the ``UsdLedger`` Protocol (``base.py``).
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import anyio


class FileUsdLedger:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._locks: dict[tuple[str, str], anyio.Lock] = {}

    def _lock(self, principal_id: str, month: str) -> anyio.Lock:
        return self._locks.setdefault((principal_id, month), anyio.Lock())

    def _file(self, principal_id: str, month: str) -> Path:
        # A content hash keeps an arbitrary principal_id (an opaque claim value, not a
        # safe UUID) from traversing the filesystem.
        digest = hashlib.sha256(f"{principal_id}\x00{month}".encode()).hexdigest()
        return self._base / f"{digest}.json"

    async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal:
        """Add ``usd`` to ``(principal_id, month)`` and flush before returning the new
        total; serialized by a per-key lock (single-process-honest)."""
        async with self._lock(principal_id, month):
            path = self._file(principal_id, month)
            new_total = self._read(path) + usd
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {
                        "principal_id": principal_id,
                        "month": month,
                        "usd_total": str(new_total),
                    },
                    handle,
                )
                handle.flush()
            return new_total

    def get(self, principal_id: str, month: str) -> Decimal:
        return self._read(self._file(principal_id, month))

    @staticmethod
    def _read(path: Path) -> Decimal:
        if not path.is_file():
            return Decimal(0)
        return Decimal(str(json.loads(path.read_text("utf-8"))["usd_total"]))
