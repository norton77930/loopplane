# Phase 1 Data Model: Scheduler & Trigger Engine

**Feature**: `004-loopplane-scheduler-trigger-engine` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

This model defines the **scheduler-layer** entities only. It references — and never redefines — the
Phase-3 entities (`LoopDefinition`, `run_loop`, `LoopOutcome`, `LoopState`, and the trigger contracts
`ManualTrigger` / `IntervalTrigger` / `ConditionTrigger`). All types are illustrative design intent for
the implementation phase, and all are public-safe (FR-001 / NFR-004).

## Entity overview

```text
Scheduler (in-process; owns the registry + Clock)
 ├─ clock:        Clock                       (VirtualClock | RealClock)
 ├─ registry:     {trigger_id -> TriggerRegistration}
 ├─ states:       {trigger_id -> TriggerState}
 └─ on_event:     SchedulerEventSink?          (off by default)

TriggerRegistration (frozen)                  TriggerState (mutable, scheduler-owned)
 ├─ trigger_id, definition (-> Phase-3)        ├─ trigger_id, enabled
 ├─ trigger (Manual|Interval|Condition)        ├─ last_fired, next_due, fire_count
 ├─ predicate? (condition only)                ├─ missed_ticks, last_condition_value
 ├─ mode? (condition: edge|level)              └─ last_run_ref (-> LoopOutcome by ref)
 └─ missed_run_policy

SchedulerEvent[] (ordered; reconstructs TriggerState)   LoopOutcome (Phase-3, by reference)
```

---

## 1. Clock  (FR-010–FR-012)

An injectable monotonic time source. The Scheduler reads time only through it.

```python
class Clock(Protocol):
    def now(self) -> float: ...        # monotonic seconds

class VirtualClock:                    # deterministic test instrument (no wall clock)
    def now(self) -> float: ...
    def advance(self, seconds: float) -> None: ...
    def set(self, t: float) -> None: ...

class RealClock:                       # thin time.monotonic adapter (production)
    def now(self) -> float: ...
```

**Rules**: `now()` is non-decreasing for `RealClock`; a `VirtualClock` regression (Decision: backward
jump) is ignored for due calculations (edge case). All scheduler decisions derive from `now()` (FR-011).

---

## 2. TriggerRegistration  (FR-001, FR-004, FR-020–FR-040, FR-060)

Frozen record bound to a stable `trigger_id`.

| Field | Type | Notes |
|---|---|---|
| `trigger_id` | `str` | stable, unique within a Scheduler (FR-004). |
| `definition` | `LoopDefinition` | the Phase-3 loop the trigger fires (FR-001). |
| `trigger` | `ManualTrigger \| IntervalTrigger \| ConditionTrigger` | the Phase-3 contract being made executable. |
| `predicate` | `Callable[[], bool] \| None` | required for a condition trigger; host logic (FR-040). |
| `mode` | `ConditionMode \| None` | `edge` / `level` for a condition trigger (FR-041). |
| `missed_run_policy` | `MissedRunPolicy` | `skip` / `catch_up_once` / `coalesce` (FR-060). |

**Validation (FR-004, FR-033)**: unique non-empty `trigger_id`; an `IntervalTrigger.interval_seconds > 0`;
a condition trigger has a `predicate`; registering a duplicate id or starting an unknown id raises a
clear, public-safe `SchedulerError`.

`MissedRunPolicy = Literal["skip", "catch_up_once", "coalesce"]`
`ConditionMode = Literal["edge", "level"]`

---

## 3. TriggerState  (FR-050–FR-052)

The per-trigger in-process record, **mutable** and scheduler-owned; references runs only.

| Field | Type | Notes |
|---|---|---|
| `trigger_id` | `str` | (FR-050). |
| `enabled` | `bool` | paused triggers are `enabled=False` (FR-071). |
| `last_fired` | `float \| None` | Clock time of the most recent fire (FR-050). |
| `next_due` | `float \| None` | next due time for an interval trigger; `None` for manual/condition (FR-050). |
| `fire_count` | `int` | total Scheduled Loop Runs started (FR-050). |
| `missed_ticks` | `int` | cumulative missed ticks recorded by the missed-run policy (FR-060). |
| `last_condition_value` | `bool` | prior predicate value for edge detection (FR-041). |
| `last_run_ref` | `LoopRunRef \| None` | reference to the most recent Scheduled Loop Run (FR-051). |

`LoopRunRef` = `{ trigger_id: str, terminal_event: str \| None, paused: bool }` — derived from the
`LoopOutcome`, by reference; the scheduler never copies `LoopState` or run history (FR-051).

