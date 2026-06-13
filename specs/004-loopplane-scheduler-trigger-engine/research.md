# Phase 0 Research: Scheduler & Trigger Engine

**Feature**: `004-loopplane-scheduler-trigger-engine` | **Date**: 2026-06-13 |
**Spec**: [spec.md](./spec.md)

No `[NEEDS CLARIFICATION]` markers remain (see [checklists/requirements.md](./checklists/requirements.md)).
Phase 0 records the design decisions that turn the spec into an implementable local scheduler and the
patterns inherited from Phases 1–3. Each decision cites the requirements it satisfies.

## Inherited context (no re-derivation — NFR-001)

The scheduler builds strictly on the merged Phase-3 loop layer. The **only** Phase-3 surface it consumes:

| Phase-3 public surface (`loopplane.engineering`) | How the scheduler uses it |
|---|---|
| `run_loop(definition, *, on_loop_event=, on_approval=, review_resolver=) -> LoopOutcome` | The single call that starts one Scheduled Loop Run for a registered trigger (FR-002, FR-090). |
| `LoopDefinition` | The registered definition a trigger fires (FR-001). |
| `LoopOutcome` (`terminal_event`, `stop_reason`, `state`, `paused`) | The opaque result recorded against Trigger State by reference (FR-003, FR-051). |
| `ManualTrigger` / `IntervalTrigger` / `ConditionTrigger` | The Phase-3 trigger *contracts* the scheduler makes executable (FR-020–FR-040). |

**Non-duplication (FR-090)**: the scheduler never re-implements validation, retry, repair, evaluation, or
the loop lifecycle, and never reaches into Phase-1/2/3 internals. It only decides *when* to call
`run_loop`.

## Decision 1 — Run invocation goes exclusively through `run_loop`

- **Decision**: The Scheduler starts every Scheduled Loop Run with `await run_loop(definition, ...)`. The
  definition and its trigger come from the registry; the scheduler adds only the *when*.
- **Rationale**: Satisfies FR-002, FR-090, NFR-003, SC-002 — exactly one auditable path to start a Loop
  Run. The loop layer already enforces host-only run invocation, so the scheduler inherits the full
  boundary chain (scheduler → run_loop → host → runtime).
- **Alternatives rejected**: *Call `LoopController` or `host.run` directly* — violates FR-090; the
  scheduler sits above the loop layer, not beside it.

## Decision 2 — An injectable monotonic Clock; a virtual clock for tests

- **Decision**: A `Clock` Protocol exposes `now() -> float` (monotonic seconds). `VirtualClock` is
  manually advanced (`advance(dt)` / `set(t)`); `RealClock` wraps `time.monotonic`. The Scheduler reads
  time only from the injected Clock. Tests use `VirtualClock`; **no test sleeps on the wall clock**.
- **Rationale**: FR-010–FR-012, NFR-002, SC-008. Determinism requires that advancing the virtual clock is
  sufficient to drive every trigger, with no real-time dependency.
- **Alternatives rejected**: *Use `asyncio.sleep`/wall clock in the scheduler core* — non-deterministic
  and untestable without real time; rejected. A real sleeping driver is a thin host concern, not core.

## Decision 3 — A poll-driven scheduler, not a background loop

- **Decision**: The Scheduler is driven by explicit `await scheduler.poll()` calls (and `start(id)` for
  manual). `poll()` reads the Clock, finds every due/satisfied trigger, and fires it via `run_loop`.
  A host owns the cadence of `poll()` (e.g. its own `asyncio` loop in production); the core ships no
  background daemon (FR-023 of Phase 3 carried forward; FR-091).
- **Rationale**: Keeps the core deterministic and daemon-free (FR-012, FR-091, FR-092). In tests, the
  sequence "advance virtual clock → `await poll()`" reproduces any schedule exactly.
- **Alternatives rejected**: *An internal `asyncio` task that sleeps and fires* — reintroduces a daemon
  and wall-clock dependency the spec forbids this phase.

## Decision 4 — Serialized single-in-flight Loop Runs

- **Decision**: `poll()` fires due triggers **sequentially**, awaiting each `run_loop` before starting the
  next. This guarantees at most one Scheduled Loop Run in flight (FR-072), matching the Phase-3
  single-in-process-Loop-Run posture. A re-entrancy guard rejects overlapping `poll()`/`start()` calls.
- **Rationale**: FR-072, SC-007. Sequential awaits make serialization automatic and deterministic; no
  locking primitives or concurrency are introduced.
- **Alternatives rejected**: *Fire due triggers concurrently* — out of scope this phase (multiple
  concurrent Scheduled Loop Runs are deferred); would also break determinism of the firing order.

## Decision 5 — Interval due-tick calculation from the Clock

- **Decision**: An interval trigger stores `period` and `next_due`. On `poll()`, while `clock.now() >=
  next_due`, the trigger is due. The number of due ticks in one advance is `floor((now - next_due)/period)
  + 1`; the **missed-run policy** (Decision 6) decides how many Loop Runs that becomes. `start_immediately`
  sets the first `next_due` to the start time (fire at t0); otherwise to `start + period`.
- **Rationale**: FR-030–FR-033, SC-003. Pure arithmetic over the Clock keeps firing exact and
  deterministic; a non-positive period is rejected at registration (FR-033).
- **Alternatives rejected**: *Track wall-clock timestamps* — non-deterministic; rejected for the
  monotonic Clock.

## Decision 6 — Missed-run policy bounds catch-up firing

