"""Conversation recall: the loop's prior-run trail as recalled context
(contracts/recall.md; FR-010-FR-013).

Reads only ``LoopState.run_refs`` (the public, loop-scoped record of the Agent
Runs the loop accumulated) and emits one entry per run, most-recent-first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loopplane.recall.entry import RecalledEntry, RecallSource

if TYPE_CHECKING:
    from loopplane.engineering import LoopState


def conversation_recall(*, limit: int = 10) -> RecallSource:
    """A recall source over the loop's prior runs, most-recent-first, bounded by
    ``limit`` (FR-010-FR-013). Empty ``run_refs`` yields no entries (FR-013)."""

    def source(state: LoopState) -> tuple[RecalledEntry, ...]:
        refs = list(reversed(state.run_refs))[:limit]
        return tuple(
            RecalledEntry(
                text=f"prior run {ref.session_id}: {ref.termination_reason}",
                origin="conversation",
                identifier=ref.session_id,
            )
            for ref in refs
        )

    return source
