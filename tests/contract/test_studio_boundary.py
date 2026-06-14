"""Boundary and cross-cutting contract tests for the desktop/studio host (012;
NFR-001-NFR-003, NFR-006, FR-051, SC-003/005).

The layer is an additive local presentation over the public host: it composes
only ``loopplane.host`` (+ ``anyio`` and stdlib), executes no tool, re-emits no
live bus, surfaces metadata-only views, and spawns no process / opens no socket.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.studio import (
    ErrorView,
    HistoryEntryView,
    InProcessSidecar,
    RunResultView,
    SessionSummaryView,
    StudioHost,
)
from tests.studio_helpers import build_test_host, multi_text_model

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDIO_DIR = REPO_ROOT / "src" / "loopplane" / "studio"

ALLOWED_PREFIXES = (
    "loopplane.host",
    "loopplane.studio",
)
# Non-import runtime-internal / re-emit / process / network surfaces this layer
# must never reach. (loopplane.* internal/event/sibling *imports* are enforced
# authoritatively by the AST import allow-list below; this text scan covers the
# stdlib process/network + re-emit symbols the allow-list does not see.)
PROHIBITED_TOKENS = (
    "RuntimeController",
    "EventEmitter",
    "serialize_event",
    "subprocess",
    "socket",
    ".system(",
)


def _modules() -> list[Path]:
    return sorted(STUDIO_DIR.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_studio_imports_only_host_surfaces() -> None:
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


def test_studio_references_no_internal_event_process_or_sibling() -> None:
    violations: list[str] = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token!r}")
    assert not violations, "Prohibited references:\n" + "\n".join(violations)


def test_studio_view_models_are_metadata_only() -> None:
    assert set(HistoryEntryView.__dataclass_fields__) == {"role", "block_count"}
    assert set(RunResultView.__dataclass_fields__) == {
        "session_id",
        "termination_reason",
        "turns_taken",
        "history",
        "consumer_failures",
    }
    assert set(SessionSummaryView.__dataclass_fields__) == {"session_id", "label"}
    assert set(ErrorView.__dataclass_fields__) == {"kind", "detail"}


@pytest.mark.anyio
async def test_studio_conflict_and_not_available_are_fail_safe(tmp_path: Path) -> None:
    class _ConflictHost:
        async def run(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("a run is already active")

    async with StudioHost(_ConflictHost()) as studio:  # type: ignore[arg-type]
        conflict = await studio.run("x")
    assert isinstance(conflict, ErrorView)
    assert conflict.kind == "conflict"

    host = build_test_host(tmp_path, model=multi_text_model("a"), tools=())
    not_available = await InProcessSidecar(host).run("x")  # before start
    assert isinstance(not_available, ErrorView)
    assert not_available.kind == "not-available"
