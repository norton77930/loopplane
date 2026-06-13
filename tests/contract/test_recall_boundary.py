"""Boundary and cross-cutting contract tests for the recall layer
(007; NFR-001, NFR-003, NFR-006, SC-002/003/008).

The layer composes only the public Phase-1 (memory, artifacts) and Phase-3
(engineering) surfaces, reads only the public Loop State, mutates nothing, and
starts no Loop Run.
"""

from __future__ import annotations

import ast
from pathlib import Path

from loopplane.recall import (
    InMemoryKnowledgeIndex,
    KnowledgeEntry,
    RetrievalBudget,
    artifact_recall,
    assemble_recall,
    conversation_recall,
    knowledge_recall,
    memory_entry_recall,
)
from tests.recall_helpers import (
    ScriptedArtifactReader,
    artifact_meta,
    artifact_ref,
    memory_entry,
    run_ref,
    scripted_state,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RECALL_DIR = REPO_ROOT / "src" / "loopplane" / "recall"

ALLOWED_PREFIXES = (
    "loopplane.engineering",
    "loopplane.memory",
    "loopplane.artifacts",
    "loopplane.recall",
)
PROHIBITED_TOKENS = (
    "loopplane.host",
    "loopplane.model",
    "loopplane.controller",
    "loopplane.gateway",
    "loopplane.context",
    "loopplane.approval",
    "loopplane.scheduling",
    "loopplane.packs",
    "loopplane.review",
    "LoopPlaneHost",
    "LoopController",
    "run_loop",
)


def _loopplane_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return [module for module in modules if module.startswith("loopplane")]


def test_recall_imports_only_public_phase1_and_phase3_surfaces() -> None:
    violations: list[str] = []
    for path in sorted(RECALL_DIR.glob("*.py")):
        for module in _loopplane_imports(path):
            if not any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in ALLOWED_PREFIXES
            ):
                violations.append(f"{path.name}: imports {module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_recall_references_no_prohibited_symbol() -> None:
    violations: list[str] = []
    for path in sorted(RECALL_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token}")
    assert not violations, "Prohibited references:\n" + "\n".join(violations)


def test_recall_leaves_state_and_store_unmutated() -> None:
    entries = [memory_entry("auth", "authentication"), memory_entry("db", "database")]
    entries_before = list(entries)
    state = scripted_state(
        loop_id="auth", run_refs=[run_ref("s1")], artifacts=[artifact_ref("s1", "a1")]
    )
    state_before = (
        state.loop_id,
        state.run_refs,
        state.artifacts,
        state.iteration_index,
    )
    sources = [
        conversation_recall(),
        artifact_recall(ScriptedArtifactReader([artifact_meta("s1", "a1")])),
        memory_entry_recall(entries),
        knowledge_recall(InMemoryKnowledgeIndex([KnowledgeEntry("k", "auth")])),
    ]
    assemble_recall(sources, RetrievalBudget(max_entries=10), state=state)
    assert entries == entries_before
    assert (
        state.loop_id,
        state.run_refs,
        state.artifacts,
        state.iteration_index,
    ) == state_before


def test_recall_is_deterministic() -> None:
    state = scripted_state(loop_id="auth", run_refs=[run_ref("s1"), run_ref("s2")])
    sources = [conversation_recall()]
    first = assemble_recall(sources, RetrievalBudget(), state=state)
    second = assemble_recall(sources, RetrievalBudget(), state=state)
    assert first == second
