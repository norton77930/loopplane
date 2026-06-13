"""The retrieval budget and its explicit, order-stable truncation
(contracts/recall.md; FR-052, FR-053).

``apply_budget`` keeps recalled entries in order until a bound would be exceeded,
then truncates — returning the kept entries plus an explicit dropped count, never
a silent drop.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from loopplane.recall.entry import RecalledEntry


@dataclass(frozen=True)
class RetrievalBudget:
    """An explicit, deterministic bound on injected recall. A ``None`` axis is
    unbounded (FR-052)."""

    max_entries: int | None = None
    max_chars: int | None = None


@dataclass(frozen=True)
class BudgetResult:
    """The kept entries and how many were truncated (FR-053)."""

    kept: tuple[RecalledEntry, ...]
    dropped: int


def apply_budget(
    entries: Sequence[RecalledEntry], budget: RetrievalBudget
) -> BudgetResult:
    """Keep entries in order until a bound would be exceeded, then stop. The
    remainder is dropped and counted (order-stable, explicit; FR-053)."""

    kept: list[RecalledEntry] = []
    chars = 0
    for entry in entries:
        if budget.max_entries is not None and len(kept) >= budget.max_entries:
            break
        if budget.max_chars is not None and chars + len(entry.text) > budget.max_chars:
            break
        kept.append(entry)
        chars += len(entry.text)
    return BudgetResult(kept=tuple(kept), dropped=len(entries) - len(kept))
