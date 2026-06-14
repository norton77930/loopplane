"""Render a run from the normalized event stream to a terminal (spec FR-004,
FR-009).

``EventRenderer`` is an ``EventSink`` that writes only public-safe metadata and
assistant text — never raw tool input/output, a secret, a private path, or an
exception. Tool I/O stays inside the runtime; the CLI shows the tool name and
outcome only.
"""

from __future__ import annotations

from typing import TextIO

from loopplane.events.envelope import (
    AssistantOutputIncrementEvent,
    DiagnosticEvent,
    RunTerminatedEvent,
    RuntimeEvent,
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
)


class EventRenderer:
    """An ``EventSink`` writing metadata-safe terminal output to ``out``."""

    def __init__(self, out: TextIO) -> None:
        self._out = out

    async def __call__(self, event: RuntimeEvent) -> None:
        if isinstance(event, AssistantOutputIncrementEvent):
            self._out.write(event.payload.text)
        elif isinstance(event, ToolCallStartedEvent):
            self._out.write(f"\n[tool {event.payload.tool_name}]")
        elif isinstance(event, ToolCallCompletedEvent):
            self._out.write(f" {event.payload.outcome}\n")
        elif isinstance(event, RunTerminatedEvent):
            payload = event.payload
            self._out.write(
                f"\n[run {payload.reason}, {payload.turns_taken} turn(s)]\n"
            )
        elif isinstance(event, DiagnosticEvent):
            self._out.write(f"\n[{event.payload.severity}] {event.payload.message}\n")
