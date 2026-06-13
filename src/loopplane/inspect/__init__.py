"""LoopPlane Observability & Debug-Console layer (feature
010-loopplane-observability-debug-console).

Read-only, deterministic, public-safe, **metadata-only** transforms that make runs
and loops inspectable after the fact: loop and run diagnostics, a trace data model,
a debug timeline, and event replay over recorded event streams. It composes only
the public Phase-3 Loop Event/State and Phase-1 Runtime Event surfaces, drives no
run, and never re-emits the live buses (Constitution VI;
contracts/inspect-boundary.md).
"""

from loopplane.inspect.base import SequencedEvent
from loopplane.inspect.diagnostics import (
    LoopDiagnostics,
    RunDiagnostics,
    loop_diagnostics,
    run_diagnostics,
)
from loopplane.inspect.timeline import Timeline, TimelineEntry, build_timeline
from loopplane.inspect.trace import SpanKind, Trace, TraceSpan, build_trace

__all__ = [
    "LoopDiagnostics",
    "RunDiagnostics",
    "SequencedEvent",
    "SpanKind",
    "Timeline",
    "TimelineEntry",
    "Trace",
    "TraceSpan",
    "build_timeline",
    "build_trace",
    "loop_diagnostics",
    "run_diagnostics",
]
