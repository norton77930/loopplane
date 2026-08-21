"""Render a run from the normalized event stream to a terminal (spec FR-004,
FR-009; spec 079 FR-005).

``EventRenderer`` is an ``EventSink`` that writes only public-safe metadata and
assistant text — never raw tool input/output, a secret, a private path, or an
exception. Tool I/O stays inside the runtime; the CLI shows the tool name and
outcome only.

Unit 079 adds two more renderable events: a permission request and an agent
question. Both carry only what an operator needs to decide — for an approval,
the tool's name and the runtime's own input summary; for a question, its text
and options. Neither renders raw tool input. The renderer only *shows* these;
answering them belongs to the interactive loop (``loopplane.cli.session``),
which is the component that holds the input source and the session handle.
"""

from __future__ import annotations

from typing import TextIO

from loopplane.events.envelope import (
    ApprovalRequestedEvent,
    AssistantOutputIncrementEvent,
    DiagnosticEvent,
    QuestionAskedEvent,
    RunTerminatedEvent,
    RuntimeEvent,
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
)

APPROVAL_ANSWERS = "y/n/a/never"
"""The answer legend shown with every permission request."""


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
        elif isinstance(event, ApprovalRequestedEvent):
            request = event.payload
            self._out.write(
                f"\n[approve] {request.tool_name} — {request.input_summary}"
                f"  [{APPROVAL_ANSWERS}]\n"
            )
        elif isinstance(event, QuestionAskedEvent):
            for question in event.payload.questions:
                self._out.write(f"\n[question] {question.text}\n")
                for option in question.options:
                    self._out.write(f"  - {option}\n")
        elif isinstance(event, RunTerminatedEvent):
            payload = event.payload
            self._out.write(
                f"\n[run {payload.reason}, {payload.turns_taken} turn(s)]\n"
            )
        elif isinstance(event, DiagnosticEvent):
            self._out.write(f"\n[{event.payload.severity}] {event.payload.message}\n")
