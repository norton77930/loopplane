"""Scheduler policies and the public-safe error type
(contracts/scheduler.md, contracts/drivers.md; FR-004, FR-041, FR-060).
"""

from __future__ import annotations

from typing import Literal

# How a clock jump past multiple due ticks is handled (each starts <=1 run; FR-062).
MissedRunPolicy = Literal["skip", "catch_up_once", "coalesce"]

# When a condition trigger fires: on the false->true edge, or on every satisfied
# poll (FR-041).
ConditionMode = Literal["edge", "level"]


class SchedulerError(ValueError):
    """Raised when a scheduler registration or operation is invalid (FR-004).

    The message is field-level and public-safe; it never carries a secret or a
    private path (NFR-004).
    """
