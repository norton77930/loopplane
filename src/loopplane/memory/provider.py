"""Memory as an augmentation source for prompt assembly (FR-072, FR-073)."""

from __future__ import annotations

from collections.abc import Sequence

from loopplane.memory.selection import select_entries
from loopplane.memory.store import MemoryEntry, MemoryStore


def _render(entries: Sequence[MemoryEntry], prompt: str, *, limit: int) -> str | None:
    selected = select_entries(entries, prompt, limit=limit)
    if not selected:
        return None
    return "\n".join(
        f"[memory:{entry.type}] {entry.name}: {entry.body}" for entry in selected
    )


class MemoryAugmentation:
    def __init__(self, store: MemoryStore, *, limit: int = 5) -> None:
        self._store = store
        self._limit = limit

    def augment_for(self, prompt: str) -> str | None:
        return _render(self._store.list_entries(), prompt, limit=self._limit)

    def re_establish(self) -> str | None:
        """Memory re-selects every turn, so compaction needs no special
        re-establishment.
        """
        return None


class MemorySnapshotAugmentation:
    """Prompt augmentation over an immutable per-session memory snapshot."""

    def __init__(self, entries: Sequence[MemoryEntry], *, limit: int = 5) -> None:
        self._entries = tuple(entries)
        self._limit = limit

    def augment_for(self, prompt: str) -> str | None:
        return _render(self._entries, prompt, limit=self._limit)

    def re_establish(self) -> None:
        return None
