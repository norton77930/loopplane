# Tasks: Platform Fairness

**Input**: Design documents from `specs/072-platform-fairness/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/platform-fairness.md`, `quickstart.md`, ADR 0013.

**Tests**: Required by Constitution Principle X and FR-011. Write the tests
first and verify they fail before implementation.

**Organization**: Tasks are grouped by user story so each story can be
implemented and tested independently.

## Phase 1: Setup (Shared Test Harness)

**Purpose**: Add reusable test scaffolding for deterministic fairness and web/API
quota checks.

- [ ] T001 [P] Add deterministic async scheduler fixtures for tenant work in `tests/unit/test_platform_fairness.py`
- [ ] T002 [P] Add a controllable streaming model fixture for fairness-gated turns in `tests/unit/test_loop_core.py`
- [ ] T003 [P] Add web/API fairness test helpers for quota rejection responses in `tests/unit/test_webapi_core.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Introduce the explicit fairness boundary and wire it through config
without enabling behavior by default.

- [ ] T004 Create `PlatformFairnessPolicy`, `PlatformFairnessRejected`, and `PlatformFairness` API skeleton in `src/loopplane/fairness.py`
- [ ] T005 Add `platform_fairness` to `RuntimeConfig`, `from_mapping()`, and `validate_config()` in `src/loopplane/host/config.py`
- [ ] T006 Export platform fairness types from `src/loopplane/host/__init__.py` and package-level public modules as needed
- [ ] T007 Thread optional platform fairness from `assemble()` to `RuntimeController` in `src/loopplane/host/assembly.py`
- [ ] T008 Add `principal_id` and optional platform fairness fields to `RunContext` and `RuntimeController` wiring in `src/loopplane/context.py` and `src/loopplane/controller/controller.py`
- [ ] T009 Pass optional platform fairness into `AgentLoop` without changing default behavior in `src/loopplane/loop/loop.py`

**Checkpoint**: Runtime config and controller/loop boundaries can name fairness,
but no user story is complete until the tests and behavior below are done.

---

## Phase 3: User Story 1 - Fair Progress Across Active Tenants (Priority: P1)

**Goal**: Within-quota tenants with queued model-call work make fair progress
under constrained shared capacity.

**Independent Test**: Two tenants enqueue model-call work with
`max_active_model_calls=1` and `max_consecutive_starts=1`; both tenants start a
turn before either tenant monopolizes the scheduler.

### Tests for User Story 1

- [ ] T010 [P] [US1] Add failing two-tenant round-robin progress tests in `tests/unit/test_platform_fairness.py`
- [ ] T011 [P] [US1] Add failing single-tenant no-artificial-delay test in `tests/unit/test_platform_fairness.py`
- [ ] T012 [P] [US1] Add failing AgentLoop model-turn permit integration test in `tests/unit/test_loop_core.py`

### Implementation for User Story 1

- [ ] T013 [US1] Implement async fair model-turn queue, shared capacity, and consecutive-start window in `src/loopplane/fairness.py`
- [ ] T014 [US1] Gate `AgentLoop._stream_model_turn()` with `PlatformFairness.model_turn()` in `src/loopplane/loop/loop.py`
- [ ] T015 [US1] Stamp session principal id into `RunContext` during `RuntimeController.drive()` in `src/loopplane/controller/controller.py`
- [ ] T016 [US1] Run focused US1 tests: `uv run pytest tests/unit/test_platform_fairness.py tests/unit/test_loop_core.py`

**Checkpoint**: Fair model-call scheduling works independently of quota
admission and without changing event/schema/tool behavior.

---

## Phase 4: User Story 2 - Bound One Tenant's Outstanding Work (Priority: P1)

**Goal**: A tenant cannot exceed its configured local outstanding-work quota,
and quota is reusable after completion, failure, or cancellation.

**Independent Test**: Configure a small per-tenant quota, admit work for tenant A
until the quota is full, verify additional tenant A work is rejected while
tenant B still admits, then release tenant A reservations and verify tenant A can
admit again.

### Tests for User Story 2

- [ ] T017 [P] [US2] Add failing quota admit/reject/release tests in `tests/unit/test_platform_fairness.py`
- [ ] T018 [P] [US2] Add failing cross-tenant quota isolation test in `tests/unit/test_platform_fairness.py`
- [ ] T019 [P] [US2] Add failing public-safe HTTP 429 quota test for one-shot runs in `tests/unit/test_webapi_core.py`
- [ ] T020 [P] [US2] Add failing host config validation tests for invalid fairness policy values in `tests/contract/test_host_config.py`

### Implementation for User Story 2

- [ ] T021 [US2] Implement tenant outstanding-work admission and exactly-once reservation release in `src/loopplane/fairness.py`
- [ ] T022 [US2] Wrap `LoopPlaneHost.run()` and `Session.submit()` work with fairness admission when a principal id is present in `src/loopplane/host/host.py`
- [ ] T023 [US2] Map `PlatformFairnessRejected` to public-safe HTTP 429 for one-shot run routes in `src/loopplane/webapi/app.py`
- [ ] T024 [US2] Preserve existing 409 active-run conflicts separately from fairness 429 in `src/loopplane/webapi/app.py`
- [ ] T025 [US2] Run focused US2 tests: `uv run pytest tests/unit/test_platform_fairness.py tests/unit/test_webapi_core.py tests/contract/test_host_config.py`

**Checkpoint**: Quota rejection is public-safe, local, and independent per
tenant.

---

## Phase 5: User Story 3 - Preserve Default Behavior And Boundaries (Priority: P1)

**Goal**: Deployments that do not configure platform fairness behave exactly as
they did before 072, and runtime/tool/event contracts remain unchanged.

**Independent Test**: Existing tenant host pool, loop core, and web/API default
tests pass with `platform_fairness=None`; no new event type, content block, or
termination reason is required.

### Tests for User Story 3

- [ ] T026 [P] [US3] Add default-off regression tests for `RuntimeConfig.from_mapping()` and `validate_config()` in `tests/contract/test_host_config.py`
- [ ] T027 [P] [US3] Add default-off tenant host pool regression coverage in `tests/unit/test_tenant_host_pool.py`
- [ ] T028 [P] [US3] Add event/termination vocabulary regression assertions in `tests/unit/test_loop_core.py`

### Implementation for User Story 3

- [ ] T029 [US3] Keep all fairness branches inert when no fairness object or no principal id is present in `src/loopplane/controller/controller.py` and `src/loopplane/loop/loop.py`
- [ ] T030 [US3] Ensure host and web/API default paths do not create fairness state in `src/loopplane/host/host.py` and `src/loopplane/webapi/app.py`
- [ ] T031 [US3] Run focused US3 tests: `uv run pytest tests/contract/test_host_config.py tests/unit/test_tenant_host_pool.py tests/unit/test_loop_core.py`

**Checkpoint**: Default-off behavior and boundary preservation are verified.

---

## Phase 6: User Story 4 - Fail Safely Under Scheduler Pressure (Priority: P2)

**Goal**: Cancellation, scheduler failure, and client disconnect cleanup release
local fairness state and expose only public-safe responses.

**Independent Test**: Queue work, cancel or fail it before/during model-turn
admission, and verify reservations/permits are released exactly once and later
work proceeds.

### Tests for User Story 4

- [ ] T032 [P] [US4] Add failing queued-cancellation cleanup tests in `tests/unit/test_platform_fairness.py`
- [ ] T033 [P] [US4] Add failing model-stream-exception permit-release test in `tests/unit/test_loop_core.py`
- [ ] T034 [P] [US4] Add failing SSE/session public-safe quota error tests in `tests/unit/test_webapi_core.py`

### Implementation for User Story 4

- [ ] T035 [US4] Make queued waiter cancellation remove scheduler entries and notify the next waiter in `src/loopplane/fairness.py`
- [ ] T036 [US4] Make model-turn permit release idempotent across normal completion, exceptions, and cancellation in `src/loopplane/fairness.py`
- [ ] T037 [US4] Map fairness quota errors to generic public-safe SSE/session errors without raw exception details in `src/loopplane/webapi/streaming.py`, `src/loopplane/webapi/app.py`, and `src/loopplane/webapi/sessions.py`
- [ ] T038 [US4] Run focused US4 tests: `uv run pytest tests/unit/test_platform_fairness.py tests/unit/test_loop_core.py tests/unit/test_webapi_core.py`

**Checkpoint**: Failure cleanup and public-safe error behavior are verified.

---

## Phase 7: Polish & Cross-Cutting Validation

**Purpose**: Documentation, contract alignment, and full gates.

- [ ] T039 [P] Update public API reference or quickstart snippets for platform fairness in `docs/api-reference.md` if the public export surface changes
- [ ] T040 [P] Update 072 quickstart validation notes in `specs/072-platform-fairness/quickstart.md` if implementation paths differ from the plan
- [ ] T041 Run `uv run ruff check`
- [ ] T042 Run `uv run ruff format --check src tests`
- [ ] T043 Run `uv run mypy src`
- [ ] T044 Run `uv run pytest`
- [ ] T045 Run `git diff --check`, changed-file scope check, private-reference scan, and public-safety scan
- [ ] T046 Update `docs/loopplane-agent-board.md` to mark 072 Verified after all gates pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on Foundational and may reuse US1 fairness state.
- **US3 (Phase 5)**: Depends on Foundational; should be checked after US1/US2 wiring.
- **US4 (Phase 6)**: Depends on US1 and US2 behavior.
- **Polish (Phase 7)**: Depends on selected user stories being complete; final review depends on all tasks.

### User Story Dependencies

- **US1**: Core fair model-call scheduling. MVP.
- **US2**: Quota admission and release. Can start after Foundational, but final web/host behavior should integrate with US1 state.
- **US3**: Default-off/boundary regression. Validates no unintended behavior changes.
- **US4**: Failure cleanup. Depends on scheduler and quota primitives from US1/US2.

### Parallel Opportunities

- T001-T003 can run in parallel.
- T010-T012 can run in parallel before US1 implementation.
- T017-T020 can run in parallel before US2 implementation.
- T026-T028 can run in parallel before US3 implementation.
- T032-T034 can run in parallel before US4 implementation.
- T039 and T040 can run in parallel after implementation stabilizes.

---

## Parallel Example: User Story 1

```text
Task: "T010 [P] [US1] Add failing two-tenant round-robin progress tests in tests/unit/test_platform_fairness.py"
Task: "T012 [P] [US1] Add failing AgentLoop model-turn permit integration test in tests/unit/test_loop_core.py"
```

## Parallel Example: User Story 2

```text
Task: "T017 [P] [US2] Add failing quota admit/reject/release tests in tests/unit/test_platform_fairness.py"
Task: "T019 [P] [US2] Add failing public-safe HTTP 429 quota test for one-shot runs in tests/unit/test_webapi_core.py"
Task: "T020 [P] [US2] Add failing host config validation tests for invalid fairness policy values in tests/contract/test_host_config.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational.
2. Complete US1 fair model-call scheduling.
3. Validate US1 focused tests.
4. Add US2 quota admission and public-safe rejection.
5. Validate default-off and failure cleanup before full gates.

### Incremental Delivery

1. Shared fairness API and wiring.
2. Fair model-turn scheduling.
3. Tenant quota admission.
4. Default-off/boundary regression.
5. Cancellation/failure cleanup and public-safe web/API mapping.
6. Full validation and board update.

### Validation Gates

Run focused tests at each checkpoint, then final gates:

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest
git diff --check
```
