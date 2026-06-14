"""Runnable example: observe and gate the agent with lifecycle hooks (unit 015).

Public-safe and credential-free. A ``HookRegistry`` holds callbacks fired at the
runtime's lifecycle points. Here one observer records every successful tool call
(an audit trail), and one before-tool gate denies a named tool. The runtime is
composed directly from the ``RuntimeController`` with a shared ``HookDispatcher``.
Hooks are additive and inert by default — omit the dispatcher and the runtime
behaves exactly as before. Tool-boundary hooks fire inside the Tool Gateway, and
a hook never executes a tool itself (Constitution V).

Run::

    python examples/hooks_quickstart.py
"""

from __future__ import annotations

from pathlib import Path

import anyio

from loopplane.context import RunContext
from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.gateway import ToolGateway
from loopplane.hooks import (
    AfterToolUsePayload,
    BeforeToolUsePayload,
    HookRegistry,
    LifecyclePoint,
    ToolGateAllow,
    ToolGateDecision,
    ToolGateDeny,
)
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)

ECHO = ToolDescriptor(
    name="echo",
    description="Echo the input text back.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
    read_only=True,
)
DANGER = ToolDescriptor(
    name="danger",
    description="A tool the policy will block.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)


async def echo_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text=str(call_input["text"]))]


async def danger_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text="danger ran")]  # never reached — the gate denies it


async def run_demo() -> None:
    registry = HookRegistry()

    audit: list[str] = []
    registry.register(
        LifecyclePoint.after_tool_use,
        lambda p: (
            audit.append(p.tool_name) if isinstance(p, AfterToolUsePayload) else None
        ),
    )

    def guard(payload: BeforeToolUsePayload) -> ToolGateDecision:
        if payload.tool_name == "danger":
            return ToolGateDeny(reason="blocked by policy")
        return ToolGateAllow()

    registry.register(LifecyclePoint.before_tool_use, guard)

    dispatcher = HookDispatcher(registry)
    model = ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    ToolCallRequest(
                        call_id="c1", tool_name="echo", input={"text": "ping"}
                    )
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(
                increments=[
                    ToolCallRequest(call_id="c2", tool_name="danger", input={})
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="all done")]),
        ],
        context_capacity=100_000,
    )
    gateway = ToolGateway(hooks=dispatcher)
    gateway.register(ECHO, echo_handler)
    gateway.register(DANGER, danger_handler)

    events: list[RuntimeEvent] = []

    async def sink(event: RuntimeEvent) -> None:
        events.append(event)

    controller = RuntimeController(
        model=model, gateway=gateway, event_sink=sink, hooks=dispatcher
    )
    session_id = controller.create_session(working_scope=Path.cwd())
    await controller.drive(session_id, [TextBlock(text="please run the tools")])

    print("Audited successful tool calls:", audit)  # ['echo']
    denied = [
        e.payload.call_id
        for e in events
        if e.type == "tool-call-completed" and e.payload.outcome == "failure"
    ]
    print("Denied tool calls:", denied)  # ['c2'] — 'danger' never executed


if __name__ == "__main__":
    anyio.run(run_demo)
