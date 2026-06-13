"""A passive demonstration consumer (FR-122; SC-009).

Produces a per-run summary using only the public extension surface: the
normalized event stream plus session lifecycle operations (FR-120). It never
imports Agent Loop internals — events are consumed by their public `type`
string, and unknown event types are skipped (FR-063), exactly as a future
scheduler/validator/evaluator layer would.

Usage: pass an instance as (or inside) the controller's `event_sink`; read
`summaries` after each run, or print them live via `on_summary`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from loopplane.events import RuntimeEvent


@dataclass
class RunSummary:
    session_id: str
    turns: int = 0
    output_characters: int = 0
    tool_calls: int = 0
    tool_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    diagnostics: int = 0
    termination_reason: str = ""

    def render(self) -> str:
        return (
            f"run on session {self.session_id[:8]}…: "
            f"{self.turns} turn(s), {self.tool_calls} tool call(s) "
            f"({self.tool_failures} failed), "
            f"{self.input_tokens}+{self.output_tokens} tokens, "
            f"ended: {self.termination_reason}"
        )


class RunSummaryConsumer:
    """An event sink: attach it and it summarizes every completed run."""

    def __init__(self, on_summary: Callable[[RunSummary], None] | None = None) -> None:
        self.summaries: list[RunSummary] = []
        self._active: dict[str, RunSummary] = {}
        self._on_summary = on_summary

    async def __call__(self, event: RuntimeEvent) -> None:
        if event.replay:
            return  # replayed history is not a new run
        summary = self._active.setdefault(
            event.session_id, RunSummary(session_id=event.session_id)
        )
        if event.type == "assistant-output-increment":
            summary.output_characters += len(event.payload.text)
        elif event.type == "turn-completed":
            summary.turns += 1
            summary.input_tokens += event.payload.usage.input_tokens
            summary.output_tokens += event.payload.usage.output_tokens
        elif event.type == "tool-call-completed":
            summary.tool_calls += 1
            if event.payload.outcome == "failure":
                summary.tool_failures += 1
        elif event.type == "diagnostic":
            summary.diagnostics += 1
        elif event.type == "run-terminated":
            summary.termination_reason = event.payload.reason
            self.summaries.append(summary)
            del self._active[event.session_id]
            if self._on_summary is not None:
                self._on_summary(summary)
        # Any other (or future) event type is skipped, per FR-063.
