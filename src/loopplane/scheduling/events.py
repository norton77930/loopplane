"""The Scheduler Event vocabulary (contracts/events-state-boundary.md;
FR-080–FR-081).

A scheduler-level lifecycle stream, distinct from Loop Events and Runtime
Events. Versioned and additive; consumers tolerate unknown future types.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

SCHEDULER_SCHEMA_VERSION: Final[str] = "1.0"

SchedulerEventType = Literal[
    "trigger_registered",
    "trigger_fired",
    "run_skipped",
    "run_caught_up",
    "run_coalesced",
    "trigger_paused",
    "trigger_resumed",
    "condition_error",
    "scheduler_stopped",
]

SCHEDULER_EVENT_TYPES: Final[tuple[SchedulerEventType, ...]] = (
    "trigger_registered",
    "trigger_fired",
    "run_skipped",
    "run_caught_up",
    "run_coalesced",
    "trigger_paused",
    "trigger_resumed",
    "condition_error",
    "scheduler_stopped",
)


@dataclass(frozen=True)
class SchedulerEvent:
    """One scheduler-level lifecycle record (FR-080)."""

    type: SchedulerEventType
    sequence: int
    clock_time: float
    trigger_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEDULER_SCHEMA_VERSION


SchedulerEventSink = Callable[[SchedulerEvent], Awaitable[None]]
