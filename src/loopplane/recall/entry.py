"""The recalled-context value type and the recall-source contract
(contracts/recall.md; FR-001, FR-002).

A ``RecalledEntry`` is a public-safe unit of recalled context. A ``RecallSource``
is a pure callable that, given the public Loop State, returns an ordered, bounded
tuple of entries — reading only public surfaces and mutating nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loopplane.engineering import LoopState


@dataclass(frozen=True)
class RecalledEntry:
    """A public-safe unit of recalled context (FR-001).

    ``identifier`` is a stable id used by the injection policy to de-duplicate
    across sources; ``None`` means the entry is never collapsed.
    """

    text: str
    origin: str
    identifier: str | None = None


RecallSource = Callable[["LoopState"], tuple[RecalledEntry, ...]]
QueryFn = Callable[["LoopState"], str]


def default_query(state: LoopState) -> str:
    """A deterministic, public-safe query derived from the public Loop State —
    the loop id plus the latest validation reason if present (FR-042)."""

    validation = state.latest_validation
    reason = validation.reason if validation is not None and validation.reason else ""
    return f"{state.loop_id} {reason}".strip()
