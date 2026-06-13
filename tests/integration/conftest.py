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