- **Decision**: A per-trigger `MissedRunPolicy` ∈ {`skip`, `catch_up_once`, `coalesce`} governs a clock
  jump past K ticks: **skip** runs the next due once and advances `next_due` past the jump; **catch_up_once**
  runs a single make-up Loop Run and records the missed count; **coalesce** collapses the missed ticks
  into one run and re-bases `next_due` to the current time. All three start **at most one** Loop Run per
  advance (FR-062), so catch-up can never run unbounded.
- **Rationale**: FR-060–FR-062, SC-005. The bound (≤1 run per advance) is the safety property; the three
  modes differ only in how `next_due` and the missed-tick counter are updated.
- **Alternatives rejected**: *Run one Loop Run per missed tick (full catch-up)* — risks unbounded firing
  on a large jump; explicitly excluded by FR-062 this phase (could be a future `catch_up_all` mode).

## Decision 7 — Condition trigger: host predicate, edge or level mode

- **Decision**: A condition trigger holds a host-supplied `predicate: Callable[[], bool] | Awaitable`
  and a `ConditionMode` ∈ {`edge`, `level`}. On `poll()`, the driver evaluates the predicate; in `edge`
  mode it fires only on a false→true transition (tracking the prior value in Trigger State); in `level`
  mode it fires on every satisfied poll. A predicate that raises becomes a diagnostic (a Scheduler Event)
  and the scheduler continues — no spurious run (FR-042).
- **Rationale**: FR-040–FR-043, SC-004. Predicate logic stays on the host; the driver only decides timing.
  Edge/level is an explicit configuration so "always-true" behavior is never accidental.
- **Alternatives rejected**: *An in-runtime event watcher / background condition daemon* — forbidden this
  phase (FR-043, FR-091); the host polls.

## Decision 8 — Trigger State is in-process and reconstructable from Scheduler Events

- **Decision**: `TriggerState` carries `trigger_id`, `last_fired`, `next_due`, `fire_count`,
  `missed_ticks`, `enabled`, `last_condition_value`, and `last_run_ref` (a reference to the most recent
  Scheduled Loop Run — never the LoopState itself). A pure `reconstruct_states(events)` rebuilds the
  per-trigger states from the ordered Scheduler Event stream.
- **Rationale**: FR-050–FR-052, SC-006. Mirrors the Phase-3 Loop State reconstruction discipline;
  reference-only storage keeps the scheduler from owning loop/run history (FR-051). Durable persistence is
  reserved (FR-091).
- **Alternatives rejected**: *Persist Trigger State to disk this phase* — out of scope (FR-091, FR-092).

## Decision 9 — A distinct Scheduler Event stream, off by default

- **Decision**: Scheduler Events (`trigger_registered`, `trigger_fired`, `run_skipped`,
  `run_caught_up`, `run_coalesced`, `trigger_paused`, `trigger_resumed`, `scheduler_stopped`,
  `condition_error`) form a stream distinct from Loop Events and Runtime Events. Events are always
  *computed* for control/reconstruction; emission to an external sink is gated by an observation flag
  that defaults off (NFR-005, SC-009).
- **Rationale**: FR-080–FR-081. Parity with the Phase-1/3 observability discipline; reconstruction
  (Decision 8) relies on the always-computed stream.
- **Alternatives rejected**: *Reuse the Loop Event stream* — blurs the scheduler/loop boundary
  (distinction 4); rejected per FR-080.

## Decision 10 — Lifecycle as explicit state, drain is trivial under serialization

- **Decision**: The Scheduler holds a `running` flag and per-trigger `enabled` flags. `stop()` sets
  `running=False` (no further fires; `next_due` unchanged); `pause(id)`/`resume(id)` flip a trigger's
  enabled flag; `drain()` — because runs are awaited sequentially, there is never more than one in flight,
  so drain simply finishes the current `poll()` and stops, starting no new runs.
- **Rationale**: FR-070–FR-071, SC-007. Sequential execution makes drain a no-op beyond "stop starting
  new runs," with no background task to join.
- **Alternatives rejected**: *A separate worker thread/task to join on drain* — unnecessary without
  concurrency; rejected.

## Best-practice patterns reused from Phases 1–3

- **Frozen dataclasses + `Protocol` seams** for configs/results; the single mutable record is
  `TriggerState` (scheduler-owned), mirroring `LoopState`.
- **Scripted/virtual instruments**: `VirtualClock` + scripted loops + scripted predicates are the
  deterministic test instruments (NFR-002, SC-008) — no real time, no credentials.
- **Versioned, additively-evolving event vocabulary** with a `SCHEDULER_SCHEMA_VERSION` constant.
- **Import-boundary audit + public-safety scan extension** for the new `loopplane.scheduling` package
  (NFR-003, NFR-004, SC-002, SC-010).
- **One package per boundary**: a single new `loopplane.scheduling` sub-package, additive and reversible.

## Open risks carried into design (not blockers)

| Risk | Handling in Phase 1 design |
|---|---|
| Scheduler reaching past the loop layer | Import-boundary test asserts `loopplane.scheduling` imports only `loopplane.engineering` (run_loop + types), never Phase-1/2/3 internals (NFR-003, SC-002). |
| Unbounded catch-up firing | Missed-run policy caps make-up runs at one per advance (FR-062); a clock-jump test asserts the run count per policy (SC-005). |
| A raising predicate crashing the scheduler | Predicate evaluation is wrapped; an error becomes a `condition_error` Scheduler Event and the scheduler continues (FR-042). |
| Overlapping Loop Runs | Sequential awaits + a re-entrancy guard guarantee single-in-flight (FR-072, SC-007). |
| A secret leaking through a registration | Registrations carry no secrets; predicates/definitions are host objects; public-safety scan over committed files (NFR-004, SC-010). |

**Output**: all design unknowns resolved; ready for Phase 1 (`data-model.md`, `contracts/`,
`quickstart.md`).
