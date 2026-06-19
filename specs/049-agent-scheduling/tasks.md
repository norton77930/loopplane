# Tasks: Agent Scheduling Tools

**Feature**: 049-agent-scheduling | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive, cross-cutting — a new `tools/scheduling.py` (Sleeper seam +
ScheduleSupervisor + 4 tools) + `RunContext`/`RuntimeConfig` fields + controller/dispatcher/
host/assembly wiring + export + api-reference + tests. Default-off (`max_schedules = 0`)
byte-identical. Reuses the unit-048 supervisor (ADR 0002) + the 043/048 child-run + the unit-004
interval concepts. **No new ADR; no unit-004 `Clock` contract change.**

**Tests**: requested (TDD-friendly; deterministic via a fake Sleeper — no real sleeping).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Add the gate `RuntimeConfig.max_schedules: int = 0` to `src/loopplane/host/config.py`
  (coerce in `from_mapping`, validate non-negative int in `validate_config`; no secret),
  mirroring `max_background_tasks`.
- [ ] T002 Add a neutral `ScheduleSupervisor` Protocol + a `ScheduleSupervisorFactory` alias to
  `src/loopplane/context.py` (the 048 `BackgroundSupervisor` pattern), and the additive field
  `RunContext.schedules: ScheduleSupervisor | None = None`. The controller/loop must reference
  this Protocol, never `loopplane.tools`.

## Phase 2: User Story 1 — Schedule deferred / recurring work (P1) 🎯 MVP

- [ ] T003 [US1] Create `src/loopplane/tools/scheduling.py`: a `Sleeper` seam (default
  `anyio.sleep`; a fake for tests), and a `ScheduleSupervisor` holding an injected `anyio` task
  group + a `{schedule_id -> Schedule}` registry + the count cap + the injected `run_child`
  (reuse the 043/048 child run). `create(instruction, *, delay_seconds=None,
  interval_seconds=None, allowed_tools=None, child_depth, working_scope) -> id | None`: validate
  exactly one positive cadence; deny at the count cap / 043 depth cap; else `start_soon` a timer
  task that `await sleeper.sleep(...)` then fires a bounded child run (once for delay →
  `completed`; each period for interval), recording occurrences + a public-safe `last_result`
  (a failing/over-running occurrence is contained — never raises). Add a
  `make_schedule_supervisor_factory(run_child_builder, max_schedules, sleeper)` helper (the 048
  `make_supervisor_factory` pattern) so the host assembly owns the tools import.
- [ ] T004 [US1] Add the `schedule_create` Gateway tool (descriptor + handler) reading
  `context.schedules`; write `tests/unit/test_agent_scheduling.py` asserting non-blocking create
  + deterministic interval firing as a fake Sleeper is advanced (scripted child model).

## Phase 3: User Story 2 — Inspect & cancel (P2)

- [ ] T005 [US2] Add `schedule_get`, `schedule_list`, `schedule_cancel` tools (descriptors +
  handlers + dispatch) over the registry: get/list report cadence + status + occurrences
  (metadata only); cancel stops further firings → `cancelled`; unknown id → a clear normalized
  error.
- [ ] T006 [US2] Extend the tests: get/list metadata, cancel → cancelled (no further firings),
  unknown-id error.

## Phase 4: User Story 3 — Bounded, contained, lifecycle (P3)

- [ ] T007 [US3] Enforce the count cap + the 043 depth cap + cadence validation (non-positive /
  both / neither → deny, nothing scheduled); ensure a failing occurrence is recorded
  (parent/schedule unaffected); ensure active schedules' timers are cancelled when the
  supervisor's task-group scope exits (`cancel_all`; no leak).
- [ ] T008 [US3] Extend the tests: count-cap denial, depth-cap denial, bad-cadence denial,
  containment (raising occurrence → recorded, parent ok), lifecycle (cancelled at scope exit),
  and **default-off byte-identity** (`max_schedules = 0` → no tools registered).

## Phase 5: Wiring (scope owners thread the supervisor)

- [ ] T009 Wire additively (the 048 pattern): optional
  `RuntimeController.drive(..., schedule_supervisor=None)` stamps it onto the `RunContext`; the
  **Dispatcher** builds a supervisor from its session task group (when `max_schedules > 0`); the
  one-shot **`host.run`** wraps a task group; `host/assembly.py` registers the scheduling tools +
  builds/injects the opaque supervisor factory only when `max_schedules > 0`. The controller
  holds the opaque factory (typed via the context Protocol) — **no `loopplane.tools` import in
  controller/dispatcher**.
- [ ] T010 Export the public name(s) (`ScheduleSupervisor` / the tool adapter) from
  `src/loopplane/tools/__init__.py` and add them to `docs/api-reference.md` (unit-014 bijection),
  mirroring 048's `BackgroundTaskSupervisor`/`BackgroundTasksAdapter`.

## Phase 6: Polish & Cross-Cutting

- [ ] T011 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof + default-off byte-identity). ALSO confirm the
  structural audits stay green: `test_no_execution_path_outside_the_gateway` (controller/loop
  do not import `loopplane.tools`) and `test_public_safety` (no secret-looking literals).

## Dependencies

- T001, T002 → block all. T003 → T004 (MVP). T004 → T005 → T006. T003/T004 → T007 → T008.
  T002/T003 → T009. T003 → T010. T010 → T011 (gates last).

## Implementation strategy

- **MVP = Phase 1 + 2 (US1)** + T009 wiring. US2/US3 add inspect/cancel + safety. The implement
  is cross-cutting — a fork subagent MAY do the mechanical multi-file work (mirroring the 048
  module + wiring exactly), then the four gates + the two structural audits are verified +
  committed in the main session.
- All changes additive; default-off (`max_schedules = 0`) byte-identical; reuse 048 + ADR 0002 +
  unit-004; no new ADR; no `Clock` contract change.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
