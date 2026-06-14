"""US5: session / subagent / file lifecycle (T020; FR-013/014/019)."""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from loopplane.hooks import (
    FileChangedPayload,
    HookRegistry,
    LifecyclePoint,
    SessionEndPayload,
)
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.model import TextBlock
from loopplane.orchestration import AgentRegistry, Coordinator
from tests.hooks_helpers import Recorder, build_with_hooks, text_script, tool_script
from tests.orchestration_helpers import scripted_subagent_definition

pytestmark = pytest.mark.anyio


async def test_process_setup_fires_once_session_start_per_session(
    tmp_path: Path,
) -> None:
    registry = HookRegistry()
    setups: list[object] = []
    starts: list[object] = []
    registry.register(LifecyclePoint.process_setup, setups.append)
    registry.register(LifecyclePoint.session_start, starts.append)
    controller, sid1, _ = build_with_hooks(
        text_script("a", "b"), Recorder(), registry, working_scope=tmp_path
    )
    sid2 = controller.create_session(working_scope=tmp_path)
    await controller.drive(sid1, [TextBlock(text="hi")])
    await controller.drive(sid2, [TextBlock(text="hi")])
    assert len(setups) == 1  # process_setup at most once per runtime (FR-014)
    assert len(starts) == 2  # session_start once per session


async def test_session_end_fires_on_terminate(tmp_path: Path) -> None:
    registry = HookRegistry()
    ends: list[SessionEndPayload] = []
    registry.register(LifecyclePoint.session_end, ends.append)
    controller, sid, _ = build_with_hooks(
        text_script("a"), Recorder(), registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="hi")])
    controller.terminate(sid)
    await anyio.sleep(0.05)  # let the fire-and-forget session_end run
    assert len(ends) == 1
    assert ends[0].state == "terminated"


async def test_file_changed_fires_for_a_writer(tmp_path: Path) -> None:
    registry = HookRegistry()
    changes: list[FileChangedPayload] = []
    registry.register(LifecyclePoint.file_changed, changes.append)
    controller, sid, _ = build_with_hooks(
        tool_script("writer", path="out.txt"),
        Recorder(),
        registry,
        working_scope=tmp_path,
    )
    await controller.drive(sid, [TextBlock(text="go")])
    assert len(changes) == 1
    assert changes[0].tool_name == "writer"
    assert changes[0].path == "out.txt"


async def test_file_changed_skips_a_read_only_tool(tmp_path: Path) -> None:
    registry = HookRegistry()
    changes: list[FileChangedPayload] = []
    registry.register(LifecyclePoint.file_changed, changes.append)
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"), Recorder(), registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="go")])
    assert changes == []  # echo is read-only (FR-013)


async def test_subagent_start_stop_bracket_a_delegated_run(tmp_path: Path) -> None:
    registry = HookRegistry()
    timeline: list[str] = []
    registry.register(
        LifecyclePoint.subagent_start, lambda p: timeline.append(f"start:{p.subagent}")
    )
    registry.register(
        LifecyclePoint.subagent_stop,
        lambda p: timeline.append(f"stop:{p.subagent}:{p.outcome}"),
    )
    agents = AgentRegistry()
    agents.register("a", scripted_subagent_definition("a"))
    coordinator = Coordinator(agents, hooks=HookDispatcher(registry))
    await coordinator.run(["a"])
    assert timeline == ["start:a", "stop:a:success"]
