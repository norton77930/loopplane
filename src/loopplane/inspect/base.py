"""The shared sequenced-event protocol and a count helper (contracts/observability.md;
FR-003).

Both the Phase-3 ``LoopEvent`` and every Phase-1 ``RuntimeEvent`` satisfy
``SequencedEvent`` structurally (each carries a ``type`` discriminator and a
monotonic ``sequence``), so the timeline, replay, and diagnostics share it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class SequencedEvent(Protocol):
    # Read-only (covariant) so a ``LoopEvent`` (``type: LoopEventType``) and every
    # ``RuntimeEvent`` (``type: <literal>``) satisfy it structurally.
    @property
    def type(self) -> str: ...

    @property
    def sequence(self) -> int: ...


def count_by_type(events: Sequence[SequencedEvent], *types: str) -> int:
    """Count events whose ``type`` is one of ``types``; an unknown type is simply
    not counted (FR-062)."""

    wanted = set(types)
    return sum(1 for event in events if event.type in wanted)
