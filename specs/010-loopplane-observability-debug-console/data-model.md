# Data Model: Observability & Debug-Console Layer (Phase-10)

All types are public-safe, metadata-only value types. The layer owns no runtime state, drives nothing, and
reads only declared metadata fields. Types mirror the existing style: frozen dataclasses + `Protocol`,
`from __future__ import annotations`, `TYPE_CHECKING` imports to keep the boundary tight.

## 0. Sequenced-event protocol

```python
class SequencedEvent(Protocol):
    type: str          # the event-type discriminator (LoopEventType or a RuntimeEvent type literal)
    sequence: int      # monotonic within a run / loop
```

- `LoopEvent` and every `RuntimeEvent` satisfy this structurally; the timeline accepts either.

## 1. Loop diagnostics (US1, FR-010-FR-011)

```python
@dataclass(frozen=True)
class LoopDiagnostics:
    iterations: int
    runs: int
    retries: int
    repairs: int
    human_reviews: int
    latest_validation_status: str | None
    latest_evaluation_label: str | None
    terminal_status: str | None        # "loop_completed" / "loop_failed" / None

def loop_diagnostics(events: Sequence[LoopEvent]) -> LoopDiagnostics: ...
```

- Counts `retry_scheduled` / `repair_requested` / `human_review_requested` by `type`; reuses the Phase-3
  `reconstruct_state(events)` for `runs` (its run references), the latest validation/evaluation outcomes, and
  the terminal status. An empty stream ⇒ all-zero / `None`; an unknown loop type ⇒ skipped (FR-011).

## 2. Run diagnostics (US2, FR-020-FR-021)

```python
@dataclass(frozen=True)
class RunDiagnostics:
    tool_calls: int
    turns: int
    errors: int
    termination_reason: str | None

def run_diagnostics(events: Sequence[RuntimeEvent]) -> RunDiagnostics: ...
```

- Counts by `event.type`: `tool-call-started` ⇒ `tool_calls`, `turn-completed` ⇒ `turns`, `diagnostic` ⇒
  `errors`; reads the `run-terminated` event's reason into `termination_reason`. Metadata only; empty ⇒
  zero / `None`; unknown type ⇒ skipped (FR-021).

## 3. Trace data model (US3, FR-030-FR-032)

```python
SpanKind = Literal["loop", "iteration", "run", "tool_call", "turn"]

@dataclass(frozen=True)
class TraceSpan:
    kind: SpanKind
    identifier: str            # loop_id / iteration index / session_id / tool-call sequence / turn sequence
    sequence: int
    children: tuple[TraceSpan, ...] = ()

@dataclass(frozen=True)
class Trace:
    root: TraceSpan | None     # the loop span, or None for an empty stream

def build_trace(
    loop_events: Sequence[LoopEvent],
    run_events_by_session: Mapping[str, Sequence[RuntimeEvent]] = {},
) -> Trace: ...
```

- Nests loop → iteration (by `iteration_index`) → run (by `session_id`) → tool_call / turn (from the
  correlated `RuntimeEvent` stream). Each span carries ids / kind / `sequence` / children only — no content
  or arguments (FR-031). A `session_id` with no correlated stream ⇒ a childless run span (FR-032). An empty
  loop stream ⇒ `Trace(root=None)`.

## 4. Debug timeline (US4, FR-040-FR-041)

```python
@dataclass(frozen=True)
class TimelineEntry:
    sequence: int
    type: str
    depth: int                 # nesting depth (loop=0, iteration=1, run=2, tool/turn=3)
    open: bool = False         # a started span with no matching completion

@dataclass(frozen=True)
class Timeline:
    entries: tuple[TimelineEntry, ...]

def build_timeline(events: Sequence[SequencedEvent]) -> Timeline: ...
```

- Orders entries by `sequence` (stable); pairs a started event with its completion (`*_started` ↔
  `*_completed`, `tool-call-started` ↔ `tool-call-completed`); an unpaired start is marked `open=True`. A
  duplicate / out-of-order `sequence` is sorted deterministically (FR-041, SC-007).

## 5. Event replay (US5, FR-050-FR-051)

```python
@dataclass(frozen=True)
class ReplaySummary:
    delivered: int
    complete: bool

async def replay(
    events: Sequence[SequencedEvent],
    sink: Callable[[SequencedEvent], Awaitable[None]],
) -> ReplaySummary: ...
```

- Awaits `sink(event)` for each recorded event **in recorded order**, bracketed by a start → complete cycle,
  and returns `ReplaySummary(delivered=len(events), complete=True)`. It reads recorded events only and starts
  no run (FR-051). An empty stream ⇒ `ReplaySummary(0, True)`.

## Relationships

```text
LoopEvent[]  ──loop_diagnostics──►  LoopDiagnostics        (reuses reconstruct_state)
RuntimeEvent[]  ──run_diagnostics──►  RunDiagnostics
LoopEvent[] + {session_id: RuntimeEvent[]}  ──build_trace──►  Trace (TraceSpan tree)
SequencedEvent[]  ──build_timeline──►  Timeline (sequence-ordered, paired)
SequencedEvent[]  ──replay(sink)──►  ReplaySummary  (sink receives events in recorded order)
```

## Validation & invariants

- **Determinism (NFR-001)**: pure functions of the recorded stream; ordering by `sequence`, never wall-clock.
- **Metadata-only (NFR-002)**: only `type` / `sequence` / ids / terminal reasons are read; no content payload.
- **Read-only (NFR-006)**: drives no run, re-emits no live-bus event; replay only feeds a supplied sink.
- **Fail-safe (NFR-005)**: empty ⇒ empty; unknown type ⇒ skipped; unpaired start ⇒ open span; missing
  correlated run ⇒ childless span — never a crash.
