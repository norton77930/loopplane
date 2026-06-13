"""Boundary and cross-cutting contract tests for the loop-engineering layer
(feature 003; NFR-003, SC-002, SC-006, SC-009, FR-075).

The layer must compose the runtime ONLY through ``loopplane.host`` (and the
normalized value types the host re-exposes), never by reaching into a Phase-1
internal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.engineering import (
    HostRuntimeProfile,
    LoopDefinition,
    LoopEvent,
    ManualTrigger,
    ObservationPolicy,
    RetryPolicy,
    StaticInput,
    ValidationPolicy,
    reconstruct_state,
    run_loop,
    stop_on_pass,
)
from tests.loop_helpers import (
    LoopEventRecorder,
    ScriptedValidator,
    scripted_host,
    scripted_host_factory,
)

pytestmark = pytest.mark.anyio

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINEERING_DIR = REPO_ROOT / "src" / "loopplane" / "engineering"

# Phase-1 orchestration internals the loop layer must never import directly
# (contracts/host-integration.md). Value-type modules (loopplane.host,
# loopplane.model, loopplane.events) are allowed.
PROHIBITED_PREFIXES = (
    "loopplane.controller",
    "loopplane.gateway",
    "loopplane.dispatcher",
    "loopplane.loop",
    "loopplane.memory",
    "loopplane.checkpoint",
    "loopplane.artifacts",
    "loopplane.approval",
    "loopplane.observability",
    "loopplane.skills",
    "loopplane.adapters",
    "loopplane.context",
)
PROHIBITED_NAMES = {"EventEmitter", "EventSequencer", "EventSink", "RuntimeController"}


def _imports(path: Path) -> list[tuple[str, str | None]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.extend((node.module, alias.name) for alias in node.names)
    return found


def test_engineering_imports_only_the_allowed_host_surface() -> None:
    violations: list[str] = []
    for path in sorted(ENGINEERING_DIR.glob("*.py")):
        for module, name in _imports(path):
            if any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in PROHIBITED_PREFIXES
            ):
                violations.append(f"{path.name}: imports module {module}")
            if module.startswith("loopplane.events") and name in PROHIBITED_NAMES:
                violations.append(f"{path.name}: imports {name} from {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


async def test_every_agent_run_goes_through_host_run(tmp_path: Path) -> None:
    inner = scripted_host("a", "b", "c", working_scope=tmp_path)

    class CountingHost:
        def __init__(self) -> None:
            self.run_calls = 0

        async def run(self, *args: object, **kwargs: object) -> object:
            self.run_calls += 1
            return await inner.run(*args, **kwargs)  # type: ignore[arg-type]

        def history_snapshot(self, session_id: str) -> object:
            return inner.history_snapshot(session_id)

        def retrieve_artifact(self, session_id: str, reference: str) -> object:
            return inner.retrieve_artifact(session_id, reference)

    host = CountingHost()
    definition = LoopDefinition(
        loop_id="counted",
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(selector=lambda: host),  # type: ignore[arg-type]
        validation_policy=ValidationPolicy(validator=ScriptedValidator("fail")),
        stop_condition=stop_on_pass(max_iterations=5),
        retry_policy=RetryPolicy(max_retries=2),
    )

    outcome = await run_loop(definition)

    # Every Agent Run was started through host.run — there is no other path.
    assert host.run_calls == len(outcome.state.run_refs) == 3


async def test_loop_state_reconstructs_from_events_alone(tmp_path: Path) -> None:
    definition = LoopDefinition(
        loop_id="reconstructable",
        trigger=ManualTrigger(),
        input_source=StaticInput("go"),
        host_profile=HostRuntimeProfile(
            selector=lambda: scripted_host("x", working_scope=tmp_path)
        ),
        validation_policy=ValidationPolicy(validator=ScriptedValidator("pass")),
        stop_condition=stop_on_pass(),
        observation_policy=ObservationPolicy(emit_loop_events=True),
    )

    outcome = await run_loop(definition)
    rebuilt = reconstruct_state(outcome.events)

    assert rebuilt.loop_id == outcome.state.loop_id
    assert rebuilt.iteration_index == outcome.state.iteration_index
    assert rebuilt.run_refs == outcome.state.run_refs
    assert rebuilt.stop_reason == outcome.state.stop_reason
    assert outcome.state.latest_validation is not None
    assert rebuilt.latest_validation == outcome.state.latest_validation


async def test_observation_off_matches_observation_on(tmp_path: Path) -> None:
    def make(observe: bool) -> LoopDefinition:
        return LoopDefinition(
            loop_id="parity",
            trigger=ManualTrigger(),
            input_source=StaticInput("go"),
            host_profile=HostRuntimeProfile(
                selector=scripted_host_factory("x", working_scope=tmp_path)
            ),
            validation_policy=ValidationPolicy(validator=ScriptedValidator("pass")),
            stop_condition=stop_on_pass(),
            observation_policy=ObservationPolicy(emit_loop_events=observe),
        )

    observed_sink = LoopEventRecorder()
    unobserved_sink = LoopEventRecorder()
    observed = await run_loop(make(True), on_loop_event=observed_sink)
    unobserved = await run_loop(make(False), on_loop_event=unobserved_sink)

    # Decisions and terminal outcome are identical; only emission differs.
    assert observed.terminal_event == unobserved.terminal_event
    assert observed.stop_reason == unobserved.stop_reason
    assert observed.state.iteration_index == unobserved.state.iteration_index
    assert observed.state.latest_validation == unobserved.state.latest_validation
    assert [e.type for e in observed.events] == [e.type for e in unobserved.events]
    assert len(observed_sink.events) > 0
    assert unobserved_sink.events == []  # observation off => sink never called


def test_unknown_future_loop_event_type_is_tolerated() -> None:
    # A consumer (here, reconstruct_state) skips an unrecognized event type
    # without error — forward-compatible per FR-075.
    events = [
        LoopEvent("loop_started", 0, "L", "L"),
        LoopEvent("a_future_event_type", 1, "L", "L"),  # type: ignore[arg-type]
        LoopEvent(
            "loop_iteration_completed",
            2,
            "L",
            "L",
            iteration_index=1,
            session_id="s1",
            payload={"termination_reason": "natural-completion"},
        ),
        LoopEvent("loop_completed", 3, "L", "L", payload={"stop_reason": "done"}),
    ]

    state = reconstruct_state(events)

    assert state.loop_id == "L"
    assert state.iteration_index == 1
    assert state.stop_reason == "done"
