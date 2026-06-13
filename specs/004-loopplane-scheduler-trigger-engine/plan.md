# Implementation Plan: Scheduler & Trigger Engine

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-loopplane-scheduler-trigger-engine/spec.md`

## Summary

Build the local, in-process **Scheduler & Trigger Engine** that makes the Phase-3 interval and condition
trigger *contracts* executable. A **Scheduler** owns a registry of triggers and an injectable **Clock**;
it decides *when* a trigger fires and starts each **Scheduled Loop Run** **only** by calling the Phase-3
`run_loop` entry point — never bypassing the loop layer or reaching into Phase-1/2/3 internals
(FR-002, FR-090). The deliverable is one new additive sub-package, `loopplane.scheduling`, providing:
a poll-driven Scheduler with a manual/interval/condition registry, an injectable Clock (`VirtualClock`
for deterministic tests, `RealClock` for production), executable interval and condition drivers, a
missed-run policy (skip / catch-up-once / coalesce), in-process Trigger State reconstructable from a
distinct Scheduler Event stream, and a lifecycle (start / stop / pause / resume / drain) with serialized
single-in-flight Loop Runs — plus a public-safe example, a doc, and unit/integration/contract suites.
Design detail lives in [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–3).

**Primary Dependencies**: The Phase-3 `loopplane.engineering` public surface (`run_loop`,
`LoopDefinition`, `LoopOutcome`, and the trigger contracts `ManualTrigger` / `IntervalTrigger` /
`ConditionTrigger`). No new third-party runtime dependency — pure scheduling logic over `anyio` already
present in the core; time comes from an injectable Clock, not the wall clock.

**Storage**: None of its own. Trigger State is in process and reconstructable from the Scheduler Event
stream (FR-052); no database, no durable persistence this phase (FR-091, FR-092).

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. A `VirtualClock` plus the Phase-3 scripted host/validator helpers are the deterministic
instruments — no real sleeping (NFR-002, SC-008).

**Target Platform**: Cross-platform library embedded in a plain host process; the scheduler is poll-driven
and ships no background daemon (FR-091, FR-092).

**Project Type**: Single library — one new sub-package (`loopplane.scheduling`) added to the existing
src-layout package, keeping the one-package-per-component-boundary convention from Phases 1–3.

**Performance Goals**: Negligible overhead; `poll()` is O(registered triggers) arithmetic plus the loop
runs it starts. Determinism preserved (NFR-002).

**Constraints**: `run_loop`-only invocation (FR-002, FR-090, SC-002); injectable Clock, no wall-clock
dependency in tests (FR-010–FR-012); serialized single-in-flight Loop Runs (FR-072, SC-007); bounded
catch-up (FR-062); observation off by default (NFR-005, SC-009); public-safe (NFR-004, SC-010); minimal,
reversible surface (NFR-006).

**Scale/Scope**: Single process; one Scheduled Loop Run in flight at a time. One new package (~7 modules),
one example, one doc, unit/integration/contract suites. **No Phase-1/2/3 source is modified.**

## Dependency on Phases 1–3

This phase is **strictly additive** and consumes only the Phase-3 public surface — it composes `run_loop`
and the trigger/value types and does not modify or re-implement them (NFR-001, FR-090). The exact surface
and the boundary are enumerated in
[contracts/events-state-boundary.md](./contracts/events-state-boundary.md) and
[research.md](./research.md#inherited-context-no-re-derivation--nfr-001).

**Non-duplication guarantee (FR-090, SC-010)**: the scheduler contains *no* validation, retry, repair,
evaluation, or loop-lifecycle logic, and no runtime/host internals. It adds only the *when* — trigger
registry, Clock, due/condition calculation, missed-run policy, Trigger State, and lifecycle — above the
`run_loop` boundary.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.scheduling` depends on `loopplane.engineering`; the
loop, host, and core have **zero** knowledge of the scheduler.

