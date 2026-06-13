"""US2: see what happened in an agent run (spec US2; SC-003/004)."""

from __future__ import annotations

from types import SimpleNamespace

from loopplane.inspect import run_diagnostics
from tests.inspect_helpers import (
    diagnostic,
    run_terminated,
    tool_call_started,
    turn_completed,
)


def test_run_diagnostics_counts_and_reason() -> None:
    events = [
        tool_call_started(0),
        tool_call_started(1),
        turn_completed(2),
        diagnostic(3),
        run_terminated(4, reason="cancelled"),
    ]
    diagnostics = run_diagnostics(events)
    assert diagnostics.tool_calls == 2
    assert diagnostics.turns == 1
    assert diagnostics.errors == 1
    assert diagnostics.termination_reason == "cancelled"


def test_run_diagnostics_empty_is_zero() -> None:
    diagnostics = run_diagnostics([])
    assert (diagnostics.tool_calls, diagnostics.turns, diagnostics.errors) == (0, 0, 0)
    assert diagnostics.termination_reason is None


def test_run_diagnostics_skips_unknown_type() -> None:
    events = [tool_call_started(0), SimpleNamespace(type="future-event", sequence=1)]
    diagnostics = run_diagnostics(events)
    assert diagnostics.tool_calls == 1


def test_run_diagnostics_is_deterministic() -> None:
    events = [tool_call_started(0), turn_completed(1), run_terminated(2)]
    assert run_diagnostics(events) == run_diagnostics(events)
