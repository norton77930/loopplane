"""Memory-entry recall: durable entries selected through the Phase-1
deterministic selection (contracts/recall.md; FR-030-FR-032).

Reuses ``loopplane.memory.select_entries`` (selection authority stays in Phase-1)
and adapts each selected entry into a Recalled Context Entry — re-implementing no
ranking of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from loopplane.memory import select_entries
from loopplane.recall.entry import QueryFn, RecalledEntry, RecallSource, default_query

if TYPE_CHECKING:
    from loopplane.engineering import LoopState
    from loopplane.memory import MemoryEntry


def memory_entry_recall(
    entries: Sequence[MemoryEntry],
    *,
    query: QueryFn = default_query,
    limit: int = 5,
) -> RecallSource:
    """A recall source that selects durable memory entries via the Phase-1
    ``select_entries`` and adapts them into recalled context (FR-030-FR-032)."""

    def source(state: LoopState) -> tuple[RecalledEntry, ...]:
        selected = select_entries(entries, query(state), limit=limit)
        return tuple(
            RecalledEntry(
                text=_format_entry(entry), origin="memory", identifier=entry.name
            )
            for entry in selected
        )

    return source


def _format_entry(entry: MemoryEntry) -> str:
    segments = [
        segment for segment in (entry.name, entry.description, entry.body) if segment
    ]
    return " — ".join(segments)
