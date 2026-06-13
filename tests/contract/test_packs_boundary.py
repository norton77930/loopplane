"""Boundary and cross-cutting contract tests for the packs layer
(feature 005; NFR-003, SC-002, SC-007).

A pack reads only the public ``RunOutcome`` / ``LoopState`` surface and never
imports or calls a Phase-1/2/3 orchestration internal or starts a run.
"""

from __future__ import annotations

import ast
from pathlib import Path

from loopplane.packs import (
    json_schema_validator,
    length_evaluator,
    rule_validator,
    text_validator,
)
from tests.packs_helpers import SAMPLE_SCHEMA, scripted_outcome

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_DIR = REPO_ROOT / "src" / "loopplane" / "packs"

# Value-type modules a pack may read; anything else under loopplane is an
# orchestration internal it must not import.
ALLOWED_PREFIXES = (
    "loopplane.engineering",
    "loopplane.host",
    "loopplane.model",
    "loopplane.packs",
)
# Driver/facade symbols a pack must never import (it starts no runs).
PROHIBITED_NAMES = {
    "run_loop",
    "LoopPlaneHost",
    "LoopController",
    "RuntimeController",
    "Scheduler",
    "assemble",
    "build_host",
}


def _imports(path: Path) -> list[tuple[str, str | None]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((a.name, None) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.extend((node.module, a.name) for a in node.names)
    return found


def test_packs_import_only_value_types_no_orchestration() -> None:
    violations: list[str] = []
    for path in sorted(PACKS_DIR.glob("*.py")):
        for module, name in _imports(path):
            if module.startswith("loopplane") and not any(
                module == p or module.startswith(p + ".") for p in ALLOWED_PREFIXES
            ):
                violations.append(f"{path.name}: imports module {module}")
            if name in PROHIBITED_NAMES:
                violations.append(f"{path.name}: imports {name}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_packs_start_no_run() -> None:
    # No pack source references run_loop / a host facade / the scheduler.
    forbidden = ("run_loop", "LoopPlaneHost", "Scheduler", "RuntimeController")
    for path in sorted(PACKS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name} references {token}"


def test_packs_are_deterministic() -> None:
    outcome, state = scripted_outcome(text='{"ok": true} done', artifacts=())
    packs = [
        rule_validator(lambda v: "done" in v.final_text),
        text_validator(mode="contains", pattern="done"),
        json_schema_validator(schema=SAMPLE_SCHEMA),
        length_evaluator(target_chars=20),
    ]
    for pack in packs:
        assert pack(outcome, state) == pack(outcome, state)