**Invariants**: never copies or owns Loop State (FR-051); reconstructable from the ordered Scheduler
Event stream (FR-052, SC-006); durable cross-restart persistence is reserved (FR-091).

---

## 4. SchedulerEvent  (FR-080–FR-081)

A scheduler-level lifecycle record, **distinct** from Loop Events and Runtime Events (FR-080). Frozen;
emitted in deterministic order.

**Common envelope fields**:

| Field | Type | Notes |
|---|---|---|
| `type` | `SchedulerEventType` | the event kind (closed-but-extensible, FR-081). |
| `schema_version` | `str` | versioned, additive. |
| `sequence` | `int` | monotonic per Scheduler. |
| `trigger_id` | `str \| None` | the trigger it pertains to (where applicable). |
| `clock_time` | `float` | the Clock time at emission (FR-080). |
| `payload` | type-specific | e.g. missed-tick count, condition error message, run reference. |

**Event types** (FR-080):

| Type | Emitted when |
|---|---|
| `trigger_registered` | a trigger is registered. |
| `trigger_fired` | a Scheduled Loop Run is started (carries the run reference). |
| `run_skipped` | a missed tick is skipped (skip policy). |
| `run_caught_up` | a make-up run starts (catch_up_once). |
| `run_coalesced` | missed ticks collapse into one run (coalesce). |
| `trigger_paused` / `trigger_resumed` | a trigger is paused / resumed. |
| `condition_error` | a predicate raised (diagnostic; no run started). |
| `scheduler_stopped` | the Scheduler stops / drains. |

**Guarantees**: deterministic order (NFR-002); the ordered stream alone reconstructs Trigger State
(FR-052, SC-006); never wraps/re-emits Loop or Runtime Events (FR-080).

---

## 5. Scheduler  (FR-001–FR-003, FR-070–FR-073)

The in-process owner of the registry and the Clock (design intent — see
[contracts/scheduler.md](./contracts/scheduler.md)).

```python
class Scheduler:
    def __init__(self, clock: Clock, *, on_event: SchedulerEventSink | None = None) -> None: ...

    def register(self, registration: TriggerRegistration) -> None: ...   # + helpers (manual/interval/condition)
    def unregister(self, trigger_id: str) -> None: ...
    def pause(self, trigger_id: str) -> None: ...
    def resume(self, trigger_id: str) -> None: ...

    async def start(self, trigger_id: str) -> LoopOutcome: ...           # manual fire (US1)
    async def poll(self) -> list[LoopOutcome]: ...                       # fire all due/satisfied (US2-4)
    async def drain(self) -> None: ...                                   # finish in-flight, stop
    def stop(self) -> None: ...

    def trigger_state(self, trigger_id: str) -> TriggerState: ...
```

**Lifecycle states**: a `running` flag (start/stop), per-trigger `enabled`. `stop()` / not-running ⇒
`poll()`/`start()` fire nothing and leave `next_due` unchanged (FR-071). `poll()` and `start()` are
**re-entrancy-guarded** so two Scheduled Loop Runs are never in flight at once (FR-072, SC-007).

## State transitions (one `poll()` over a due interval trigger)

```text
 poll() ─► read clock.now()
        ─► for each enabled trigger, in registration order (deterministic, FR-073):
              interval:  while now >= next_due  → DUE
                         apply missed_run_policy → start ≤1 Loop Run via run_loop
                         advance next_due; update fire_count / missed_ticks
              condition: evaluate predicate (guarded)
                         edge:  fire on false→true ; level: fire on true
              manual:    never auto-fires in poll() (only start(id))
        ─► each fired trigger: emit trigger_fired; record last_run_ref (by ref)
        ─► return the list of LoopOutcomes (in firing order)
```

Every fire goes through `await run_loop(...)`, awaited before the next (serialized, FR-072). The
Scheduler reads only the Phase-3 surface; it owns no loop or runtime internal (FR-090).

## Referenced Phase-3 entities (not redefined)

| Entity | Source | Referenced as |
|---|---|---|
| `LoopDefinition` | `loopplane.engineering` | the registered loop a trigger fires |
| `run_loop` | `loopplane.engineering` | the only path to start a Scheduled Loop Run |
| `LoopOutcome` / `LoopState` | `loopplane.engineering` | run result, kept by reference (`LoopRunRef`) |
| `ManualTrigger` / `IntervalTrigger` / `ConditionTrigger` | `loopplane.engineering` | the trigger contracts made executable |
