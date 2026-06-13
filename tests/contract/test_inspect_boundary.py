"""Boundary and cross-cutting contract tests for the inspect layer
(010; NFR-001, NFR-003, NFR-006, SC-002/005).

The layer composes only the public Phase-3 Loop Event / Loop State and Phase-1
Runtime Event surfaces, drives no run, re-emits no live-bus event, and reads only
metadata.
"""

from __future__ import annotations

import ast
from pathlib import Path

from loopplane.inspect import build_trace, loop_diagnostics, run_diagnostics
from tests.inspect_helpers import loop_event, run_terminated, tool_call_started

REPO_ROOT = Path(__file__).resolve().parents[2]
INSPECT_DIR = REPO_ROOT / "src" / "loopplane" / "inspect"

ALLOWED_PREFIXES = (
    "loopplane.engineering",
    "loopplane.events",
    "loopplane.inspect",
)
PROHIBITED_IMPORT_NAMES = ("run_loop", "LoopController", "LoopPlaneHost")


def _modules() -> list[Path]:
    return sorted(INSPECT_DIR.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_inspect_imports_only_event_and_state_surfaces() -> None:
    violations: list[str] = []
    for path in _modules():
        for node in ast.walk(_parsed(path)):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.startswith("loopplane") and not any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in ALLOWED_PREFIXES
                ):
                    violations.append(f"{path.name}: imports {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_inspect_imports_no_run_driver() -> None:
    violations: list[str] = []
    for path in _modules():
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in PROHIBITED_IMPORT_NAMES:
                        violations.append(f"{path.name}: imports {alias.name}")
    assert not violations, "Run-driver imports:\n" + "\n".join(violations)


def test_inspect_drives_no_run() -> None:
    violations: list[str] = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        if ".run(" in text or "run_loop" in text or "LoopController" in text:
            violations.append(f"{path.name}: references a run-driving surface")
    assert not violations, "Drives a run:\n" + "\n".join(violations)


def test_inspect_is_deterministic() -> None:
    loop_events = [
        loop_event(
            "loop_iteration_completed", sequence=0, iteration_index=0, session_id="s1"
        ),
        loop_event("loop_completed", sequence=1),
    ]
    assert loop_diagnostics(loop_events) == loop_diagnostics(loop_events)
    runs = {"s1": [tool_call_started(0, session_id="s1")]}
    assert build_trace(loop_events, runs) == build_trace(loop_events, runs)


def test_inspect_artifacts_are_metadata_only() -> None:
    run = run_diagnostics([tool_call_started(0), run_terminated(1, reason="cancelled")])
    # Only counts + a public-safe reason — no content fields.
    assert set(vars(run)) == {"tool_calls", "turns", "errors", "termination_reason"}
    trace = build_trace(
        [
            loop_event(
                "loop_iteration_completed",
                sequence=0,
                iteration_index=0,
                session_id="s1",
            )
        ],
        {"s1": [tool_call_started(2, session_id="s1")]},
    )
    assert trace.root is not None
    span = trace.root.children[0].children[0].children[0]
    assert set(vars(span)) <= {"kind", "identifier", "sequence", "children"}
