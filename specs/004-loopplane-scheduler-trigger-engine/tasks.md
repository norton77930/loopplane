---
description: "Task list for Scheduler & Trigger Engine (004)"
---

# Tasks: Scheduler & Trigger Engine

**Input**: Design documents from `/specs/004-loopplane-scheduler-trigger-engine/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each user-story phase writes its tests first (they must
FAIL before implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5, priorities P1–P5). Phases SA–SF in
[plan.md](./plan.md#implementation-phases) map to the phases below (Foundational = SA, US1 = SB,
US2 = SC, US3 = SD, US4 = SE, US5 = SF).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/scheduling/`.

## Boundary reminder (every implementation task)

The Scheduler starts Scheduled Loop Runs **only** through the Phase-3 `run_loop`. It MUST NOT import or
call any Phase-1/2 internal or the Phase-3 `LoopController` mechanics directly — only
`loopplane.engineering` public symbols (`run_loop`, `LoopDefinition`, `LoopOutcome`, the trigger types).
See [contracts/events-state-boundary.md](./contracts/events-state-boundary.md). No Phase-1/2/3 source is
modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `loopplane.scheduling` package skeleton: `src/loopplane/scheduling/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [X] T002 [P] Add deterministic scheduling test helpers in `tests/scheduling_helpers.py`: a `SchedulerEventRecorder` sink, a `scripted_predicate(*values)` (returns booleans per poll), and a thin `pass_loop_definition(...)` builder that reuses the Phase-3 scripted host/validator helpers from `tests/loop_helpers.py`.

---

## Phase 2: Foundational (Blocking Prerequisites — plan phase SA)

**Purpose**: The Clock, policies, events, state, and registry that ALL user stories depend on.

**⚠️ CRITICAL**: Blocks US1–US5.

- [X] T003 [P] Write unit tests in `tests/unit/test_scheduling_core.py` (MUST FAIL first): `VirtualClock` advance/set; a backward clock move is ignored for due calculations (no negative or double fire — spec Edge Case); registration validation (duplicate/empty id, non-positive interval, condition without predicate); interval due math; missed-run math (skip/catch_up_once/coalesce run counts + next_due); `reconstruct_states` round-trip.
- [X] T004 [P] Implement `src/loopplane/scheduling/clock.py`: `Clock` Protocol, `VirtualClock`, `RealClock` (FR-010–FR-012).
- [X] T005 [P] Implement `src/loopplane/scheduling/policy.py`: `MissedRunPolicy`, `ConditionMode`, and `SchedulerError` (FR-060, FR-041, FR-004).
- [X] T006 [P] Implement `src/loopplane/scheduling/events.py`: `SCHEDULER_SCHEMA_VERSION`, `SchedulerEventType` (the nine types), frozen `SchedulerEvent`, and `SchedulerEventSink` (FR-080–FR-081).
- [X] T007 Implement `src/loopplane/scheduling/state.py`: `LoopRunRef`, the mutable `TriggerState` (reference-only fields), and `reconstruct_states(events)` (depends on T006) (FR-050–FR-052, SC-006).
- [X] T008 Implement `src/loopplane/scheduling/registry.py`: `TriggerRegistration` (frozen) + `validate_registration` raising `SchedulerError` (depends on T005) (FR-001, FR-004, FR-033).
- [X] T009 Populate `src/loopplane/scheduling/__init__.py` exports for the foundational types.
- [X] T010 Run `pytest tests/unit/test_scheduling_core.py` → green (gate for SA).

**Checkpoint**: Foundations ready — scheduler work can begin.

---

## Phase 3: User Story 1 - Manual trigger registry (Priority: P1) 🎯 MVP

**Goal**: Register a Loop Definition under a trigger id and start it on demand; the Scheduler starts
exactly one Scheduled Loop Run through `run_loop`, records it in Trigger State, and returns the outcome.

**Independent Test**: Register a manual trigger over a scripted loop, start it by id, and assert exactly
one `run_loop` was invoked, Trigger State records one fire with the clock's time, and the outcome is the
loop's terminal outcome.

- [X] T011 [P] [US1] Write integration tests in `tests/integration/test_scheduler_us1.py` (MUST FAIL first): `register_manual` + `start(id)` ⇒ one Scheduled Loop Run via `run_loop`; Trigger State records fire count + last-fired from the Clock; unknown/duplicate id ⇒ `SchedulerError` with no run started; a registered loop whose `run_loop` pauses for human review records the paused outcome in Trigger State (`last_run_ref.paused`) and still counts as exactly one fire (catch-up is tick-based, not outcome-based — spec Edge Case); a boundary audit that the run started only through `run_loop` (US1 scenarios 1–4; SC-001, SC-002).
- [X] T012 [US1] Implement `src/loopplane/scheduling/scheduler.py`: `Scheduler(clock, *, on_event=None)`, `register_manual`, `unregister`, `start(id)` (fires `await run_loop(definition, ...)`), `trigger_state`, the Scheduler Event emit helper, and the re-entrancy guard (depends on Phase 2) (FR-001–FR-004, FR-020–FR-021, FR-072).
- [X] T013 [US1] Export `Scheduler` (and clock/policy/event/state symbols) from `src/loopplane/scheduling/__init__.py`.
- [X] T014 [US1] Run `pytest tests/integration/test_scheduler_us1.py` → green (boundary audit + state).

**Checkpoint**: MVP — a registered loop starts on demand through `run_loop`.

---

## Phase 4: User Story 2 - Interval trigger on a virtual clock (Priority: P2)

**Goal**: An interval trigger fires once per elapsed period as the virtual clock advances, computing each
next-due from the Clock — deterministically, with no real sleeping.

**Independent Test**: Register an interval trigger, advance a virtual clock by 3P, and assert the loop
fired exactly three times at the due ticks, next-due advanced by the period each fire, and two identical
clock scripts produce identical firing sequences.

- [ ] T015 [P] [US2] Write integration tests in `tests/integration/test_scheduler_us2.py` (MUST FAIL first): period P + advance 3P ⇒ 3 fires through `run_loop` at the due ticks; each fire advances next-due by one period and increments fire_count; two schedulers on identical virtual-clock scripts ⇒ identical firing sequences (determinism); `start_immediately` fires at t0 then every period (US2 scenarios 1–4; SC-003, SC-008).
- [ ] T016 [US2] Implement in `scheduler.py`: `register_interval` and `poll()` interval handling — compute due ticks from `clock.now()` vs `next_due`, fire via `run_loop`, advance `next_due` per period, and update Trigger State (depends on T012) (FR-030–FR-033).
- [ ] T017 [US2] Run `pytest tests/integration/test_scheduler_us2.py` → green (SC-003, SC-008).

**Checkpoint**: The interval contract is now executable and deterministic.

---

## Phase 5: User Story 3 - Condition trigger from a host predicate (Priority: P3)

**Goal**: A condition trigger evaluates a host predicate on each poll and fires a Loop Run when satisfied,
in edge or level mode; a raising predicate is a non-fatal diagnostic.

**Independent Test**: Register a condition trigger whose scripted predicate flips false→true at a known
tick; poll across ticks and assert the loop fires only on the satisfied ticks per the mode, and a raising
predicate yields a diagnostic with no spurious run.

- [ ] T018 [P] [US3] Write integration tests in `tests/integration/test_scheduler_us3.py` (MUST FAIL first): false predicate ⇒ no run; rising edge ⇒ exactly one run; edge mode fires once across a true plateau while level mode fires each poll; a raising predicate ⇒ `condition_error` Scheduler Event, no run, scheduler continues (US3 scenarios 1–4; SC-004).
- [ ] T019 [US3] Implement in `scheduler.py`: `register_condition` and `poll()` condition handling — evaluate the (sync/awaitable) predicate guarded, fire via `run_loop` on edge (false→true) or level (every satisfied poll), and emit `condition_error` on a raising predicate (depends on T012) (FR-040–FR-043).
- [ ] T020 [US3] Run `pytest tests/integration/test_scheduler_us3.py` → green (SC-004).

**Checkpoint**: The condition contract is now executable, with edge/level modes and fail-safe predicates.

---

## Phase 6: User Story 4 - Missed-run policy and Trigger State (Priority: P4)

**Goal**: A clock jump past several due ticks starts the number of Loop Runs dictated by the missed-run
policy (skip / catch-up-once / coalesce, each ≤1 per advance), and Trigger State reconstructs from the
Scheduler Event stream.

**Independent Test**: Advance a virtual clock past several due ticks in one jump and assert the run count
matches the policy and Trigger State counters reflect it; reconstruct Trigger State from events alone.

- [ ] T021 [P] [US4] Write integration tests in `tests/integration/test_scheduler_us4.py` (MUST FAIL first): a clock jump past K ticks ⇒ skip → 1 run (next-due past the jump), catch-up-once → 1 make-up run, coalesce → 1 collapsed run; `missed_ticks` records K-1 in each; Trigger State reconstructs from the Scheduler Event stream alone (US4 scenarios 1–4; SC-005, SC-006).
- [ ] T022 [US4] Implement the missed-run policy in `scheduler.py`: on a multi-tick advance, apply skip / catch_up_once / coalesce (≤1 run each), update `next_due` and `missed_ticks`, and emit `run_skipped` / `run_caught_up` / `run_coalesced` (depends on T016) (FR-060–FR-062).
- [ ] T023 [US4] Ensure the Scheduler Event stream carries enough for `reconstruct_states` to rebuild fire_count, missed_ticks, next_due, and last-fired; reconcile any gap (depends on T022, T007) (FR-052).
- [ ] T024 [US4] Run `pytest tests/integration/test_scheduler_us4.py` → green (SC-005, SC-006).

**Checkpoint**: Recurring-schedule correctness under clock jumps, with reconstructable state.

---

## Phase 7: User Story 5 - Scheduler lifecycle and honest edges (Priority: P5)

**Goal**: Start/stop the Scheduler, pause/resume a trigger, and drain it; serialize the Loop Runs it
starts (one in flight at a time); fire same-tick triggers in deterministic registration order.

**Independent Test**: Pause a trigger and assert it fires nothing while paused and resumes after resume;
drain mid-schedule and assert the in-flight run completes and no new run starts; assert two due triggers
never run concurrently.

- [ ] T025 [P] [US5] Write integration tests in `tests/integration/test_scheduler_us5.py` (MUST FAIL first): a paused trigger fires nothing across due ticks and resumes after `resume`; two same-tick due triggers fire in registration order and never run concurrently (one-in-flight, asserted via a re-entrancy probe); `drain()` lets the in-flight run finish and starts no new run; a stopped Scheduler fires nothing and leaves next-due unchanged (US5 scenarios 1–4; SC-007).
- [ ] T026 [US5] Implement lifecycle in `scheduler.py`: a `running` flag (`stop`), per-trigger `enabled` (`pause`/`resume`), `drain()` (finish in-flight, start nothing, stop), registration-order same-tick firing, and the single-in-flight serialization guard (depends on T012) (FR-070–FR-073).
- [ ] T027 [P] [US5] Create `examples/scheduler_quickstart.py`: a runnable interval-over-`VirtualClock` example that prints the firing sequence and outcomes (public-safe, no real sleeping).
- [ ] T028 [P] [US5] Write `docs/scheduling.md`: a public-safe guide (register → poll → triggers → missed-run → lifecycle) that points at the Phase-3 `run_loop` boundary.
- [ ] T029 [US5] Run `pytest tests/integration/test_scheduler_us5.py` → green (SC-007).

**Checkpoint**: Lifecycle and serialization edges close the phase scope.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T030 [P] Write `tests/contract/test_scheduling_boundary.py`: an import-boundary audit asserting `loopplane.scheduling` imports only `loopplane.engineering` (+ stdlib) and no Phase-1/2 internal or `LoopController` mechanics; a `run_loop`-only firing assertion (SC-002); an observation-parity check (observed vs unobserved decisions/outcome identical, SC-009); and an unknown-future-Scheduler-Event tolerance check (FR-081) (NFR-003).
- [ ] T031 Extend `tests/contract/test_public_safety.py` to include all committed Phase-4 files (`src/loopplane/scheduling/`, `examples/scheduler_quickstart.py`, `docs/scheduling.md`, `specs/004-*`) so the scan finds zero private references (SC-010, NFR-004).
- [ ] T032 [P] Execute the [quickstart.md](./quickstart.md) scenarios end-to-end as a smoke check and reconcile any drift.
- [ ] T033 Final validation: full `pytest` green, `ruff format --check` + `ruff check` clean, `mypy` clean, `git diff --check` clean (board §10).
- [ ] T034 Update `docs/loopplane-agent-board.md`: advance unit 004 status (→ Verified) and its Next Action; set the active feature to 005.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (SA)** blocks all stories → **US1–US5** (share `scheduler.py`, so
  they proceed in priority order; US2–US5 extend `poll()`/lifecycle on top of US1) → **Polish**.
- US1 (P1) establishes `scheduler.py` + manual `start`. US2 adds the interval `poll()`. US3 adds condition
  handling. US4 adds the missed-run policy. US5 adds lifecycle + serialization.

### Parallel opportunities

- Foundational type modules T004–T006 are [P]; T007–T009 follow deps.
- Each story's test task (T011, T015, T018, T021, T025) is [P] and written first (must fail).
- US5 docs/example (T027, T028) are [P]; Polish T030 ∥ T032.

---

## Implementation Strategy

### MVP first (US1)

Setup → Foundational (SA, blocks all) → US1 → **STOP & VALIDATE**: a registered loop starts on demand
through `run_loop` with reference-only Trigger State (SC-001/002).

### Incremental delivery

Foundational → US1 (MVP) → US2 (interval) → US3 (condition) → US4 (missed-run + state) → US5 (lifecycle)
→ Polish. Each story is an independently testable increment; commit after each green checkpoint and push
(board §10–11).

---

## Notes

- [P] = different files. The shared `scheduler.py` is the serialization point across US1–US5.
- Tests are written first per story and must FAIL before implementation (Constitution X).
- Every implementation task obeys the `run_loop`-only boundary.
- The `VirtualClock` is the deterministic instrument; no test sleeps on the wall clock.