```text
host (owns the poll cadence / lifecycle)
      │  registers triggers; calls start()/poll()/drain()
      ▼
  Scheduler ──reads──► Clock (VirtualClock | RealClock)
      │  for each due/satisfied trigger (registration order, serialized)
      ▼
  run_loop(definition, ...)  ◄── Phase-3 (the ONLY path to start a Loop Run)
      │  returns LoopOutcome
      ▼
  Trigger State (refs only) ◄── records ── Scheduler Event stream (distinct; off by default)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/events-state-boundary.md](./contracts/events-state-boundary.md)):

- The Scheduler starts Loop Runs **only** through `run_loop` (FR-002, FR-090).
- Time comes **only** from the injected Clock (FR-010).
- Trigger State holds **references** (run refs) — never copied Loop State (FR-051).
- The Scheduler Event stream is separate from Loop Events and Runtime Events (FR-080).

## Project Structure

### Documentation (this feature)

```text
specs/004-loopplane-scheduler-trigger-engine/
├── spec.md                 # Feature specification (complete)
├── plan.md                 # This file (/speckit.plan output)
├── research.md             # Phase 0: design decisions
├── data-model.md           # Phase 1: scheduler-layer entities
├── quickstart.md           # Phase 1: validation/run guide
├── contracts/              # Phase 1: interface contracts
│   ├── scheduler.md            # Scheduler API + registry + lifecycle + serialization
│   ├── drivers.md              # Clock + interval/condition drivers + missed-run policy
│   └── events-state-boundary.md # Scheduler Events + Trigger State + the run_loop-only boundary
├── checklists/
│   └── requirements.md     # Spec quality checklist (complete)
└── tasks.md                # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/scheduling/
├── __init__.py        # public exports (Scheduler, Clock, VirtualClock, RealClock, policies, events, state)
├── clock.py           # Clock Protocol + VirtualClock + RealClock (FR-010–FR-012)
├── policy.py          # MissedRunPolicy + ConditionMode + SchedulerError (FR-060, FR-041, FR-004)
├── events.py          # SchedulerEvent vocabulary + SCHEDULER_SCHEMA_VERSION + sink (FR-080–FR-081)
├── state.py           # TriggerState + LoopRunRef + reconstruct_states (FR-050–FR-052)
├── registry.py        # TriggerRegistration + validation (FR-001, FR-004, FR-033)
└── scheduler.py       # Scheduler: registry, poll/start, drivers, missed-run, lifecycle (FR-002, FR-020–FR-073)

examples/
└── scheduler_quickstart.py # runnable interval-over-virtual-clock example (public-safe)

docs/
└── scheduling.md      # public-safe guide: register → poll → triggers → missed-run → lifecycle

tests/
├── unit/
│   └── test_scheduling_core.py    # clock, registration validation, due math, missed-run, state reconstruction
├── integration/
│   ├── test_scheduler_us1.py      # US1: manual registry + start + boundary audit (SC-001/002)
│   ├── test_scheduler_us2.py      # US2: interval driver on a virtual clock + determinism (SC-003/008)
│   ├── test_scheduler_us3.py      # US3: condition driver, edge/level, raising predicate (SC-004)
│   ├── test_scheduler_us4.py      # US4: missed-run policy + Trigger State reconstruction (SC-005/006)
│   └── test_scheduler_us5.py      # US5: pause/resume, serialization, drain, stop (SC-007)
└── contract/
    └── test_scheduling_boundary.py # import-boundary audit + run_loop-only + observation parity + public-safety
