"""US1: observe every tool call for an audit trail (T011; FR-005, SC-001/004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.hooks import (
    AfterToolFailurePayload,
    AfterToolUsePayload,
    HookRegistry,
    LifecyclePoint,
)
from loopplane.model import TextBlock
from tests.hooks_helpers import Recorder, build_with_hooks, tool_script

pytestmark = pytest.mark.anyio


async def test_after_tool_use_fires_once_per_success(tmp_path: Path) -> None:
    registry = HookRegistry()
    seen: list[str] = []
    registry.register(
        LifecyclePoint.after_tool_use,
        lambda p: (
            seen.append(p.tool_name) if isinstance(p, AfterToolUsePayload) else None
        ),
    )
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"), Recorder(), registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="go")])
    assert seen == ["echo"]


async def test_after_tool_failure_fires_with_sanitized_reason(tmp_path: Path) -> None:
    registry = HookRegistry()
    seen: list[AfterToolFailurePayload] = []
    registry.register(LifecyclePoint.after_tool_failure, seen.append)
    controller, sid, _ = build_with_hooks(
        tool_script("boom"), Recorder(), registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="go")])
    assert len(seen) == 1
    assert seen[0].tool_name == "boom"
    assert "boom-secret-detail" not in seen[0].reason  # sanitized (FR-015)


async def test_failing_observer_never_changes_the_run(tmp_path: Path) -> None:
    registry = HookRegistry()

    def boom(_p: object) -> None:
        raise RuntimeError("observer-secret")

    registry.register(LifecyclePoint.after_tool_use, boom)
    recorder, failures = Recorder(), []
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"),
        recorder,
        registry,
        working_scope=tmp_path,
        failures=failures,
    )
    await controller.drive(sid, [TextBlock(text="go")])
    terminal = recorder.events[-1]
    assert terminal.type == "run-terminated"
    assert terminal.payload.reason == "natural-completion"  # outcome unchanged (SC-004)
    assert failures and all("observer-secret" not in m for m in failures)
