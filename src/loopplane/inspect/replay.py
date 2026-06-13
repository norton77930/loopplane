"""Event replay over a recorded stream (contracts/observability.md; FR-050-FR-051).

Feeds a recorded event stream to a supplied sink in recorded order, bracketed by a
start -> complete cycle. It reads recorded events only and starts no run.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loopplane.inspect.base import SequencedEvent


@dataclass(frozen=True)
class ReplaySummary:
    delivered: int
    complete: bool


async def replay(
    events: Sequence[SequencedEvent],
    sink: Callable[[SequencedEvent], Awaitable[None]],
) -> ReplaySummary:
    """Await ``sink`` for each recorded event in recorded order; return a summary
    bracketing the start -> complete cycle. Starts no run (FR-050, FR-051)."""

    delivered = 0
    for event in events:
        await sink(event)
        delivered += 1
    return ReplaySummary(delivered=delivered, complete=True)
