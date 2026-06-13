# Contract: Observability Transforms

The public surface of `loopplane.inspect`. Every transform is deterministic (sequence-ordered, never
wall-clock), metadata-only, read-only, and fail-safe. Behaviour is normative; signatures are illustrative.

## Loop & run diagnostics (FR-010-FR-021)

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
    terminal_status: str | None

def loop_diagnostics(events: Sequence[LoopEvent]) -> LoopDiagnostics: ...

@dataclass(frozen=True)
class RunDiagnostics:
    tool_calls: int
    turns: int
    errors: int
    termination_reason: str | None

def run_diagnostics(events: Sequence[RuntimeEvent]) -> RunDiagnostics: ...
```

- `loop_diagnostics` counts `retry_scheduled` / `repair_requested` / `human_review_requested` by `type` and
  reuses the Phase-3 `reconstruct_state` for runs + the latest validation/evaluation + terminal status
  (FR-010, SC-008). `run_diagnostics` counts `tool-call-started` / `turn-completed` / `diagnostic` by `type`
  and reads the `run-terminated` reason (FR-020). Empty ⇒ zero/`None`; unknown type ⇒ skipped (FR-011/FR-021).

## Trace (FR-030-FR-032)

```python
SpanKind = Literal["loop", "iteration", "run", "tool_call", "turn"]

@dataclass(frozen=True)
class TraceSpan:
    kind: SpanKind
    identifier: str
    sequence: int
    children: tuple[TraceSpan, ...] = ()

@dataclass(frozen=True)
class Trace:
    root: TraceSpan | None

def build_trace(
    loop_events: Sequence[LoopEvent],
    run_events_by_session: Mapping[str, Sequence[RuntimeEvent]] = {},
) -> Trace: ...
```

- Nests loop → iteration → run → tool_call / turn keyed by public ids + `sequence`; metadata only — no
  content/arguments (FR-031). A `session_id` with no correlated stream ⇒ a childless run span (FR-032); an
  empty loop stream ⇒ `Trace(root=None)`.

## Debug timeline (FR-040-FR-041)

```python
@dataclass(frozen=True)
class TimelineEntry:
    sequence: int
    type: str
    depth: int
    open: bool = False

@dataclass(frozen=True)
class Timeline:
    entries: tuple[TimelineEntry, ...]

def build_timeline(events: Sequence[SequencedEvent]) -> Timeline: ...
```

- Entries ordered by `sequence` (stable); a started event is paired with its completion; an unpaired start is
  `open=True`; duplicate/out-of-order sequences are sorted deterministically (FR-041, SC-007).

## Event replay (FR-050-FR-051)

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

- Awaits `sink(event)` for each recorded event in recorded order, bracketed by a start → complete cycle;
  returns `ReplaySummary(delivered, complete=True)`. Reads recorded events only; starts no run (FR-051).

## Determinism, metadata-only & fail-safe (NFR-001/002/005)

- The same recorded stream ⇒ an identical trace / timeline / replay order / diagnostics every run.
- Only `type` / `sequence` / ids / terminal reasons are read — never content, arguments, or outputs.
- Empty ⇒ empty; unknown type ⇒ skipped; unpaired start ⇒ open span; missing correlated run ⇒ childless
  span — never a crash.
