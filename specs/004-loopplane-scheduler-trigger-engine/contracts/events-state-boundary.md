# Contract: Scheduler Events, Trigger State & Boundary

**Feature**: `004-loopplane-scheduler-trigger-engine` | FR-050–FR-052, FR-080–FR-081, FR-090–FR-092

The scheduler-level event stream, the in-process Trigger State it reconstructs, and the boundary that
keeps the scheduler strictly above the loop layer.

## Scheduler Events (FR-080–FR-081)

```python
SCHEDULER_SCHEMA_VERSION = "1.0"

SchedulerEventType = Literal[
    "trigger_registered", "trigger_fired", "run_skipped", "run_caught_up",
    "run_coalesced", "trigger_paused", "trigger_resumed", "condition_error",
    "scheduler_stopped",
]

@dataclass(frozen=True)
class SchedulerEvent:
    type: SchedulerEventType
    sequence: int                       # monotonic per Scheduler
    clock_time: float
    trigger_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEDULER_SCHEMA_VERSION

SchedulerEventSink = Callable[[SchedulerEvent], Awaitable[None]]
```

**Requirements**

- MUST emit the listed types at the appropriate points (FR-080), each carrying `trigger_id` (where
  applicable) and the `clock_time` from the injected Clock.
- MUST be emitted in deterministic order; the ordered stream MUST be sufficient to reconstruct Trigger
  State (FR-081, SC-006).
- MUST be a **distinct** stream — it never wraps, replaces, or re-emits Loop Events or Runtime Events
  (FR-080). The vocabulary is versioned and evolves additively; consumers tolerate unknown future types.
- Observation MUST default **off**: events are always computed for control/reconstruction, but emission to
  an external sink only happens when an observation flag is enabled, with zero behavior change otherwise
  (FR-081, NFR-005, SC-009).

## Trigger State (FR-050–FR-052)

`TriggerState` shape and invariants are defined in
[data-model.md](../data-model.md#3-triggerstate-fr-050fr-052). Contract obligations restated:

- MUST carry `trigger_id`, `enabled`, `last_fired`, `next_due`, `fire_count`, `missed_ticks`,
  `last_condition_value`, and `last_run_ref` (FR-050).
- MUST reference the most recent Scheduled Loop Run by reference only — never copying `LoopState` or run
  history (FR-051).
- MUST be reconstructable from the ordered Scheduler Event stream (FR-052):

```python
def reconstruct_states(events: Sequence[SchedulerEvent]) -> dict[str, TriggerState]: ...
```

- Durable, cross-restart persistence is a **reserved extension point**, named but not built (FR-091).

## Boundary (FR-090–FR-092, NFR-003)

The scheduler composes the loop layer **only** through the Phase-3 public surface:

```python
from loopplane.engineering import (
    run_loop, LoopDefinition, LoopOutcome,
    ManualTrigger, IntervalTrigger, ConditionTrigger,
)
```

The scheduler MUST NOT:

- import or call any Phase-1 internal (`loopplane.controller`, `.gateway`, `.loop`, `.events.EventEmitter`,
  `.memory`, `.checkpoint`, `.artifacts`, `.approval`, `.observability`), any Phase-2 host internal
  (`loopplane.host.*` assembly), or any Phase-3 loop-control internal
  (`loopplane.engineering.controller`'s `LoopController` mechanics) directly (FR-090);
- start a Scheduled Loop Run by any path other than `run_loop` (FR-002, FR-090);
- re-implement validation, retry, repair, evaluation, or the loop lifecycle (FR-090);
- implement any out-of-scope product layer — a distributed/durable queue, a queue-worker system, a
  background OS daemon, multi-process/cross-host scheduling, persistent Trigger State, cron-expression
  parsing, cloud deployment, web/UI, multi-user tenancy, or wall-clock guarantees (FR-092).

> Importing the Phase-3 **value types and the `run_loop` function** is the intended composition path.
> Reaching into `LoopController` internals or any lower-layer module is the prohibited reach-through.

## Reserved extension points (named, not built) — FR-091

- A distributed or durable queue, and multi-process / cross-host scheduling.
- Persistent Trigger State across process restarts.
- Cron-expression parsing.
- A background OS daemon (the scheduler is poll-driven this phase).

## Auditability (NFR-003, SC-002, SC-010)

- An import-boundary test MUST assert `loopplane.scheduling` imports only `loopplane.engineering` (the
  `run_loop` surface + trigger/value types) and standard library — never a prohibited Phase-1/2/3 internal.
- 100% of Scheduled Loop Runs in the suite MUST go through `run_loop` (SC-002).
- A public-safety scan over committed Phase-4 files MUST find zero private references (SC-010, NFR-004).
