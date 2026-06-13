"""Knowledge-index recall: a named, host-implemented index contract with an
in-memory, public-safe reference (contracts/recall.md; FR-040-FR-043).

``knowledge_recall`` derives a deterministic query from the public Loop State,
looks it up through a host ``KnowledgeIndex``, and adapts the results into recalled
context. ``InMemoryKnowledgeIndex`` is a deterministic reference double — empty by
default, carrying no domain data, and shipping no external or remote backend.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from loopplane.recall.entry import QueryFn, RecalledEntry, RecallSource, default_query

if TYPE_CHECKING:
    from loopplane.engineering import LoopState


@dataclass(frozen=True)
class KnowledgeEntry:
    """A public-safe unit of host knowledge (FR-040)."""

    identifier: str
    text: str


class KnowledgeIndex(Protocol):
    """A host-implemented deterministic lookup from a query to knowledge entries
    (FR-040)."""

    def lookup(self, query: str, *, limit: int) -> Sequence[KnowledgeEntry]: ...


class InMemoryKnowledgeIndex:
    """A deterministic, public-safe reference index — empty by default, no domain
    data, no external backend (FR-041)."""

    def __init__(self, entries: Sequence[KnowledgeEntry] = ()) -> None:
        self._entries = tuple(entries)

    def lookup(self, query: str, *, limit: int) -> Sequence[KnowledgeEntry]:
        query_tokens = _tokens(query)
        matched = [
            entry for entry in self._entries if _tokens(entry.text) & query_tokens
        ]
        return matched[:limit]


def knowledge_recall(
    index: KnowledgeIndex, *, query: QueryFn = default_query, limit: int = 5
) -> RecallSource:
    """A recall source over a host knowledge index; the query is derived
    deterministically from the Loop State (FR-042). A raising index contributes
    nothing (NFR-005)."""

    def source(state: LoopState) -> tuple[RecalledEntry, ...]:
        try:
            results = index.lookup(query(state), limit=limit)
        except Exception:  # noqa: BLE001 - fail safe: a raising index contributes nothing
            return ()
        return tuple(
            RecalledEntry(
                text=entry.text, origin="knowledge", identifier=entry.identifier
            )
            for entry in results
        )

    return source


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))
