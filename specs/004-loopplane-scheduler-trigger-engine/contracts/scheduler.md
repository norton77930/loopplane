# Contract: Scheduler & Registry

**Feature**: `004-loopplane-scheduler-trigger-engine` | FR-001–FR-004, FR-020–FR-021, FR-070–FR-073

The local, in-process owner of the trigger registry and the Clock. It decides *when* to start a Loop Run
and starts it **only** through the Phase-3 `run_loop` entry point. Signatures are design intent for the
implementation phase.

## `Scheduler`

```python
class Scheduler:
    def __init__(self, clock: Clock, *, on_event: SchedulerEventSink | None = None) -> None: ...

    # Registration (FR-001, FR-004)
    def register_manual(self, trigger_id: str, definition: LoopDefinition) -> None: ...
    def register_interval(
        self, trigger_id: str, definition: LoopDefinition, *,
        interval_seconds: float, start_immediately: bool = False,
        missed_run_policy: MissedRunPolicy = "skip",
    ) -> None: ...
    def register_condition(
        self, trigger_id: str, definition: LoopDefinition, *,
        predicate: Callable[[], bool], mode: ConditionMode = "edge",
    ) -> None: ...
    def unregister(self, trigger_id: str) -> None: ...

    # Lifecycle (FR-070-FR-071)
    def pause(self, trigger_id: str) -> None: ...
    def resume(self, trigger_id: str) -> None: ...
    def stop(self) -> None: ...
    async def drain(self) -> None: ...

    # Firing (FR-002, FR-020, FR-030-FR-040)
    async def start(self, trigger_id: str) -> LoopOutcome: ...   # manual on-demand fire
    async def poll(self) -> list[LoopOutcome]: ...               # fire all due/satisfied

    # Inspection (FR-050)
    def trigger_state(self, trigger_id: str) -> TriggerState: ...
    def trigger_ids(self) -> tuple[str, ...]: ...
```

## Contract requirements

- **Run invocation (FR-002, FR-090, SC-002)**: every Scheduled Loop Run MUST be started by
  `await run_loop(registration.definition, ...)`. The Scheduler MUST NOT call any Phase-1/2/3 internal,
  drive sessions, or re-implement the loop lifecycle.
- **Registry (FR-004)**: `register_*` MUST validate inputs and raise a public-safe `SchedulerError` on a
  duplicate or empty `trigger_id`, a non-positive interval (FR-033), or a condition trigger without a
  predicate. `start`/`pause`/`resume`/`unregister` on an unknown id MUST raise `SchedulerError` and start
  no Loop Run (US1.3).
- **Manual fire (FR-020-FR-021)**: `start(id)` starts exactly one Scheduled Loop Run, returns its
  `LoopOutcome`, and updates Trigger State (fire count, last-fired from the Clock).
- **Poll (FR-030-FR-040)**: `poll()` reads `clock.now()`, fires every due interval trigger and every
  satisfied condition trigger (in **registration order**, FR-073), and returns the outcomes in firing
  order. Manual triggers never auto-fire in `poll()`.
- **Serialization (FR-072, SC-007)**: `poll()` fires due triggers **sequentially** (awaiting each
  `run_loop` before the next); a re-entrancy guard MUST reject overlapping `poll()`/`start()` so at most
  one Scheduled Loop Run is ever in flight. A host opts into concurrency only by driving multiple
  Schedulers itself.
- **Lifecycle (FR-070-FR-071)**: `stop()` (or a not-yet-started Scheduler) MUST fire nothing and leave
  `next_due` unchanged. `pause(id)` MUST stop a trigger from firing until `resume(id)`. `drain()` MUST let
  the in-flight run finish (there is at most one), start no new runs, and stop cleanly.
- **Determinism (NFR-002, SC-008)**: given identical Clock advancement and scripted loops/predicates,
  `poll()` MUST produce identical firing order, count, and outcomes.

## `SchedulerError`

A public-safe `ValueError` subclass with a field-level message (FR-004); it never carries a secret or
private path (NFR-004).
