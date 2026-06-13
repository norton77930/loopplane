"""Boundary and cross-cutting contract tests for the human-review layer
(006; NFR-003, SC-002, SC-007, FR-051).

The layer composes only the Phase-3 public surface and reads only the public Loop
State; it never imports or references a Phase-1 approval/interaction symbol or any
orchestration internal.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.engineering import run_loop
from loopplane.review import ReviewEvent, build_review_resolver
from tests.review_helpers import (
    ReviewEventRecorder,
    const_reviewer,
    needs_review_definition,
)

pytestmark = pytest.mark.anyio

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = REPO_ROOT / "src" / "loopplane" / "review"

ALLOWED_PREFIXES = ("loopplane.engineering", "loopplane.review")
PROHIBITED_TOKENS = (
    "loopplane.approval",
    "InteractionBroker",
    "HumanApproval",
    "session_approval_memory",
    "LoopController",
    "LoopPlaneHost",
    "loopplane.controller",
    "loopplane.host",
    "loopplane.scheduling",
)


def _loopplane_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return [m for m in modules if m.startswith("loopplane")]


def test_review_imports_only_the_loop_layer_public_surface() -> None:
    violations: list[str] = []
    for path in sorted(REVIEW_DIR.glob("*.py")):
        for module in _loopplane_imports(path):
            if not any(
                module == p or module.startswith(p + ".") for p in ALLOWED_PREFIXES
            ):
                violations.append(f"{path.name}: imports {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_review_references_no_phase1_approval_symbol() -> None:
    violations: list[str] = []
    for path in sorted(REVIEW_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token}")
    assert not violations, "Phase-1/2/3 internal references:\n" + "\n".join(violations)


async def test_review_drives_only_through_run_loop(tmp_path: Path) -> None:
    gate = build_review_resolver(const_reviewer("approve"))
    outcome = await run_loop(
        needs_review_definition(working_scope=tmp_path), review_resolver=gate
    )
    # The review run is a real Loop Run driven through run_loop (SC-002).
    assert outcome.terminal_event == "loop_completed"
    assert len(outcome.state.run_refs) >= 1


async def test_gated_review_is_deterministic(tmp_path: Path) -> None:
    async def run() -> tuple[str | None, str | None, list[str]]:
        recorder = ReviewEventRecorder()
        outcome = await run_loop(
            needs_review_definition(working_scope=tmp_path),
            review_resolver=build_review_resolver(
                const_reviewer("approve", reason="ok"), on_event=recorder
            ),
        )
        return outcome.terminal_event, outcome.stop_reason, recorder.types

    assert await run() == await run()


def test_unknown_future_review_event_is_tolerated() -> None:
    # A consumer iterating events skips an unrecognized type without error
    # (forward-compatible per FR-051).
    events = [
        ReviewEvent(type="review_requested", sequence=0, loop_id="L"),
        ReviewEvent(type="a_future_event", sequence=1, loop_id="L"),  # type: ignore[arg-type]
        ReviewEvent(type="review_decided", sequence=2, loop_id="L"),
    ]
    known = {"review_requested", "review_decided"}
    handled = [e.type for e in events if e.type in known]
    assert handled == ["review_requested", "review_decided"]
