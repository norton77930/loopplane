"""Boundary, public-safety, and zero-behavior-change for hooks
(T024-T026; FR-009, FR-010, FR-011, FR-015, SC-003/005)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from loopplane.hooks import HookRegistry, LifecyclePoint
from loopplane.model import TextBlock
from tests.hooks_helpers import Recorder, build_with_hooks, tool_script

from .conftest import EventCollector, HarnessFactory

pytestmark = pytest.mark.anyio

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "src" / "loopplane" / "hooks"
PROHIBITED = ("ToolGateway", "EventEmitter", "RuntimeController", "serialize_event")


def test_hooks_package_imports_nothing_else_from_the_runtime() -> None:
    # The hook layer is foundational and dependency-free: it imports only itself
    # from loopplane, so it can neither execute tools nor touch the event bus
    # (FR-009, FR-010). This is also what justifies higher layers depending on it.
    violations: list[str] = []
    for path in sorted(HOOKS_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.startswith("loopplane") and not module.startswith(
                    "loopplane.hooks"
                ):
                    violations.append(f"{path.name}: imports {module}")
    assert not violations, violations


def test_hooks_package_references_no_runtime_internal() -> None:
    violations: list[str] = []
    for path in sorted(HOOKS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED:
            if token in text:
                violations.append(f"{path.name}: references {token!r}")
    assert not violations, violations


def _payload_text(event: object) -> str:
    payload = getattr(event, "payload", None)
    return f"{getattr(payload, 'message', '')} {getattr(payload, 'reason', '')}"


async def test_no_event_or_diagnostic_leaks_a_raw_exception(tmp_path: Path) -> None:
    registry = HookRegistry()

    def leaky(_p: object) -> None:
        raise RuntimeError("super-secret-leak")

    registry.register(LifecyclePoint.after_tool_use, leaky)
    recorder, failures = Recorder(), []
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"),
        recorder,
        registry,
        working_scope=tmp_path,
        failures=failures,
    )
    await controller.drive(sid, [TextBlock(text="go")])
    haystack = " ".join(_payload_text(e) for e in recorder.events) + " ".join(failures)
    assert "super-secret-leak" not in haystack  # no raw exception leak (FR-015)


async def test_empty_registry_matches_a_no_hooks_run(
    tmp_path: Path, harness: HarnessFactory, collector: EventCollector
) -> None:
    # No-hooks baseline (the harness builds a controller with no hooks).
    base_controller, base_sid = harness(tool_script("echo", text="ping"), collector)
    await base_controller.drive(base_sid, [TextBlock(text="go")])
    baseline = collector.types

    # Hooks present but empty: the event sequence must be identical (SC-003).
    recorder = Recorder()
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"),
        recorder,
        HookRegistry(),
        working_scope=tmp_path,
    )
    await controller.drive(sid, [TextBlock(text="go")])
    assert recorder.types == baseline
