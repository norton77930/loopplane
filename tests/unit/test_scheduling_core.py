"""Foundational unit tests for the scheduler layer (feature 004, SA).

Covers the virtual clock, registration validation, and Trigger State
reconstruction — all host-free and synchronous.
"""

from __future__ import annotations

import pytest

from loopplane.scheduling import (
    SchedulerError,
    SchedulerEvent,
    TriggerRegistration,
    VirtualClock,
    reconstruct_states,
    validate_registration,
)
from loopplane.scheduling.state import LoopRunRef
from tests.scheduling_helpers import pass_loop_definition

# --- VirtualClock (FR-010-FR-012) ---


def test_virtual_clock_advances_and_sets() -> None:
    clock = VirtualClock()
    assert clock.now() == 0.0
    clock.advance(5.0)
    assert clock.now() == 5.0
    clock.set(2.0)  # backward move is allowed; the scheduler ignores it for due calc
    assert clock.now() == 2.0


# --- Registration validation (FR-004, FR-033) ---


def _registration(**kw: object) -> TriggerRegistration:
    base = dict(
        trigger_id="t",
        definition=pass_loop_definition(),
        kind="manual",
    )
    base.update(kw)
    return TriggerRegistration(**base)  # type: ignore[arg-type]


def test_empty_trigger_id_is_rejected() -> None:
    with pytest.raises(SchedulerError, match="non-empty"):
        validate_registration(_registration(trigger_id=""), set())


def test_duplicate_trigger_id_is_rejected() -> None:
    with pytest.raises(SchedulerError, match="already registered"):
        validate_registration(_registration(trigger_id="t"), {"t"})


def test_non_positive_interval_is_rejected() -> None:
    reg = _registration(kind="interval", interval_seconds=0.0)
    with pytest.raises(SchedulerError, match="must be positive"):
        validate_registration(reg, set())


def test_condition_without_predicate_is_rejected() -> None:
    reg = _registration(kind="condition", predicate=None)
    with pytest.raises(SchedulerError, match="requires a predicate"):
        validate_registration(reg, set())


def test_valid_registrations_pass() -> None:
    validate_registration(_registration(), set())
    validate_registration(_registration(kind="interval", interval_seconds=60.0), set())
    validate_registration(
        _registration(kind="condition", predicate=lambda: True), set()
    )


# --- Trigger State reconstruction (FR-052, SC-006) ---


def test_reconstruct_states_rebuilds_from_the_event_stream() -> None:
    events = [
        SchedulerEvent(
            "trigger_registered", 0, 0.0, "t", {"kind": "interval", "next_due": 10.0}
        ),
        SchedulerEvent(
            "trigger_fired",
            1,
            10.0,
            "t",
            {
                "next_due": 20.0,
                "missed_ticks_delta": 0,
                "terminal_event": "loop_completed",
                "paused": False,
            },
        ),
        SchedulerEvent(
            "run_skipped", 2, 50.0, "t", {"missed_ticks": 2, "next_due": 60.0}
        ),
        SchedulerEvent(
            "trigger_fired",
            3,
            50.0,
            "t",
            {
                "next_due": 60.0,
                "missed_ticks_delta": 2,
                "terminal_event": "loop_completed",
                "paused": False,
            },
        ),
        SchedulerEvent("trigger_paused", 4, 60.0, "t", {}),
    ]

    states = reconstruct_states(events)

    state = states["t"]
    assert state.fire_count == 2
    assert state.last_fired == 50.0
    assert state.next_due == 60.0
    assert state.missed_ticks == 2
    assert state.enabled is False
    assert state.last_run_ref == LoopRunRef("t", "loop_completed", False)


def test_reconstruct_states_handles_an_empty_stream() -> None:
    assert reconstruct_states([]) == {}
