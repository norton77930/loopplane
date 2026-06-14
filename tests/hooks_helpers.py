"""Deterministic, public-safe helpers for the lifecycle-hook integration suites
(feature 015). Credential-free: a scripted model plus a few small tools.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from loopplane.context import RunContext
from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.gateway import PolicyDecider, ToolGateway, ToolHandler
from loopplane.hooks import HookRegistry
from loopplane.hooks.dispatcher import HookDispatcher
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    ScriptEntry,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
    ToolDescriptor,
)

# --- tools ---

ECHO = ToolDescriptor(
    name="echo",
    description="Echo the input text back.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
    concurrency_safe=True,
    read_only=True,
)

WRITER = ToolDescriptor(
    name="writer",
    description="A non-read-only tool that names a file path.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    },
    read_only=False,
)

BOOM = ToolDescriptor(
    name="boom",
    description="A tool that raises during execution.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)


async def echo_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text=str(call_input["text"]))]


async def writer_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text="written")]


async def boom_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    raise RuntimeError("boom-secret-detail")


# --- scripts ---


def tool_script(
    tool_name: str, *, call_id: str = "c1", **call_input: object
) -> list[ScriptEntry]:
    """A turn that calls one tool, then a closing text turn."""
    return [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id=call_id, tool_name=tool_name, input=dict(call_input)
                )
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


def text_script(*texts: str) -> list[ScriptEntry]:
    """One plain-text turn per argument (default one). Each turn ends a run, so
    pass one per expected drive."""
    chosen = texts or ("hi",)
    return [ScriptedTurn(increments=[TextIncrement(text=t)]) for t in chosen]


# --- recorder + builder ---


class Recorder:
    """Records every emitted runtime event in order."""

    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]


def build_with_hooks(
    script: Sequence[ScriptEntry],
    sink: Recorder,
    registry: HookRegistry,
    *,
    working_scope: Path,
    decide: PolicyDecider | None = None,
    failures: list[str] | None = None,
    extra_tools: Sequence[tuple[ToolDescriptor, ToolHandler]] = (),
) -> tuple[RuntimeController, str, HookDispatcher]:
    """A controller + gateway sharing one dispatcher built from ``registry``."""

    on_failure = None
    if failures is not None:

        async def on_failure(message: str) -> None:
            failures.append(message)

    dispatcher = HookDispatcher(registry, on_failure=on_failure)
    model = ScriptedModel(script=script, context_capacity=100_000)
    gateway = ToolGateway(decide=decide, hooks=dispatcher)
    gateway.register(ECHO, echo_handler)
    gateway.register(WRITER, writer_handler)
    gateway.register(BOOM, boom_handler)
    for descriptor, handler in extra_tools:
        gateway.register(descriptor, handler)
    controller = RuntimeController(
        model=model, gateway=gateway, event_sink=sink, hooks=dispatcher
    )
    session_id = controller.create_session(working_scope=working_scope)
    return controller, session_id, dispatcher
