# Scheduler & Trigger Engine

The **scheduler layer** (`loopplane.scheduling`) makes the Phase-3 interval and
condition trigger contracts executable. A `Scheduler` owns a registry of triggers
and an injectable `Clock`, decides *when* a trigger fires, and starts every
**Scheduled Loop Run** **only** through the Phase-3 `run_loop` entry point — never
bypassing the loop layer or reaching into Phase-1/2/3 internals.

It is poll-driven and ships no background daemon: a host owns the cadence by
calling `poll()`. A runnable example is
[`examples/scheduler_quickstart.py`](../examples/scheduler_quickstart.py).

> **Loop vs schedule.** The Phase-3 `run_loop` runs one Loop Run to a terminal
> outcome (or a human-review pause). The Phase-4 `Scheduler` decides *when* to
> call `run_loop` — manually, every interval, or on a satisfied condition.

## A first schedule

```python
from loopplane.scheduling import Scheduler, VirtualClock

clock = VirtualClock()              # deterministic; a RealClock is the production adapter
scheduler = Scheduler(clock)
scheduler.register_interval("nightly", my_definition, interval_seconds=60.0)

clock.advance(180.0)                # 3 periods
outcomes = await scheduler.poll()  # fires the due ticks per the missed-run policy
```

## Triggers

| Trigger | Register with | Fires |
|---|---|---|
| Manual | `register_manual(id, definition)` | on `await scheduler.start(id)` |
| Interval | `register_interval(id, definition, interval_seconds=, start_immediately=, missed_run_policy=)` | once per elapsed period on `poll()` |
| Condition | `register_condition(id, definition, predicate=, mode=)` | when the host predicate is satisfied on `poll()` (`edge` or `level`) |

The interval and condition triggers are the Phase-3 *contracts* made executable;
a host owns the `poll()` cadence (its own loop in production, a `VirtualClock` in
tests). Time comes only from the injected `Clock` — **no real sleeping**.

## The Clock

`Clock` is a `now() -> float` monotonic source. `VirtualClock` is advanced
manually (`advance` / `set`) and drives deterministic tests; `RealClock` wraps
`time.monotonic` for production, with identical scheduler decisions. A backward
clock move is ignored for due calculations.

## Missed-run policy

When `poll()` finds the clock advanced past several due ticks, the per-trigger
`missed_run_policy` decides — each starts **at most one** Loop Run:

| Policy | Loop Runs | `next_due` after |
|---|---|---|
| `skip` | 1 (next due) | advanced past the jump |
| `catch_up_once` | 1 (make-up) | advanced past the jump |
| `coalesce` | 1 (collapsed) | `now + period` |

`missed_ticks` records the collapsed ticks. Catch-up can never fire unbounded.

## Lifecycle & serialization

`pause(id)` / `resume(id)` enable or disable a single trigger; `stop()` halts the
Scheduler (it fires nothing and leaves `next_due` unchanged); `drain()` lets the
in-flight run finish and starts nothing more. The Scheduler **serializes** the
Loop Runs it starts — at most one in flight at a time, consistent with the
Phase-3 single-in-process-Loop-Run constraint. Same-tick triggers fire in
registration order.

## Trigger State & Scheduler Events

`trigger_state(id)` returns the per-trigger record — `last_fired`, `next_due`,
`fire_count`, `missed_ticks`, `enabled`, and a reference to the most recent
Scheduled Loop Run (never copied Loop State). The Scheduler emits a **distinct**
Scheduler Event stream (`trigger_registered`, `trigger_fired`, `run_skipped` /
`run_caught_up` / `run_coalesced`, `trigger_paused` / `trigger_resumed`,
`condition_error`, `scheduler_stopped`), off by default. `reconstruct_states(events)`
rebuilds Trigger State from the stream alone.

## Reserved extension points

Named but **not** built this phase: a distributed or durable queue, multi-process
or cross-host scheduling, persistent Trigger State across restarts,
cron-expression parsing, and a background OS daemon.

## Boundary

The scheduler composes the loop layer **only** through `loopplane.engineering`
(`run_loop` + the trigger/value types). It never imports or drives
`loopplane.controller`, `.gateway`, `.loop`, the stores, or the `LoopController`
mechanics. See
[`specs/004-loopplane-scheduler-trigger-engine/contracts/events-state-boundary.md`](../specs/004-loopplane-scheduler-trigger-engine/contracts/events-state-boundary.md).
