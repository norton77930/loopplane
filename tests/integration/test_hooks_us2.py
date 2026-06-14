"""US2: gate or rewrite a tool call before it runs (T013; FR-006/008/012, SC-002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.approval.decisions import PolicyAllow, PolicyDeny, PolicyVerdict
from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.events.emitter import EventEmitter
from loopplane.hooks import (
    HookRegistry,
    LifecyclePoint,
    ToolGateAllow,
    ToolGateDeny,
    ToolGateModify,
)
from loopplane.model import TextBlock
from loopplane.model.boundary import ToolCallRequest, ToolDescriptor
from tests.hooks_helpers import Recorder, build_with_hooks, tool_script

pytestmark = pytest.mark.anyio


def _completed(recorder: Recorder) -> object:
    return next(e for e in recorder.events if e.type == "tool-call-completed")


async def test_before_tool_deny_prevents_execution(tmp_path: Path) -> None:
    registry = HookRegistry()
    registry.register(
        LifecyclePoint.before_tool_use, lambda _p: ToolGateDeny(reason="blocked")
    )
    after: list[str] = []
    registry.register(
        LifecyclePoint.after_tool_use, lambda p: after.append(p.tool_name)
    )
    recorder = Recorder()
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"), recorder, registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="go")])
    completed = _completed(recorder)
    assert completed.payload.outcome == "failure"
    assert completed.payload.error.category is ErrorCategory.POLICY_DENIAL
    assert completed.payload.error.reason == "blocked"
    assert after == []  # the tool never executed, so after-tool never fired


async def test_before_tool_modify_rewrites_inputs(tmp_path: Path) -> None:
    registry = HookRegistry()
    registry.register(
        LifecyclePoint.before_tool_use,
        lambda _p: ToolGateModify(input={"text": "modified"}),
    )
    recorder = Recorder()
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"), recorder, registry, working_scope=tmp_path
    )
    await controller.drive(sid, [TextBlock(text="go")])
    completed = _completed(recorder)
    assert completed.payload.outcome == "success"
    assert list(completed.payload.outputs) == [TextBlock(text="modified")]


async def test_hook_cannot_widen_an_approval_denial(tmp_path: Path) -> None:
    async def deny_echo(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        return (
            PolicyDeny(reason="policy-no")
            if call.tool_name == "echo"
            else PolicyAllow()
        )

    registry = HookRegistry()
    registry.register(LifecyclePoint.before_tool_use, lambda _p: ToolGateAllow())
    recorder = Recorder()
    controller, sid, _ = build_with_hooks(
        tool_script("echo", text="ping"),
        recorder,
        registry,
        working_scope=tmp_path,
        decide=deny_echo,
    )
    await controller.drive(sid, [TextBlock(text="go")])
    completed = _completed(recorder)
    assert completed.payload.outcome == "failure"
    assert completed.payload.error.reason == "policy-no"  # approval's deny stands
