"""Memory as an augmentation source for prompt assembly (FR-072, FR-073)."""

from __future__ import annotations

from loopplane.memory.selection import select_entries
from loopplane.memory.store import MemoryStore


class MemoryAugmentation:
    def __init__(self, store: MemoryStore, *, limit: int = 5) -> None:
        self._store = store
        self._limit = limit

    def augment_for(self, prompt: str) -> str | None:
        entries = select_entries(self._store.list_entries(), prompt, limit=self._limit)
        if not entries:
            return None
        return "\n".join(
            f"[memory:{entry.type}] {entry.name}: {entry.body}" for entry in entries
        )

    def re_establish(self) -> str | None:
        """Memory re-selects every turn, so compaction needs no special
        re-establishment.
        """
        return None
