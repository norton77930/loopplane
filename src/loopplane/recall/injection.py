"""The memory injection policy: compose recall sources, apply the budget, and
produce a Phase-3 ``InputSource`` (contracts/injection-boundary.md; FR-050,
FR-054, FR-055).

``assemble_recall`` runs each source over the public Loop State, de-duplicates by
identifier, applies the Retrieval Budget, and formats a bounded preamble.
``build_recall_input`` wraps a base ``InputSource`` so the loop's
first prompt is prefixed with the recalled preamble — never mutating the base,
the state, or any store.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loopplane.recall.budget import RetrievalBudget, apply_budget
from loopplane.recall.entry import RecalledEntry, RecallSource

if TYPE_CHECKING:
    from loopplane.engineering import InputSource, LoopState, Prompt


@dataclass(frozen=True)
class RecallAssembly:
    """The composed recall result: a bounded preamble, the kept entries, the
    truncation count, and diagnostics for sources that contributed nothing."""

    preamble: str
    entries: tuple[RecalledEntry, ...]
    dropped: int
    skipped: tuple[str, ...]


def assemble_recall(
    sources: Sequence[RecallSource], budget: RetrievalBudget, *, state: LoopState
) -> RecallAssembly:
    """Compose sources in order, de-duplicate by identifier, apply the budget, and
    format a bounded preamble.

    Duplicates collapse to the first (highest-precedence) occurrence; a source that
    raises contributes nothing and its label lands in ``skipped`` (fail-safe;
    NFR-005). Reads only the public Loop State and mutates nothing (NFR-006).
    """

    collected: list[RecalledEntry] = []
    skipped: list[str] = []
    for index, source in enumerate(sources):
        try:
            collected.extend(source(state))
        except Exception:  # noqa: BLE001 - fail safe: a raising source is skipped
            skipped.append(f"source[{index}]")
    result = apply_budget(_dedupe(collected), budget)
    return RecallAssembly(
        preamble=_format_preamble(result.kept),
        entries=result.kept,
        dropped=result.dropped,
        skipped=tuple(skipped),
    )


def build_recall_input(
    base: InputSource,
    sources: Sequence[RecallSource],
    budget: RetrievalBudget,
    *,
    state: LoopState,
) -> InputSource:
    """Wrap ``base`` so ``initial()`` prepends the bounded recalled preamble to a
    string base prompt (FR-054). An empty recall, or a non-string base prompt,
    yields the base prompt unchanged (FR-055)."""

    return _RecallInput(base=base, sources=tuple(sources), budget=budget, state=state)


def _dedupe(entries: Sequence[RecalledEntry]) -> list[RecalledEntry]:
    """Drop duplicate identifiers keeping the first (highest-precedence)
    occurrence; ``identifier=None`` entries are never collapsed (FR-051)."""

    seen: set[str] = set()
    out: list[RecalledEntry] = []
    for entry in entries:
        if entry.identifier is None:
            out.append(entry)
            continue
        if entry.identifier in seen:
            continue
        seen.add(entry.identifier)
        out.append(entry)
    return out


def _format_preamble(entries: Sequence[RecalledEntry]) -> str:
    if not entries:
        return ""
    lines = ["[recalled context]"]
    lines.extend(f"- {entry.text}" for entry in entries)
    return "\n".join(lines)


@dataclass(frozen=True)
class _RecallInput:
    """A Phase-3 ``InputSource`` that injects recalled context ahead of a base
    input. Composition only — it never mutates the base, state, or a store."""

    base: InputSource
    sources: tuple[RecallSource, ...]
    budget: RetrievalBudget
    state: LoopState

    def initial(self) -> Prompt:
        assembly = assemble_recall(self.sources, self.budget, state=self.state)
        base_prompt = self.base.initial()
        if not assembly.preamble:
            return base_prompt
        if isinstance(base_prompt, str):
            return f"{assembly.preamble}\n\n{base_prompt}"
        # A ContentBlock-sequence base prompt is passed through unchanged this
        # phase (recall augments string prompts).
        return base_prompt
