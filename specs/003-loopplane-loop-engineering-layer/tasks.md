---
description: "Task list for Loop Engineering Layer (003)"
---

# Tasks: Loop Engineering Layer

**Input**: Design documents from `/specs/003-loopplane-loop-engineering-layer/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (user stories),
[research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X (Testable Evolution). Every user-story phase writes its
tests first (they must FAIL before implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5, priorities P1–P5 from spec.md) so each story
is an independently testable increment. Phases EA–EF in [plan.md](./plan.md#implementation-phases) map to
the phases below (Foundational = EA, US1 = EB, US2 = EC, US3 = ED, US4 = EE, US5 = EF).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 for user-story phases; Setup/Foundational/Polish carry no story label
- All paths are repository-relative. New package: `src/loopplane/engineering/`.

## Boundary reminder (applies to EVERY implementation task)

The layer starts/observes Agent Runs **only** through the Phase-2 `loopplane.host` surface
(`LoopPlaneHost.run` / `.session`, `RunOutcome`). It MUST NOT import or call any Phase-1 internal
(`loopplane.controller`, `.gateway`, `.loop`, `.events.EventEmitter`, `.memory`, `.checkpoint`,
`.artifacts`, `.approval`, `.observability`) for run orchestration. See
[contracts/host-integration.md](./contracts/host-integration.md). No Phase-1/2 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package and shared deterministic test helpers.

- [X] T001 Create the `loopplane.engineering` package skeleton: `src/loopplane/engineering/__init__.py` with a module docstring and an empty `__all__` placeholder (per [plan.md](./plan.md) structure).
- [X] T002 [P] Add deterministic loop test helpers in `tests/loop_helpers.py`: `build_scripted_host(...)` (a `LoopPlaneHost` over a `ScriptedModel` + echo tool), `scripted_validator(statuses)`, `scripted_evaluator(results)`, and a `LoopEventRecorder` sink — all credential-free and public-safe.

---

## Phase 2: Foundational (Blocking Prerequisites — plan phase EA)

**Purpose**: The declarative contracts, value types, events, and in-process state that ALL user stories
depend on. **No user-story controller work may begin until this phase is green.**

**⚠️ CRITICAL**: Blocks US1–US5.

- [X] T003 [P] Write unit tests in `tests/unit/test_engineering_core.py` (MUST FAIL first): definition validation (empty `loop_id`, unresolvable host profile, missing `max_iterations` bound), the `decide()` status→action mapping table, the hard stop bound, and `reconstruct_state` round-trip from a Loop Event stream.
- [X] T004 [P] Implement `src/loopplane/engineering/events.py`: `LOOP_SCHEMA_VERSION`, `LoopEventType` (the ten event names), frozen `LoopEvent` envelope (FR-072), and `LoopEventSink` type (FR-070–FR-075).
- [X] T005 [P] Implement `src/loopplane/engineering/state.py` types: `RunReference`, `ArtifactRef`, `ApprovalStatus`, and the mutable `LoopState` (reference-only fields per FR-060–FR-061, FR-063).
- [X] T006 [P] Implement `src/loopplane/engineering/validation.py`: `ValidationStatus`, frozen `ValidationResult`, the `Validator` `Protocol`, and a pure `decide(status, retries_used, max_retries, stop_satisfied) -> NextAction` mapping helper (FR-030–FR-032).
- [X] T007 [P] Implement `src/loopplane/engineering/evaluation.py`: frozen `EvaluationResult` and the optional `Evaluator` `Protocol` (FR-040, non-gating types only).
- [X] T008 [P] Implement `src/loopplane/engineering/triggers.py`: `ManualTrigger` (executable marker) plus `IntervalTrigger` and `ConditionTrigger` frozen **contract** dataclasses, and the `Trigger` union (FR-020–FR-023).
- [X] T009 Implement `src/loopplane/engineering/policies.py`: `ValidationPolicy`, `EvaluationPolicy`, `RetryPolicy` (+ `BackoffContract`), `RepairPolicy` (+ `RepairInstructionSource`), `ArtifactPolicy`, `ApprovalPolicy`, `ObservationPolicy` (depends on T006, T007) (FR-004–FR-009, FR-051).
- [X] T010 Implement `src/loopplane/engineering/stopping.py`: `StopCondition` plus reference constructors `stop_on_pass()`, `max_iterations(n)`, `stop_when_score_at_least(threshold, *, max_iterations)`, with the mandatory hard bound (depends on T005, T007) (FR-007, FR-013).
- [X] T011 Implement `src/loopplane/engineering/definition.py`: `InputSource` Protocol, `HostRuntimeProfile` (`config`/`selector` → `build()`), frozen `LoopDefinition`, and `validate_definition(defn)` raising a public-safe `LoopDefinitionError` (depends on T008, T009, T010) (FR-001–FR-009).
- [X] T012 Add `reconstruct_state(events, outcomes) -> LoopState` to `src/loopplane/engineering/state.py` (depends on T004, T005, T006, T007) (FR-062, FR-073, SC-006).
- [X] T013 Populate `src/loopplane/engineering/__init__.py` exports for all foundational types (definition, policies, triggers, validation, evaluation, stopping, events, state).
- [X] T014 Run `pytest tests/unit/test_engineering_core.py` → green (gate for EA).

**Checkpoint**: Contracts + state ready — user-story controller work can begin.

---

## Phase 3: User Story 1 - Define and manually run a single-iteration loop (Priority: P1) 🎯 MVP

**Goal**: A loop engineer defines a loop and triggers it manually; the controller starts exactly one
Agent Run **through the Host Interface**, records reference-only Loop State, and emits the ordered Loop
Event sequence — touching no Phase-1 internal.

**Independent Test**: Define a loop over a scripted host with an always-pass validator and a
single-iteration stop; trigger manually; assert exactly one `host.run`, Loop State references the run's
`session_id` + artifacts, and events `loop_started → loop_iteration_started → loop_iteration_completed →
validation_completed → loop_completed` in order; run twice for identical streams.

- [ ] T015 [P] [US1] Write integration tests in `tests/integration/test_loop_us1.py` (MUST FAIL first): one-Agent-Run-via-`host.run`, Loop State references `session_id`/artifacts, ordered Loop Events, determinism (twice ⇒ identical), and a boundary audit asserting no Phase-1 internal was called (US1 scenarios 1–4; SC-001, SC-002).
- [ ] T016 [US1] Implement `src/loopplane/engineering/controller.py`: `LoopController` + `run_loop(definition, *, on_loop_event=None, on_approval=None)` single-iteration path — build the host from `host_profile`, call `await host.run(prompt, on_event, on_approval=...)`, capture the `RunOutcome` as a `RunReference`, apply the validator, evaluate `stop_on_pass`, and update in-process `LoopState` (depends on Phase 2) (FR-010–FR-015, FR-080–FR-083).
- [ ] T017 [US1] Add `LoopOutcome` and observation gating to `controller.py`: emit `loop_started`/`loop_iteration_started`/`loop_iteration_completed`/`validation_completed`/`loop_completed` only when `observation_policy.emit_loop_events` is on, with identical decisions when off (FR-009, NFR-005, SC-009).
- [ ] T018 [US1] Export `run_loop`, `LoopController`, `LoopOutcome` from `src/loopplane/engineering/__init__.py`.
- [ ] T019 [US1] Run `pytest tests/integration/test_loop_us1.py` → green (incl. boundary audit + determinism).

**Checkpoint**: MVP — a single-iteration loop runs end-to-end through the Host Interface.

---

## Phase 4: User Story 2 - Gate a loop on validation outcomes (Priority: P2)

**Goal**: After each iteration the Validator returns one of `pass`/`fail`/`needs_repair`/
`needs_human_review`; the controller emits `validation_completed` and takes the matching action,
including a fail-safe path for a raised/unknown status.

**Independent Test**: Script each status in turn and assert the emitted event and selected next action;
script a raising validator and assert fail-safe (never silent pass).

- [ ] T020 [P] [US2] Write integration tests in `tests/integration/test_loop_us2.py` (MUST FAIL first): `pass`→`loop_completed`; `needs_repair`→`validation_completed`+`repair_requested`; `needs_human_review`→`human_review_requested`+pause (no further run); raised/unknown status→fail-safe to review (or `loop_failed`) + diagnostic, never silent pass (US2 scenarios 1–4; SC-003).
- [ ] T021 [US2] Implement the full status→decision wiring in `controller.py` using `decide()`: `pass`→stop-success (if stop satisfied), `fail`→stop-failure (retry depth added in US3), `needs_repair`→`repair_requested`, `needs_human_review`→`human_review_requested`; emit `validation_completed` each iteration. Also map a **non-natural** `RunOutcome.termination_reason` (turn budget exhausted, cancelled, unrecoverable error) to a failed iteration subject to the retry policy — never a loop crash (depends on T016) (FR-032, FR-016).
- [ ] T022 [US2] Implement fail-safe handling in `controller.py`: a Validator that raises or returns an unrecognized status routes to human review (or `loop_failed` when `approval_policy.human_review_available` is false) and emits a diagnostic-bearing Loop Event — never a silent `pass` (depends on T021) (FR-034, SC-003).
- [ ] T023 [US2] Implement human-review pause in `controller.py`: set `LoopState.approval_status = pending`, emit `human_review_requested`, start no further Agent Run, and leave the loop cleanly terminal-pending (depends on T021) (FR-009, US5 scenarios 3–4 baseline).
- [ ] T024 [US2] Run `pytest tests/integration/test_loop_us2.py` → green (SC-003).

**Checkpoint**: All four validation statuses map to observable decisions; fail-safe holds.

---

## Phase 5: User Story 3 - Retry transient failures and repair bad output (Priority: P3)

**Goal**: On `fail`, retry the same input up to the retry count then stop-failure; on `needs_repair`,
build a changed input injecting the repair instruction and prior-run context — keeping retry and repair
distinct and the definition unmutated.

**Independent Test**: Script always-`fail` with `max_retries=2` and assert ≤3 runs + `retry_scheduled`×2
+ `loop_failed`; script `needs_repair` then `pass` and assert the 2nd run's submitted input contains the
repair instruction + prior context while the `LoopDefinition` is unchanged.

- [ ] T025 [P] [US3] Write integration tests in `tests/integration/test_loop_us3.py` (MUST FAIL first): retry exhaustion (`max_retries=2`, always `fail` ⇒ ≤3 `host.run` calls, `retry_scheduled`×2 carrying the backoff delay, `loop_failed`; `max_retries=0` ⇒ no `retry_scheduled`); a **non-natural** termination (e.g. cancelled / turn-budget) maps to a failed iteration subject to retry, not a loop crash (FR-016); repair content (`needs_repair`→`pass` ⇒ 2nd input has instruction + prior context, definition unchanged, `loop_completed`); artifact reuse by reference; checkpoint default reset (US3 scenarios 1–4; SC-004, SC-005).
- [ ] T026 [US3] Implement the retry path in `controller.py`: on `fail`, re-submit the **same** input while `retries_used < max_retries`, emit `retry_scheduled` with `backoff.delay_seconds(attempt)` and **no in-process sleeping**; exhaustion → `loop_failed` (depends on T021) (FR-050, FR-051, FR-055).
- [ ] T027 [US3] Implement the repair path in `controller.py`: `build_repair_input(original_input, prior_run_ref, validation_reason, validation_metadata, reused_artifacts)` injecting the repair instruction + previous-run context; emit `repair_requested`; the `LoopDefinition` is never mutated (depends on T021) (FR-052, SC-005).
- [ ] T028 [US3] Implement artifact reuse-by-reference and the explicit checkpoint reuse-or-reset decision in `controller.py`: reuse prior artifacts only via `host.retrieve_artifact(session_id, ref)` governed by `artifact_policy.reuse`; default to reset/fresh run (depends on T027) (FR-053, FR-054).
- [ ] T029 [US3] Run `pytest tests/integration/test_loop_us3.py` → green (SC-004, SC-005).

**Checkpoint**: Retry and repair work and stay distinct.

---

## Phase 6: User Story 4 - Score or label iterations with an optional evaluator (Priority: P4)

**Goal**: When an evaluation policy is present, run the Evaluator after validation, emit
`evaluation_completed`, record the result, and let a stop condition read the score — without evaluation
ever gating control flow. Absent policy ⇒ no evaluation step.

**Independent Test**: Script evaluator scores and assert recording + `evaluation_completed`; a
score-threshold stop halts at the right iteration; removing the policy leaves the loop functional; an
evaluator error is non-fatal.

- [ ] T030 [P] [US4] Write integration tests in `tests/integration/test_loop_us4.py` (MUST FAIL first): score ≥ threshold ⇒ `evaluation_completed`+`loop_completed`; low score + `pass` ⇒ control follows validator/stop (non-gating); no evaluation policy ⇒ no evaluation step or event; evaluator raises ⇒ non-fatal diagnostic, iteration proceeds on validation (US4 scenarios 1–4; FR-040–FR-043).
- [ ] T031 [US4] Implement optional evaluator invocation in `controller.py`: after validation, when an `EvaluationPolicy` exists, call the evaluator, emit `evaluation_completed`, and record `LoopState.latest_evaluation`; when absent, run no evaluation step and emit no event (depends on T021) (FR-041, FR-042).
- [ ] T032 [US4] Implement evaluator error handling in `controller.py`: an evaluator that raises becomes a non-fatal diagnostic; the iteration proceeds on the validation result and the Loop Run continues (depends on T031) (FR-043).
- [ ] T033 [US4] Wire `stop_when_score_at_least` to read `LoopState.latest_evaluation.score` so evaluation can drive **stopping** but never retry/repair (depends on T031, T010) (FR-007, FR-041).
- [ ] T034 [US4] Run `pytest tests/integration/test_loop_us4.py` → green (FR-040–FR-043).

**Checkpoint**: Optional, non-gating evaluation and quality-driven stopping work.

---

## Phase 7: User Story 5 - Bound triggers and route human review through extension points (Priority: P5)

**Goal**: The manual trigger starts Loop Runs; a host-supplied driver enacts the interval/condition
trigger **contracts** through the same manual entry point; `needs_human_review` pauses the loop and an
external decision resumes or terminates it — with no scheduler and no stranded runs.

**Independent Test**: Manual trigger starts exactly one Loop Run; a test driver enacts an interval tick /
satisfied condition via the manual entry point; a `needs_human_review` pause resumes/terminates on a
supplied decision and never hangs.

- [ ] T035 [P] [US5] Write integration tests in `tests/integration/test_loop_us5.py` (MUST FAIL first): manual trigger ⇒ exactly one Loop Run, no daemon; a host-supplied interval/condition driver starts a Loop Run through the manual entry point; `needs_human_review` pauses, a supplied decision resumes or terminates, and a never-answered pause stays cleanly terminal-pending without stranding a run; a never-satisfiable stop predicate still terminates at the `max_iterations` bound with `loop_failed` (no unbounded loop) (US5 scenarios 1–4 + Edge Cases; SC-007, SC-008).
- [ ] T036 [US5] Implement the interval/condition driver path: document and support a host driver that turns a tick or satisfied predicate into a `run_loop(...)` call, asserting no scheduler/queue/daemon is introduced (depends on T021) (FR-021–FR-023, SC-008).
- [ ] T037 [US5] Implement human-review resume in `controller.py`: expose an explicit resume entry point (e.g. `resume_loop(paused_state, decision) -> LoopOutcome`, where a paused `run_loop` returns a terminal-pending `LoopOutcome` carrying the paused `LoopState`) so a supplied decision resumes a paused loop (continue to the next iteration or terminate) without stranding the prior Agent Run; in-run tool approval still flows through the host's `on_approval` (depends on T023) (FR-082, US5 scenarios 3–4).
- [ ] T038 [P] [US5] Create `examples/loop_quickstart.py`: a runnable single-iteration loop over a scripted host that prints the ordered Loop Events and the outcome (public-safe, credential-free).
- [ ] T039 [P] [US5] Write `docs/loop-engineering.md`: a public-safe guide (Loop Definition → `run_loop` → Loop Events → retry/repair/human-review) that points to the Phase-2 boundary rather than restating runtime internals.
- [ ] T040 [US5] Run `pytest tests/integration/test_loop_us5.py` → green (SC-007, SC-008).

**Checkpoint**: Trigger contracts and the human-review boundary close the phase scope.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Boundary/public-safety enforcement and final validation across all stories.

- [ ] T041 [P] Write `tests/contract/test_engineering_boundary.py`: an import-boundary audit asserting `loopplane.engineering` imports only the allowed `loopplane.host` surface (+ permitted value types) and no Phase-1 internal; a host-only run-path assertion (SC-002); a `reconstruct_state` event-sufficiency check (SC-006); an observation-parity check (observed vs unobserved decisions/outcome identical, SC-009); and an unknown-future-Loop-Event tolerance check (a consumer skips an unrecognized event type without error, FR-075) (NFR-003).
- [ ] T042 Extend `tests/contract/test_public_safety.py` to include all committed Phase-3 files (`src/loopplane/engineering/`, `examples/loop_quickstart.py`, `docs/loop-engineering.md`, `specs/003-*`) so the scan finds zero private references (SC-010, NFR-004).
- [ ] T043 [P] Execute the [quickstart.md](./quickstart.md) scenarios end-to-end as a smoke check and reconcile any drift between the guide and the implementation.
- [ ] T044 Final validation: full `pytest` green, `git diff --check` clean, public-safety scan clean (board §10).
- [ ] T045 Update `docs/loopplane-agent-board.md`: advance unit 003 status (Implemented → Verified) and its Next Action per board §13 maintenance rules.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2 / EA)**: depends on Setup — **blocks all user stories**.
- **User Stories (Phases 3–7)**: each depends on Foundational. They share `controller.py`, so in
  practice they proceed in priority order (US1 → US2 → US3 → US4 → US5): US2–US5 each extend the
  controller US1 establishes. Tests per story are independent and [P].
- **Polish (Phase 8)**: depends on the user stories it audits being complete.

### User-story dependencies

- **US1 (P1)**: after Foundational — establishes `controller.py` + `run_loop` (MVP).
- **US2 (P2)**: after US1 — adds the status→decision spine + fail-safe + pause.
- **US3 (P3)**: after US2 — adds retry + repair on top of the decision spine.
- **US4 (P4)**: after US2 — adds optional evaluation (independent of US3).
- **US5 (P5)**: after US2/US3 — trigger driver path + human-review resume + example/docs.

### Parallel opportunities

- Setup T002 ∥ T001.
- Foundational type modules T004–T008 are all [P] (different files); T009–T012 follow their deps.
- Each story's test task (T015, T020, T025, T030, T035) is [P] and written first (must fail).
- US5 docs/example (T038, T039) are [P] with each other and with controller work.
- Polish T041 ∥ T043.

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (EA, **blocks all**) → 3. Phase 3 US1 → **STOP & VALIDATE**:
a single-iteration loop runs end-to-end through the Host Interface with ordered Loop Events and
reference-only Loop State (SC-001/002).

### Incremental delivery

Foundational → US1 (MVP) → US2 (gating) → US3 (retry/repair) → US4 (evaluation) → US5 (triggers/review)
→ Polish. Each story is an independently testable increment that never breaks a prior one; commit after
each green checkpoint and push (board §10–11).

---

## Notes

- [P] = different files, no incomplete-task dependency. The shared `controller.py` is the main
  serialization point across US1–US5.
- Tests are written first per story and must FAIL before implementation (Constitution X).
- Every implementation task obeys the host-only boundary (see the Boundary reminder above).
- Commit after each task or logical group; run board §10 validation before each commit; push after each
  safe commit.
