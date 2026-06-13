"""The trace data model — a nested span tree over recorded streams
(contracts/observability.md; FR-030-FR-032).

Nests loop -> iteration -> run -> tool_call / turn, each span keyed by public ids
and the event ``sequence``. Metadata only — no content or arguments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from loopplane.engineering import LoopEvent
    from loopplane.events import RuntimeEvent

SpanKind = Literal["loop", "iteration", "run", "tool_call", "turn"]


@dataclass(frozen=True)
class TraceSpan:
    kind: SpanKind
    identifier: str
    sequence: int
    children: tuple[TraceSpan, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Trace:
    root: TraceSpan | None


def build_trace(
    loop_events: Sequence[LoopEvent],
    run_events_by_session: Mapping[str, Sequence[RuntimeEvent]] | None = None,
) -> Trace:
    """Build a metadata-only span tree nesting loop -> iteration -> run -> tool/turn.
    A session with no correlated run stream yields a childless run span; an empty
    loop stream yields ``Trace(root=None)`` (FR-030-FR-032)."""

    if not loop_events:
        return Trace(root=None)

    by_session = run_events_by_session if run_events_by_session is not None else {}
    starts: dict[int, int] = {}
    sessions: dict[int, str] = {}
    for event in loop_events:
        index = event.iteration_index
        if index is None:
            continue
        starts.setdefault(index, event.sequence)
        if event.type == "loop_iteration_completed" and event.session_id is not None:
            sessions[index] = event.session_id

    iteration_spans: list[TraceSpan] = []
    for index in sorted(starts):
        children: tuple[TraceSpan, ...] = ()
        session_id = sessions.get(index)
        if session_id is not None:
            children = (
                _run_span(session_id, starts[index], by_session.get(session_id, ())),
            )
        iteration_spans.append(
            TraceSpan(
                kind="iteration",
                identifier=str(index),
                sequence=starts[index],
                children=children,
            )
        )

    root = TraceSpan(
        kind="loop",
        identifier=loop_events[0].loop_id,
        sequence=loop_events[0].sequence,
        children=tuple(iteration_spans),
    )
    return Trace(root=root)


def _run_span(
    session_id: str, sequence: int, run_events: Sequence[RuntimeEvent]
) -> TraceSpan:
    children: list[TraceSpan] = []
    for event in run_events:
        if event.type == "tool-call-started":
            children.append(
                TraceSpan(
                    kind="tool_call",
                    identifier=str(event.sequence),
                    sequence=event.sequence,
                )
            )
        elif event.type == "turn-completed":
            children.append(
                TraceSpan(
                    kind="turn", identifier=str(event.sequence), sequence=event.sequence
                )
            )
    children.sort(key=lambda span: span.sequence)
    return TraceSpan(
        kind="run", identifier=session_id, sequence=sequence, children=tuple(children)
    )
