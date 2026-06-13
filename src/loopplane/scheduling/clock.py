"""The injectable Clock (contracts/drivers.md; FR-010–FR-012).

The Scheduler reads time only through a ``Clock``. A ``VirtualClock`` drives
deterministic tests with no real sleeping; a ``RealClock`` is a thin
``time.monotonic`` adapter for production, with identical scheduler decisions.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """A monotonic time source in seconds."""

    def now(self) -> float: ...


class VirtualClock:
    """A manually advanced clock — the deterministic test instrument (FR-012)."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        """Move the clock forward (or backward, for edge-case tests) by
        ``seconds``."""

        self._t += seconds

    def set(self, t: float) -> None:
        """Set the clock to an absolute time (may move backward — the Scheduler
        ignores a regression for due calculations)."""

        self._t = t


class RealClock:
    """A production adapter over ``time.monotonic`` (FR-010)."""

    def now(self) -> float:
        return time.monotonic()
