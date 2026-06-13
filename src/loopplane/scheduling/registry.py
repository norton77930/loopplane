"""Trigger registration and its validation
(contracts/scheduler.md; FR-001, FR-004, FR-033).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Set
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from loopplane.scheduling.policy import ConditionMode, MissedRunPolicy, SchedulerError

if TYPE_CHECKING:
    from loopplane.engineering import LoopDefinition

TriggerKind = Literal["manual", "interval", "condition"]

Predicate = Callable[[], bool | Awaitable[bool]]


@dataclass(frozen=True)
class TriggerRegistration:
    """A stable trigger id bound to a Loop Definition and a trigger
    configuration (FR-001)."""

    trigger_id: str
    definition: LoopDefinition
    kind: TriggerKind
    interval_seconds: float | None = None
    start_immediately: bool = False
    predicate: Predicate | None = None
    mode: ConditionMode = "edge"
    missed_run_policy: MissedRunPolicy = "skip"


def validate_registration(
    registration: TriggerRegistration, existing_ids: Set[str]
) -> None:
    """Fail fast on an invalid registration (FR-004, FR-033)."""

    if not registration.trigger_id:
        raise SchedulerError("trigger_id must be a non-empty string")
    if registration.trigger_id in existing_ids:
        raise SchedulerError(
            f"trigger id already registered: {registration.trigger_id!r}"
        )
    if registration.kind == "interval":
        if registration.interval_seconds is None or registration.interval_seconds <= 0:
            raise SchedulerError("interval_seconds must be positive")
    if registration.kind == "condition" and registration.predicate is None:
        raise SchedulerError("a condition trigger requires a predicate")
