"""The outcome reader (contracts/packs.md; FR-002).

A single, read-only extraction of the public ``RunOutcome`` / ``LoopState``
surface every pack uses: the terminal reason, the final assistant text, and the
artifact references. It reads only the public surface and never a Phase-1/2
internal, and never mutates the inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loopplane.model import TextBlock

if TYPE_CHECKING:
    from loopplane.engineering import LoopState
    from loopplane.host import RunOutcome


@dataclass(frozen=True)
class OutcomeView:
    """The stable, public-safe view of a run outcome a pack reads (FR-002)."""

    terminal_reason: str
    final_text: str
    artifact_references: tuple[str, ...]


def read_outcome(outcome: RunOutcome, state: LoopState) -> OutcomeView:
    """Extract the public view from a ``RunOutcome`` + ``LoopState``.

    ``final_text`` is the concatenated ``TextBlock`` text of the **last
    ``assistant``** history entry (empty when there is none), giving a
    deterministic selection across multiple fragments (FR-002, edge case).
    """

    final_text = ""
    for entry in reversed(outcome.history):
        if entry.role == "assistant":
            final_text = "".join(
                block.text for block in entry.blocks if isinstance(block, TextBlock)
            )
            break
    artifact_references = tuple(ref.reference for ref in state.artifacts)
    return OutcomeView(
        terminal_reason=outcome.termination_reason,
        final_text=final_text,
        artifact_references=artifact_references,
    )
