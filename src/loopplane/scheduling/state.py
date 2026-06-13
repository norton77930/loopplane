"""Trigger State and its event-stream reconstruction
(contracts/events-state-boundary.md; FR-050–FR-052).

Trigger State is the per-registered-trigger in-process record. It references the
most recent Scheduled Loop Run by reference only — never copying Loop State or
run history — and is reconstructable from the ordered Scheduler Event stream
(FR-051, FR-052, SC-006).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from loopplane.scheduling.events import SchedulerEvent


@dataclass(frozen=True)
class LoopRunRef:
    """A reference to a Scheduled Loop Run — the only run data Trigger State
    keeps (FR-051)."""

    trigger_id: str
    terminal_event: str | None
    paused: bool


@dataclass
class TriggerState:
    """The per-trigger in-process record (FR-050). Mutable and scheduler-owned;
    holds references only."""

    trigger_id: str
    enabled: bool = True
    last_fired: float | None = None
    next_due: float | None = None
    fire_count: int = 0
    missed_ticks: int = 0
    last_condition_value: bool = False
    last_run_ref: LoopRunRef | None = None


def reconstruct_states(events: Sequence[SchedulerEvent]) -> dict[str, TriggerState]:
    """Rebuild every trigger's state from the ordered Scheduler Event stream
    alone (FR-052, SC-006)."""

    states: dict[str, TriggerState] = {}
    for event in events:
        trigger_id = event.trigger_id
        if event.type == "trigger_registered" and trigger_id is not None:
            state = TriggerState(trigger_id=trigger_id)
            next_due = event.payload.get("next_due")
            if isinstance(next_due, int | float):
                state.next_due = float(next_due)
            states[trigger_id] = state
        elif trigger_id is None or trigger_id not in states:
            continue
        elif event.type == "trigger_fired":
            state = states[trigger_id]
            state.fire_count += 1
            state.last_fired = event.clock_time
            delta = event.payload.get("missed_ticks_delta", 0)
            if isinstance(delta, int):
                state.missed_ticks += delta
            next_due = event.payload.get("next_due")
            state.next_due = (
                float(next_due) if isinstance(next_due, int | float) else None
            )
            terminal = event.payload.get("terminal_event")
            state.last_run_ref = LoopRunRef(
                trigger_id=trigger_id,
                terminal_event=terminal if isinstance(terminal, str) else None,
                paused=bool(event.payload.get("paused", False)),
            )
            if "condition_value" in event.payload:
                state.last_condition_value = bool(event.payload["condition_value"])
        elif event.type == "trigger_paused":
            states[trigger_id].enabled = False
        elif event.type == "trigger_resumed":
            states[trigger_id].enabled = True
    return states
