# Tasks: Pre-Turn Cost Guard

**Feature**: 068-pre-turn-cost-guard | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0014](../../docs/adr/0014-pre-turn-cost-guard.md)

**Scope**: additive, default-off pre-model-call USD estimate. Extends 055's `BudgetChecker` and the
Agent Loop model-call boundary; reuses `budget-exceeded`; no new dependency, event reason, or
`SCHEMA_VERSION` bump. Durable monthly predictive enforcement is out of scope.

**Tests**: required. Write/verify failing focused tests before implementation.

## Phase 1: Setup & shared test fixtures

**Purpose**: Create the focused test surface and shared helpers used by all user stories.

- [ ] T001 Create `tests/unit/test_pre_turn_cost_guard.py` with shared helpers: call-counting
  scripted model, `PricingTable` factory, `BudgetChecker` factory, event reason extraction, and
  request-building helpers.
- [ ] T002 Add failing tests in `tests/unit/test_pre_turn_cost_guard.py` for request-token
  estimation over a `ModelRequest` containing history, tools, and output schema; run the focused
  test and confirm the estimator test fails before implementation.

---

## Phase 2: Foundational plumbing

**Purpose**: Add the default-off configuration and reusable request estimator required before any
story can deny or allow a turn predictively.

- [ ] T003 Implement public `estimate_request_tokens(request: ModelRequest, *, chars_per_token:
  int = 4) -> int` in `src/loopplane/loop/assembly.py` and make `PromptAssembler._estimate_tokens`
  delegate to it so capacity checks and pre-turn cost use the same heuristic.
- [ ] T004 Add `RuntimeConfig.pre_turn_max_output_tokens: int | None = None` to
  `src/loopplane/host/config.py`, support it in `RuntimeConfig.from_mapping`, and validate that a
  configured value is a non-negative integer.
- [ ] T005 Thread `pre_turn_max_output_tokens` through `src/loopplane/host/assembly.py` and
  `src/loopplane/controller/controller.py` into the per-session `BudgetChecker` construction without
  building a checker when pricing/caps/model id are otherwise absent.

**Checkpoint**: Configuration and request-token estimation are available, but no pre-turn refusal is
implemented yet.

---

## Phase 3: User Story 1 - Refuse an over-budget turn before the model call (Priority: P1) MVP

**Goal**: A complete estimate that exceeds a known remaining cap terminates `budget-exceeded` before
the model is called.

**Independent Test**: A run configured with pricing, a cap, and `pre_turn_max_output_tokens` refuses
before the call-counting model sees the request.

### Tests for User Story 1

- [ ] T006 [US1] Add failing tests in `tests/unit/test_pre_turn_cost_guard.py` proving an estimated
  per-message overage terminates `budget-exceeded` before model invocation.
- [ ] T007 [US1] Add failing tests in `tests/unit/test_pre_turn_cost_guard.py` proving an estimated
  per-session overage terminates `budget-exceeded` before model invocation.

### Implementation for User Story 1

- [ ] T008 [US1] Extend `src/loopplane/budget/__init__.py` so `BudgetChecker` accepts
  `pre_turn_max_output_tokens` and exposes a non-mutating pre-turn decision using
  `PricingTable.cost(TokenUsage(input_tokens=estimated, output_tokens=max_output), model_id)`.
- [ ] T009 [US1] In `src/loopplane/loop/loop.py`, after `_assemble(...)` and before
  `_stream_model_turn(...)`, call the pre-turn budget decision and emit
  `run_terminated("budget-exceeded", turns_completed)` on refusal.
- [ ] T010 [US1] Run `uv run pytest -q tests/unit/test_pre_turn_cost_guard.py` and confirm US1 tests
  pass.

**Checkpoint**: MVP complete - predictable per-message/per-session overages refuse before the model
call.

---

## Phase 4: User Story 2 - Missing estimate inputs fail open (Priority: P1)

**Goal**: Incomplete pre-turn estimate inputs never block a run.

**Independent Test**: Each incomplete-input case still calls the model and leaves post-turn budget
accounting available.

### Tests for User Story 2

- [ ] T011 [US2] Add failing tests in `tests/unit/test_pre_turn_cost_guard.py` for missing
  `pre_turn_max_output_tokens`, missing pricing table, missing model id, no active cap, and unpriced
  model; each must allow the model call.

### Implementation for User Story 2

- [ ] T012 [US2] Implement fail-open outcomes in `src/loopplane/budget/__init__.py` for incomplete
  estimate inputs; do not guess price or token counts.
