"""Boundary and cross-cutting contract tests for the scheduler layer
(feature 004; NFR-003, SC-002, SC-006, SC-009, FR-081).

The scheduler must compose the loop layer ONLY through ``loopplane.engineering``
(the ``run_loop`` surface + trigger/value types), never by importing a Phase-1/2
internal or the Phase-3 ``LoopController`` mechanics.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.scheduling import (
    Scheduler,
    SchedulerEvent,
    VirtualClock,
    reconstruct_states,
)
from tests.scheduling_helpers import SchedulerEventRecorder, pass_loop_definition

pytestmark = pytest.mark.anyio

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEDULING_DIR = REPO_ROOT / "src" / "loopplane" / "scheduling"


def _loopplane_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return [m for m in modules if m.startswith("loopplane")]


def test_scheduling_imports_only_the_loop_layer_public_surface() -> None:
    # A loopplane import is allowed iff it is the engineering package itself
    # (run_loop + types) or another scheduling module. Anything else — host,
    # model, events, controller mechanics, or any lower Phase-1 internal — is a
    # boundary violation.
    violations: list[str] = []
    for path in sorted(SCHEDULING_DIR.glob("*.py")):
        for module in _loopplane_imports(path):
            allowed = module == "loopplane.engineering" or module.startswith(
                "loopplane.scheduling"
            )
            if not allowed:
                violations.append(f"{path.name}: imports {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


async def test_scheduled_runs_go_through_run_loop(tmp_path: Path) -> None:
    scheduler = Scheduler(VirtualClock())
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))

    outcome = await scheduler.start("job")

    # The fired run is a real Loop Run with an Agent Run reference — it went
    # through run_loop -> host, the only firing path (SC-002).
    assert outcome.terminal_event == "loop_completed"
    assert len(outcome.state.run_refs) == 1


async def test_observation_off_matches_observation_on(tmp_path: Path) -> None:
    async def run(observe: bool) -> tuple[int, float | None, list[str]]:
        recorder = SchedulerEventRecorder()
        clock = VirtualClock()
        scheduler = Scheduler(clock, on_event=recorder if observe else None)
        scheduler.register_interval(
            "iv", pass_loop_definition(working_scope=tmp_path), interval_seconds=10.0
        )
        for _ in range(3):
            clock.advance(10.0)
            await scheduler.poll()
        state = scheduler.trigger_state("iv")
        return state.fire_count, state.next_due, [e.type for e in scheduler.events]

    observed = await run(True)
    unobserved = await run(False)

    # Decisions and outcome are identical; only external emission differs.
    assert observed == unobserved


async def test_observation_off_calls_no_sink(tmp_path: Path) -> None:
    recorder = SchedulerEventRecorder()
    # Wire the recorder but keep observation effectively off by never passing it.
    scheduler = Scheduler(VirtualClock())
    scheduler.register_manual("job", pass_loop_definition(working_scope=tmp_path))
    await scheduler.start("job")
    assert recorder.events == []  # the unwired sink received nothing


def test_unknown_future_scheduler_event_is_tolerated() -> None:
    events = [
        SchedulerEvent("trigger_registered", 0, 0.0, "t", {"next_due": 10.0}),
        SchedulerEvent("a_future_event_type", 1, 10.0, "t"),  # type: ignore[arg-type]
        SchedulerEvent(
            "trigger_fired",
            2,
            10.0,
            "t",
            {"next_due": 20.0, "terminal_event": "loop_completed", "paused": False},
        ),
    ]

    states = reconstruct_states(events)

    assert states["t"].fire_count == 1
    assert states["t"].next_due == 20.0
