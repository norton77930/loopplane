"""Per-session event sequence allocation: monotonic and gap-free within a
process lifetime (contracts/runtime-events.md envelope; FR-060).
"""

from __future__ import annotations


class EventSequencer:
    def __init__(self, start: int = 1) -> None:
        self._next = start

    def next_sequence(self) -> int:
        value = self._next
        self._next += 1
        return value