- [ ] T013 [US2] In `src/loopplane/loop/loop.py`, emit only generic public-safe diagnostics for
  skipped configured pre-turn enforcement, if diagnostics are emitted at all.
- [ ] T014 [US2] Run `uv run pytest -q tests/unit/test_pre_turn_cost_guard.py` and confirm US2 tests
  pass.

**Checkpoint**: Configured but incomplete pre-turn guard cannot create a false-positive denial.

---

## Phase 5: User Story 3 - Preserve event and budget contracts (Priority: P2)

**Goal**: Pre-turn refusal uses the existing budget contract and does not weaken post-turn
accounting.

**Independent Test**: A pre-turn refusal emits existing `budget-exceeded`; an allowed turn can still
terminate from the existing post-turn checker when actual usage crosses a cap.

### Tests for User Story 3

- [ ] T015 [US3] Add tests in `tests/unit/test_pre_turn_cost_guard.py` asserting pre-turn refusal
  uses `budget-exceeded`, does not change `SCHEMA_VERSION`, and does not emit `cancelled`.
- [ ] T016 [US3] Add tests in `tests/unit/test_pre_turn_cost_guard.py` proving an under-estimated
  allowed turn still terminates `budget-exceeded` through existing post-turn accounting when actual
  usage crosses the cap.

### Implementation for User Story 3

- [ ] T017 [US3] Audit `src/loopplane/events/envelope.py`, `src/loopplane/checkpoint/rebuild.py`,
  `src/loopplane/webapi/app.py`, and frontend run-terminated handling for assumptions that would
  mis-handle a pre-turn `budget-exceeded`; update only if an exhaustive or cancellation-specific path
  requires it.

**Checkpoint**: Event vocabulary, schema, checkpoint, and post-turn accounting semantics are
preserved.

---

## Phase 6: User Story 4 - Default-off behavior stays byte-identical (Priority: P3)

**Goal**: Without the new pre-turn estimate configuration, existing runtime behavior remains
unchanged.

**Independent Test**: Existing budget-configured runs without `pre_turn_max_output_tokens` behave as
055/063 did.

### Tests for User Story 4

- [ ] T018 [US4] Add tests in `tests/unit/test_pre_turn_cost_guard.py` proving no pre-turn estimate
  or denial occurs when `pre_turn_max_output_tokens` is unset, even if post-turn caps are configured.

### Implementation for User Story 4

- [ ] T019 [US4] Verify `src/loopplane/host/config.py`, `src/loopplane/host/assembly.py`, and
  `src/loopplane/controller/controller.py` keep the guard disabled by default and do not build budget
  collaborators solely for pre-turn checking.

**Checkpoint**: Default runtime path remains byte-identical.

---

## Phase 7: Polish & gates

- [ ] T020 Update `docs/api-reference.md` if it lists `RuntimeConfig` budget fields and must include
  `pre_turn_max_output_tokens`.
- [ ] T021 Run focused validation from `specs/068-pre-turn-cost-guard/quickstart.md`.
- [ ] T022 Run full gates: `uv run ruff check`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest -q`.
- [ ] T023 Run board audits: `git diff --check`, `openspec/` scan, public-safety scan, and
  api-reference/structural audits if touched.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 tests.
- **US1 (Phase 3)**: Depends on Phase 2.
- **US2 (Phase 4)**: Depends on US1's pre-turn decision seam.
- **US3 (Phase 5)**: Depends on US1 and US2.
- **US4 (Phase 6)**: Depends on Phase 2 and can be verified after US1/US2 behavior exists.
- **Polish (Phase 7)**: Depends on all desired stories.

### User Story Dependencies

- **US1**: MVP. Blocks implementation of the other behavior stories because it creates the guard
  decision and loop hook.
- **US2**: Builds on US1 by completing fail-open cases.
- **US3**: Builds on US1/US2 and verifies the existing budget/event contract.
- **US4**: Verifies default-off behavior after the guard is wired.

### Parallel Opportunities

- T003 and T004 are different files and can be reviewed independently after T002 exists.
- T006 and T007 are similar tests in the same file; keep serial to avoid merge conflicts.
- US2/US3/US4 tests are in the same focused test file; keep serial in this workspace.
- Documentation/API reference work in T020 can run after the public config field is finalized.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 only.
3. Validate with `uv run pytest -q tests/unit/test_pre_turn_cost_guard.py`.
4. Confirm the model call count is zero for predicted overage.

### Incremental Delivery

1. Add US1 refusal.
2. Add US2 fail-open cases.
3. Add US3 contract preservation.
4. Add US4 default-off proof.
5. Run all gates and board scans.

## Cross-Artifact Analysis (gate)

Pending `/speckit-analyze`.
