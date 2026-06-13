"""The debug timeline — sequence-ordered entries with start/complete pairing
(contracts/observability.md; FR-040-FR-041).

Orders entries by the events' monotonic ``sequence`` (never wall-clock), pairs a
started event with its completion, and marks an unpaired start as an open span.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loopplane.inspect.base import SequencedEvent

_PAIR_KEY = {
    "loop_started": "loop",
    "loop_completed": "loop",
    "loop_failed": "loop",
    "loop_iteration_started": "iteration",
    "loop_iteration_completed": "iteration",
    "tool-call-started": "tool",
    "tool-call-completed": "tool",
}
_IS_START = {"loop_started", "loop_iteration_started", "tool-call-started"}
_IS_END = {
    "loop_completed",
    "loop_failed",
    "loop_iteration_completed",
    "tool-call-completed",
}
_DEPTH = {
    "loop_started": 0,
    "loop_completed": 0,
    "loop_failed": 0,
    "loop_iteration_started": 1,
    "loop_iteration_completed": 1,
    "validation_completed": 1,
    "evaluation_completed": 1,
    "retry_scheduled": 1,
    "repair_requested": 1,
    "human_review_requested": 1,
    "tool-call-started": 3,
    "tool-call-completed": 3,
    "turn-completed": 3,
}


@dataclass(frozen=True)
class TimelineEntry:
    sequence: int
    type: str
    depth: int
    open: bool = False


@dataclass(frozen=True)
class Timeline:
    entries: tuple[TimelineEntry, ...]


def build_timeline(events: Sequence[SequencedEvent]) -> Timeline:
    """Order entries by ``sequence`` (stable), pair started/completed spans, and
    mark an unpaired start ``open`` (FR-040, FR-041)."""

    ordered = sorted(events, key=lambda event: event.sequence)
    entries = [
        TimelineEntry(
            sequence=event.sequence, type=event.type, depth=_DEPTH.get(event.type, 2)
        )
        for event in ordered
    ]
    stacks: dict[str, list[int]] = {}
    for index, event in enumerate(ordered):
        if event.type in _IS_START:
            entries[index] = replace(entries[index], open=True)
            stacks.setdefault(_PAIR_KEY[event.type], []).append(index)
        elif event.type in _IS_END:
            stack = stacks.get(_PAIR_KEY[event.type])
            if stack:
                start_index = stack.pop()
                entries[start_index] = replace(entries[start_index], open=False)
    return Timeline(entries=tuple(entries))
