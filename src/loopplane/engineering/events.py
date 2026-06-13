"""The Loop Event vocabulary (contracts/loop-events.md; FR-070–FR-075).

A loop-level lifecycle stream that is **distinct** from the Phase-1 Runtime
Event Bus. Loop Events reference Agent Runs by ``session_id`` but never wrap,
replace, or re-emit Runtime Events (FR-070). The vocabulary is versioned and
evolves additively; consumers tolerate unknown future types (FR-075).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

LOOP_SCHEMA_VERSION: Final[str] = "1.0"

LoopEventType = Literal[
    "loop_started",
    "loop_iteration_started",
    "loop_iteration_completed",
    "validation_completed",
    "evaluation_completed",
    "repair_requested",
    "retry_scheduled",
    "human_review_requested",
    "loop_completed",
    "loop_failed",
]

LOOP_EVENT_TYPES: Final[tuple[LoopEventType, ...]] = (
    "loop_started",
    "loop_iteration_started",
    "loop_iteration_completed",
    "validation_completed",
    "evaluation_completed",
    "repair_requested",
    "retry_scheduled",
    "human_review_requested",
    "loop_completed",
    "loop_failed",
)

TERMINAL_LOOP_EVENTS: Final[tuple[LoopEventType, ...]] = (
    "loop_completed",
    "loop_failed",
)


@dataclass(frozen=True)
class LoopEvent:
    """One loop-level lifecycle record (FR-070–FR-072).

    Carries the loop identity, the iteration it pertains to (where applicable),
    and a correlation to the relevant Agent Run (``session_id``) when one
    exists. ``sequence`` is monotonic within a Loop Run (FR-073).
    """

    type: LoopEventType
    sequence: int
    loop_id: str
    loop_definition_id: str
    iteration_index: int | None = None
    session_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = LOOP_SCHEMA_VERSION


# Async, consumer-side sink — structurally parallel to the Phase-1 ``EventSink``
# but a distinct stream (FR-070). Attached only when observation is enabled.
LoopEventSink = Callable[[LoopEvent], Awaitable[None]]
