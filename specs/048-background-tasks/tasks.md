# Tasks: Background Task Tools

**Feature**: 048-background-tasks | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0002](../../docs/adr/0002-background-task-execution.md)

**Scope**: additive, cross-cutting (a new `tools/background.py` + `RunContext`/`RuntimeConfig`
fields + `controller`/`dispatcher`/`host`/`assembly` wiring + export + api-reference + tests).
Default-off (`max_background_tasks = 0`) byte-identical. No event-schema/content-model change.
Reuses the 043 child-run + depth cap.

**Tests**: requested (TDD-friendly).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Add the gate `RuntimeConfig.max_background_tasks: int = 0` (where `RuntimeConfig`
  lives), coerced in `from_mapping` and validated in `validate_config` (a non-negative int;
  `ConfigError` otherwise); carries no secret.
- [ ] T002 Add the additive field `RunContext.background_tasks: BackgroundTaskSupervisor | None = None`
  to `src/loopplane/context.py` (default `None`, per-run; spec-048/ADR-0002 comment). Use a
  `TYPE_CHECKING` import to avoid an import cycle if needed.

## Phase 2: User Story 1 — Non-blocking launch (P1) 🎯 MVP

**Goal**: `task_create` starts a concurrent child run and returns an id immediately.

- [ ] T003 [US1] Create `src/loopplane/tools/background.py`: `BackgroundTaskSupervisor`
  (holds an injected `anyio` task group, a `{task_id -> BackgroundTask(status, result)}`
  registry, the per-run count cap, and a child-run factory reusing the 043 one-shot
  `run_loop` child / depth-incremented child host). Implement `create(instruction,
  allowed_tools=None) -> task_id` via `task_group.start_soon(child_run)` (deny at the count
  cap or the 043 depth cap with a normalized error and no task started); a child run records
  `completed` + result, or `failed` + a fixed public-safe message (contained — never raises).
- [ ] T004 [US1] Add the `task_create` Gateway tool (descriptor + handler) reading
  `context.background_tasks`; write `tests/unit/test_background_tasks.py` asserting create
  returns an id without blocking and the result becomes retrievable (scripted child model).

## Phase 3: User Story 2 — Inspect & control (P2)

- [ ] T005 [US2] Add `task_get`, `task_list`, `task_stop`, `task_output` tools (descriptors +
  handlers + dispatch) over the supervisor registry: get/output return status (+ result when
  `completed`), list enumerates the run's tasks, stop cancels a running task → `stopped`;
  unknown id → a clear normalized error; output before completion → current status (no block).
- [ ] T006 [US2] Extend the tests: status lifecycle (running → completed), list, stop →
  stopped, output, and unknown-id error.

## Phase 4: User Story 3 — Bounded, contained, lifecycle (P3)

- [ ] T007 [US3] Enforce the per-run count cap + the 043 depth cap in `create`; ensure a
  failing child is recorded `failed` (parent unaffected); ensure pending tasks are cancelled
  when the supervisor's task-group scope exits (no leak).
- [ ] T008 [US3] Extend the tests: count-cap denial (no task started), depth-cap denial,
  containment (raising child → `failed`, parent ok), lifecycle (pending cancelled at scope
  exit), and **default-off byte-identity** (`max_background_tasks = 0` → no tools registered).

## Phase 5: Wiring (scope owners thread the supervisor)

- [ ] T009 Wire the supervisor additively (the 043 `subagent_depth` pattern): an optional
  `RuntimeController.drive(..., background_supervisor=None)` stamps it onto the `RunContext`;
  the **Dispatcher** creates a supervisor from its existing session task group and passes it
  to `drive` (only when `max_background_tasks > 0`); the one-shot **`host.run`** wraps its
  single `drive` in a task group and creates a supervisor; `host/assembly.py` registers the
  five background tools + the child-host factory only when `max_background_tasks > 0` (mirror
  the 043 assembly gating).
- [ ] T010 Export the public name(s) (e.g. `BackgroundTaskSupervisor` / the tool adapter) from
  `src/loopplane/tools/__init__.py` and add them to `docs/api-reference.md` (unit-014
  bijection); mirror how 043's `SpawnSubagentAdapter` is exported/documented.

## Phase 6: Polish & Cross-Cutting

- [ ] T011 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof, incl. the default-off byte-identity). Fix any issue.

## Dependencies

- T001, T002 → block all. T003 → T004 (MVP). T004 → T005 → T006. T003/T004 → T007 → T008.
  T002/T003 → T009. T003 → T010. T010 → T011 (gates last).

## Implementation strategy

- **MVP = Phase 1 + 2 (US1)** plus T009 wiring (without wiring, create can't run). US2/US3 add
  control + safety. The implement is large/cross-cutting — a fork subagent MAY do the
  mechanical multi-file work, then gates are verified + committed in the main session.
- All changes additive; default-off (`max_background_tasks = 0`) byte-identical; per ADR 0002.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 2 low (informational). 100%
requirement coverage (FR-001..FR-009 and SC-001..004 each map to ≥1 task); every task traces
to a requirement/design item; spec ↔ plan ↔ **ADR 0002** ↔ data-model ↔ contract ↔ tasks
agree (per-run `BackgroundTaskSupervisor`; five Gateway tools; `RunContext.background_tasks`
threading via `drive`; `RuntimeConfig.max_background_tasks` gate; reuse of the 043 child-run +
depth cap; caps / containment / lifecycle). The one boundary crossing (a new in-run
concurrency pattern) is **maintainer-approved and recorded in ADR 0002**, implemented
additively and default-off — no Constitution violation (III/IV/V/VI/X) and no breaking
001/002 contract change. Low notes are informational: deferred streaming/persistent/
distributed tasks (per spec + ADR 0002); the implement is large/cross-cutting (controller/
dispatcher/host) and may use a fork. **Cleared for `/speckit-implement`.**
