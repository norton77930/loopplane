"""Boundary and cross-cutting contract tests for the multi-agent orchestration
layer (013; NFR-001-NFR-003, NFR-006, SC-002/003/005).

The layer composes only the public Phase-3 loop surface: it executes no tool,
re-emits no live bus (it reads each captured outcome), and surfaces metadata-only
aggregated views, deterministically by registration order.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.orchestration import (
    AgentRegistry,
    AggregatedArtifact,
    AggregatedEvent,
    ChildRunReference,
    Coordinator,
    SubagentResult,
    aggregate_events,
)
from tests.orchestration_helpers import scripted_subagent_definition

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCH_DIR = REPO_ROOT / "src" / "loopplane" / "orchestration"

ALLOWED_PREFIXES = (
    "loopplane.engineering",
    "loopplane.orchestration",
    # Feature 015: the coordinator may fire subagent lifecycle hooks through the
    # foundational, dependency-free hook layer. This preserves the boundary's
    # intent (still no tool execution and no live-bus re-emit — enforced by
    # PROHIBITED_TOKENS below); hooks observe only.
    "loopplane.hooks",
)
# Non-import runtime-internal / re-emit symbols this layer must never reach.
# (loopplane.* internal/host/sibling *imports* are enforced authoritatively by
# the AST import allow-list below.)
PROHIBITED_TOKENS = (
    "RuntimeController",
    "EventEmitter",
    "serialize_event",
)


def _modules() -> list[Path]:
    return sorted(ORCH_DIR.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_orchestration_imports_only_engineering() -> None:
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


def test_orchestration_references_no_runtime_internal() -> None:
    violations: list[str] = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token!r}")
    assert not violations, "Runtime-internal references:\n" + "\n".join(violations)


def test_aggregated_views_are_metadata_only() -> None:
    assert set(AggregatedEvent.__dataclass_fields__) == {
        "subagent",
        "type",
        "sequence",
    }
    assert set(AggregatedArtifact.__dataclass_fields__) == {
        "subagent",
        "session_id",
        "reference",
    }
    assert set(ChildRunReference.__dataclass_fields__) == {
        "subagent",
        "loop_id",
        "run_refs",
    }
    assert set(SubagentResult.__dataclass_fields__) == {
        "subagent",
        "reference",
        "outcome",
        "failure",
    }


@pytest.mark.anyio
async def test_aggregation_is_deterministic() -> None:
    registry = AgentRegistry()
    registry.register("a", scripted_subagent_definition("a"))
    coordinator = Coordinator(registry)

    first = aggregate_events(await coordinator.run(["a"]))
    second = aggregate_events(await coordinator.run(["a"]))

    assert first == second
