"""Shared harness assembly for the US1 integration suites."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.controller.controller import RuntimeController
from loopplane.events import RuntimeEvent
from loopplane.gateway import PolicyDecider, ToolGateway, ToolHandler
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptEntry,
    TextBlock,
    ToolDescriptor,
)

ECHO_DESCRIPTOR = ToolDescriptor(
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


async def echo_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text=str(call_input["text"]))]


class EventCollector:
    """An event sink that records every emitted event in order."""

    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]


HarnessFactory = Callable[..., tuple[RuntimeController, str]]


@pytest.fixture
def collector() -> EventCollector:
    return EventCollector()


@pytest.fixture
def harness(tmp_path: Path) -> HarnessFactory:
    """Assemble a controller around a scripted model and the echo tool."""

    def make(
        script: Sequence[ScriptEntry],
        sink: EventCollector,
        *,
        turn_budget: int | None = None,
        context_capacity: int = 100_000,
        decide: PolicyDecider | None = None,
        call_timeout_seconds: float | None = None,
        extra_tools: Sequence[tuple[ToolDescriptor, ToolHandler]] = (),
    ) -> tuple[RuntimeController, str]:
        model = ScriptedModel(script=script, context_capacity=context_capacity)
        if call_timeout_seconds is not None:
            gateway = ToolGateway(
                decide=decide, call_timeout_seconds=call_timeout_seconds
            )
        else:
            gateway = ToolGateway(decide=decide)
        gateway.register(ECHO_DESCRIPTOR, echo_handler)
        for descriptor, handler in extra_tools:
            gateway.register(descriptor, handler)
        controller = RuntimeController(model=model, gateway=gateway, event_sink=sink)
        session_id = controller.create_session(
            working_scope=tmp_path, turn_budget=turn_budget
        )
        return controller, session_id

    return make


# --- Host integration helpers (feature 002-loopplane-host-interface) ---

from loopplane.host import RuntimeConfig, ToolSpec  # noqa: E402
from loopplane.model import (  # noqa: E402
    ScriptedTurn,
    TextIncrement,
    ToolCallRequest,
)

__all__ = [
    "BIG_TOOL",
    "ECHO_DESCRIPTOR",
    "ECHO_TOOL",
    "EventCollector",
    "RuntimeConfig",
    "big_tool_model",
    "echo_handler",
    "multi_text_model",
    "text_model",
    "tool_then_text_model",
]

ECHO_TOOL = ToolSpec(descriptor=ECHO_DESCRIPTOR, handler=echo_handler)

BIG_DESCRIPTOR = ToolDescriptor(
    name="big",
    description="Emit a large blob to exercise artifact offload.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)


async def big_handler(
    call_input: dict[str, object], context: RunContext
) -> list[OutputBlock]:
    return [TextBlock(text="X" * 200_000)]


BIG_TOOL = ToolSpec(descriptor=BIG_DESCRIPTOR, handler=big_handler)


def text_model(text: str = "hello") -> ScriptedModel:
    """One plain-text turn ending the run."""

    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=text)])],
        context_capacity=100_000,
    )


def multi_text_model(*texts: str) -> ScriptedModel:
    """One text turn per argument — enough script for several sequential runs."""

    return ScriptedModel(
        script=[ScriptedTurn(increments=[TextIncrement(text=t)]) for t in texts],
        context_capacity=100_000,
    )


def tool_then_text_model(tool_name: str = "echo") -> ScriptedModel:
    """A tool-calling turn followed by a closing text turn."""

    return ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[
                    TextIncrement(text="let me use a tool"),
                    ToolCallRequest(
                        call_id="c1", tool_name=tool_name, input={"text": "hello"}
                    ),
                ],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="done")]),
        ],
        context_capacity=100_000,
    )


def big_tool_model() -> ScriptedModel:
    """Calls the oversized 'big' tool, then closes with text."""

    return ScriptedModel(
        script=[
            ScriptedTurn(
                increments=[ToolCallRequest(call_id="c1", tool_name="big", input={})],
                stop_reason="tool-use",
            ),
            ScriptedTurn(increments=[TextIncrement(text="stored")]),
        ],
        context_capacity=100_000,
    )
