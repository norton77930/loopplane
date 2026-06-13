"""The Trigger boundary (contracts/loop-definition.md; FR-020–FR-023).

Only :class:`ManualTrigger` is executable this phase. :class:`IntervalTrigger`
and :class:`ConditionTrigger` are **data contracts** a host-supplied driver
enacts by calling the same manual entry point; the layer ships no scheduler,
queue worker, or background daemon (FR-023).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManualTrigger:
    """A host explicitly starts a Loop Run (FR-020)."""


@dataclass(frozen=True)
class IntervalTrigger:
    """Contract only: "start a Loop Run every interval" (FR-021).

    Carries no scheduler state and no background behavior. A host driver enacts
    each tick by calling the manual entry point.
    """

    interval_seconds: float
    start_immediately: bool = False


@dataclass(frozen=True)
class ConditionTrigger:
    """Contract only: a host-supplied predicate whose satisfaction starts a
    Loop Run (FR-022).

    ``predicate_ref`` names a host-resolved predicate; the layer provides no
    event or condition watcher this phase.
    """

    predicate_ref: str
    description: str = ""


Trigger = ManualTrigger | IntervalTrigger | ConditionTrigger