```

**Structure Decision**: one new sub-package `loopplane.scheduling`, mirroring the Phase-1/2/3
one-package-per-boundary convention so the scheduler is a single, clearly-bounded, independently
revertible addition. The package name maps to the feature ("**scheduler**-trigger-engine"). It is distinct
from `loopplane.engineering` (the loop layer it drives) and depends inward on it only through `run_loop`.
No Phase-1/2/3 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| SA — Foundations | `clock.py`, `policy.py`, `events.py`, `state.py`, `registry.py` (types + validation + `reconstruct_states` + due math) | `test_scheduling_core.py` green; states reconstruct (SC-006) | Revert package; nothing depends on it yet |
| SB — Manual registry (US1) | `scheduler.py`: registry + `start(id)` via `run_loop`; Trigger State; Scheduler Events | `test_scheduler_us1.py` green incl. boundary audit (SC-001/002) | Revert to foundations |
| SC — Interval driver (US2) | `poll()` + interval due math + `start_immediately`; determinism | `test_scheduler_us2.py` green (SC-003/008) | Revert interval path; US1 intact |
| SD — Condition driver (US3) | predicate evaluation, edge/level, raising-predicate diagnostic | `test_scheduler_us3.py` green (SC-004) | Revert condition path |
| SE — Missed-run + state (US4) | skip / catch-up-once / coalesce; Trigger State reconstruction | `test_scheduler_us4.py` green (SC-005/006) | Revert missed-run policy |
| SF — Lifecycle, example, docs (US5) | pause/resume/stop/drain + serialization; `examples/scheduler_quickstart.py`; `docs/scheduling.md`; extend public-safety scan | `test_scheduler_us5.py` + `test_scheduling_boundary.py` green; example runs; scan clean (SC-007/010) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Scheduler reaches past the loop layer | Import-boundary audit asserts `loopplane.scheduling` imports only `loopplane.engineering` + stdlib (FR-090, NFR-003, SC-002); run_loop-only firing enforced by design |
| Unbounded catch-up firing | Missed-run policy caps make-up runs at one per advance (FR-062); a clock-jump test asserts the count per policy (SC-005) |
| Wall-clock / real-sleep dependency creeps in | All time via the injected Clock; tests use `VirtualClock`; a determinism test runs identical clock scripts (FR-010–FR-012, SC-008) |
| Overlapping Loop Runs | Sequential awaits + a re-entrancy guard guarantee single-in-flight (FR-072, SC-007) |
| A raising predicate crashes the scheduler | Predicate evaluation wrapped → `condition_error` event; scheduler continues (FR-042) |
| Observation changes behavior | Off by default; parity test compares observed vs unobserved decisions/outcome (NFR-005, SC-009) |
| Scope creeps into a queue/daemon/cron | Poll-driven core only; out-of-scope list forbidden by FR-091–FR-092; Constitution III review gate |
| A secret/private path leaks via a registration | Registrations carry no secrets; predicates/definitions are host objects; public-safety scan over committed files (NFR-004, SC-010) |

**Rollback posture**: `loopplane.scheduling` is purely **additive** over Phases 1–3 — small, task-scoped
commits, each phase (SA–SF) independently revertible. Reverting any or all leaves the Phase-1/2/3 layers
and on-disk records untouched (the scheduler owns no runtime/loop state and no storage format).
Observation is default-off, so a partial revert can never change scheduling behavior.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.scheduling` package written fresh; composes the Phase-3 public API only; no legacy code copied (FR-090) |
| III | Agent Harness Before Loop Automation | PASS | This is the local scheduling the Phase-3 spec deferred; it stays minimal, ships **no** distributed queue/daemon, and names every reserved extension point (FR-091, NFR-006) — poll-driven, virtual-clock |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (decide *when* to fire); depends inward on Phase 3 via `run_loop`; boundary table assigns ownership; no lower-layer boundary blurred (FR-090) |
| V | Tool Gateway Ownership | PASS | The scheduler never resolves/authorizes/executes tools; all tool execution stays in Phase-1, reached transitively through `run_loop` → host → gateway (FR-090) |
| VI | Runtime Event Bus Ownership | PASS | Consumes no Runtime Events directly; emits a **distinct** Scheduler Event stream that never wraps/re-emits Loop or Runtime Events; versioned + unknown-type tolerant (FR-080) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; registrations carry no secrets (FR-001, NFR-004); example/docs public-safe; scan extended (SC-010) |
| VIII | No SDK Replacement | PASS | No agent/scheduler framework introduced; pure scheduling logic over LoopPlane's own loop layer |
| IX | Reference, Not Clone | PASS | Scheduling concepts re-derived public-safe from the spec and the Phase-3 surface; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (SA–SF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; observation default-off; determinism via the virtual clock |

**Post-design re-check**: PASS — the entity model, contracts, and event model introduce no boundary
violation and no Phase-1/2/3 modification. The only mutable entity (`TriggerState`) is scheduler-owned and
reference-only. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
