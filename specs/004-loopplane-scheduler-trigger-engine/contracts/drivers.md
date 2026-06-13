# Contract: Clock & Trigger Drivers

**Feature**: `004-loopplane-scheduler-trigger-engine` | FR-010–FR-012, FR-030–FR-043, FR-060–FR-062

The injectable time source plus the executable interval and condition drivers and the missed-run policy.
Signatures are design intent for the implementation phase.

## Clock (FR-010–FR-012)

```python
class Clock(Protocol):
    def now(self) -> float: ...          # monotonic seconds

class VirtualClock:                      # deterministic test instrument
    def __init__(self, start: float = 0.0) -> None: ...
    def now(self) -> float: ...
    def advance(self, seconds: float) -> None: ...
    def set(self, t: float) -> None: ...

class RealClock:                         # production adapter over time.monotonic
    def now(self) -> float: ...
```

- The Scheduler reads time **only** through the injected Clock (FR-010, FR-011). Tests use `VirtualClock`
  and MUST NOT sleep on the wall clock (FR-012, SC-008). A backward `VirtualClock` move is ignored for due
  calculations (edge case).

## Interval driver (FR-030–FR-033, SC-003)

- An interval trigger stores `period` (= `interval_seconds`) and a `next_due` (in Trigger State).
- `start_immediately=True` sets the first `next_due` to the start time (fire at t0); otherwise to
  `start + period` (FR-032).
- On `poll()`, the trigger is **due** while `clock.now() >= next_due`. The count of elapsed ticks in one
  advance is `floor((now - next_due) / period) + 1`; the **missed-run policy** decides how many Loop Runs
  that becomes (FR-031, FR-060). Each fire advances `next_due` by exactly one period (skip/catch_up_once
  advance past the jump; see below) and increments `fire_count` (FR-031).
- A non-positive `period` MUST be rejected at registration (FR-033).

## Missed-run policy (FR-060–FR-062, SC-005)

`MissedRunPolicy = Literal["skip", "catch_up_once", "coalesce"]`. For a clock jump past K due ticks
(K ≥ 1), each policy starts **at most one** Loop Run (FR-062):

| Policy | Loop Runs started | `next_due` after | `missed_ticks` |
|---|---|---|---|
| `skip` | 1 (the next due) | re-based to the first due strictly after `now` | `+= K-1` |
| `catch_up_once` | 1 (one make-up) | re-based to the first due strictly after `now` | `+= K-1` |
| `coalesce` | 1 (collapsed) | `now + period` | `+= K-1` |

- The bound (≤1 run per advance) guarantees catch-up can never fire unbounded (FR-062). The policies
  differ in `next_due` re-basing and which Scheduler Event is emitted (`run_skipped` / `run_caught_up` /
  `run_coalesced`).

## Condition driver (FR-040–FR-043, SC-004)

```python
ConditionMode = Literal["edge", "level"]
```

- On `poll()`, the driver evaluates the host predicate (sync or awaitable). In **`edge`** mode it fires a
  Loop Run only on a false→true transition (the prior value is tracked in `TriggerState.last_condition_value`);
  in **`level`** mode it fires on every satisfied poll (FR-041).
- A predicate that **raises** MUST be caught, surfaced as a `condition_error` Scheduler Event, and the
  Scheduler MUST continue — no spurious Loop Run, no crash (FR-042).
- The predicate is host logic; the driver implements **no** in-runtime watcher or background daemon
  (FR-043, FR-091).
