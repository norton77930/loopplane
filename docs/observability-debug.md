# Observability & Debug Console (`loopplane.inspect`)

Make a run or loop **inspectable after the fact** — deterministically, public-safe, metadata-only, and
offline. The layer turns recorded event streams into inspection value structures: loop and run diagnostics,
a trace, a debug timeline, and event replay.

It is a **read-only data layer**. It consumes the recorded Phase-3 **Loop Event** stream (correlated to its
Agent Runs by `session_id`, reusing `reconstruct_state`) and the recorded Phase-1 **Runtime Event** stream —
exactly as Constitution VI prescribes for trace/observability consumers. It **never** drives a run, never
re-emits the live buses, reads only metadata, and ships **no** frontend.

## The pieces

| Piece | What it does |
|---|---|
| `loop_diagnostics(loop_events)` | `LoopDiagnostics`: iterations / runs / retries / repairs / human-reviews + latest validation/evaluation outcomes + terminal status (reusing `reconstruct_state`). |
| `run_diagnostics(runtime_events)` | `RunDiagnostics`: tool-call / turn / error counts + the termination reason. |
| `build_trace(loop_events, run_events_by_session)` | A `Trace` of `TraceSpan`s nesting loop → iteration → run → tool/turn, keyed by public ids + sequence. |
| `build_timeline(events)` | A `Timeline` of sequence-ordered `TimelineEntry`s, pairing started/completed spans and marking unpaired starts open. |
| `replay(events, sink)` | Feeds a recorded stream to a sink in recorded order; returns a `ReplaySummary`. |
| `SequencedEvent` | The shared protocol (`type` + `sequence`) satisfied by Loop and Runtime events. |

## Using it

```python
from loopplane.inspect import loop_diagnostics, build_trace, build_timeline

# The host captures the streams (via the Phase-3 LoopEventSink / Phase-1 EventSink) and inspects them after:
summary = loop_diagnostics(recorded_loop_events)
trace = build_trace(recorded_loop_events, {session_id: recorded_run_events})
timeline = build_timeline(recorded_loop_events)
```

Capturing the streams is the host's concern; this layer only transforms them. See
[`examples/inspect_quickstart.py`](../examples/inspect_quickstart.py).

## Determinism, metadata-only, read-only

- **Deterministic**: no I/O, clock, or randomness; ordering is by the events' monotonic `sequence`, never
  wall-clock — the same recorded stream yields an identical result every run.
- **Metadata-only**: only `type` / `sequence` / ids / terminal reasons are read; no conversation content,
  tool arguments, or outputs is ever surfaced.
- **Read-only**: the layer drives zero runs and re-emits zero live-bus events; replay only feeds a supplied
  sink. An import + no-run audit enforces it.
- **Fail-safe**: an empty stream ⇒ empty; an unknown event type ⇒ skipped; an unpaired start ⇒ an open span;
  a session with no correlated run ⇒ a childless span — never a crash.

## Boundary

`loopplane.inspect` imports only `loopplane.engineering` (Loop Events / Loop State) and `loopplane.events`
(Runtime Events). It never imports the controller, the host, the gateway, or a sibling layer, and it starts
no run.

## Reserved extension points (named, not built)

A live or streaming debug console or web UI; remote/distributed trace export beyond the existing Phase-1
OpenTelemetry overlay; persistent trace storage; cross-run/distributed trace correlation; and wall-clock
performance timing or flame graphs.
