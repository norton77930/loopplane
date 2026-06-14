---
description: "Task list for unit 015 — LoopPlane Lifecycle Hook System"
---

# Tasks: LoopPlane Lifecycle Hook System

**Input**: Design documents from `specs/015-loopplane-hook-system/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). Write each test FIRST and confirm it FAILS
before the matching implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: may run in parallel (different files, no ordering dependency)
- **[Story]**: the user story (US1–US5) the task serves

---

## Phase 1: Setup

- [ ] T001 Create the `src/loopplane/hooks/` package directory with an empty
  `__init__.py` placeholder so the subpackage imports.

---

## Phase 2: Foundational — the hooks core (BLOCKS every user story)

**⚠️ No user-story wiring may begin until this phase is green.**

- [ ] T002 [P] Unit test `tests/unit/test_hooks_points.py`: `LifecyclePoint` has the
  eleven members; each payload dataclass is frozen and exposes its
  data-model.md fields; gating vs observational classification is correct. (FAIL first)
- [ ] T003 [P] Unit test `tests/unit/test_hooks_decisions.py`: `ToolGateAllow/Deny/Modify`
  and `PromptAllow/Block/Annotate` construct, are frozen, and carry public-safe
  fields. (FAIL first)
- [ ] T004 [P] Unit test `tests/unit/test_hooks_registry.py`: `register` appends FIFO,
  duplicate registration fires twice, `unregister` removes the first match and
  reports it, `clear(point)` and `clear()` behave (FR-001/FR-003). (FAIL first)
- [ ] T005 [P] Unit test `tests/unit/test_hooks_dispatcher.py`: observational `fire`
  runs all callbacks in order and isolates a raising one via an injected
  diagnostic sink (FR-005); `decide_tool`/`decide_prompt` resolve deny-wins +
  ordered-compose + abstain-on-failure (FR-016/FR-017); sync and async callbacks
  both run (FR-004); a callback registered mid-fire does not affect the in-flight
  firing (FR-018). (FAIL first)
- [ ] T006 Implement `src/loopplane/hooks/points.py` — `LifecyclePoint` + the eleven
  frozen, metadata-only payload dataclasses (data-model.md).
- [ ] T007 Implement `src/loopplane/hooks/decisions.py` — `ToolGateDecision` and
  `PromptDecision` families.
- [ ] T008 Implement `src/loopplane/hooks/registry.py` — `HookRegistry`
  (register/unregister/clear; ordered per-point lists). Depends on T006/T007.
- [ ] T009 Implement `src/loopplane/hooks/dispatcher.py` — `HookDispatcher`: `fire`,
  `decide_tool`, `decide_prompt`; per-fire snapshot; isolation through an injected
  `diagnostic` callback (no raw exception/inputs — FR-015); coroutine detection.
  Depends on T006–T008.
- [ ] T010 Implement `src/loopplane/hooks/__init__.py` public surface (`__all__`:
  points, payloads, decision types, `HookRegistry`, `HookDispatcher`). Depends on T006–T009.

**Checkpoint**: hooks core passes unit tests; nothing else touched yet.

---

## Phase 3: User Story 1 — observe every tool call (P1) 🎯 MVP

- [ ] T011 [US1] Integration test `tests/integration/test_hooks_us1.py`: after_tool_use
  fires once per success and after_tool_failure once per execution/timeout failure,
  in tool order, with metadata-only payloads, and the run outcome is unchanged
  vs. no hooks (SC-001/SC-004). (FAIL first)
- [ ] T012 [US1] Wire `src/loopplane/gateway/gateway.py`: add optional
  `hooks: HookDispatcher | None = None`; in `_run_one` fire after_tool_use on
  success and after_tool_failure on the execution/timeout `_failure` branch;
  isolate via the existing `emitter.diagnostic`. Default-absent path unchanged
  (FR-011). Depends on Phase 2.

**Checkpoint**: US1 works independently.

---

## Phase 4: User Story 2 — gate or rewrite a tool call (P1)

- [ ] T013 [US2] Integration test `tests/integration/test_hooks_us2.py`: a before_tool
  `Deny` surfaces a normalized `POLICY_DENIAL` and the tool never runs; a `Modify`
  re-validates and executes with the new input; a hook cannot widen a call the
  approval boundary already denied (FR-006/FR-008/FR-012, SC-002). (FAIL first)
- [ ] T014 [US2] Wire `src/loopplane/gateway/gateway.py`: fire before_tool_use after
  Stage 3 `decide` on the allow path; apply `ToolGateDeny` → `_failure(POLICY_DENIAL)`,
  `ToolGateModify` → replace input and re-run `validate_input` before execute.
  Depends on T012.

**Checkpoint**: US1 + US2 both work.

---

## Phase 5: User Story 3 — run follow-up when the model stops (P2)

- [ ] T015 [US3] Integration test `tests/integration/test_hooks_us3.py`: model_stop
  fires exactly once at natural-completion with a metadata-only payload. (FAIL first)
- [ ] T016 [US3] Wire `src/loopplane/loop/loop.py`: add optional `hooks`; fire
  model_stop at the `natural-completion` termination. Depends on Phase 2.

**Checkpoint**: US3 works.

---

## Phase 6: User Story 4 — screen or annotate a prompt (P2)

- [ ] T017 [US4] Integration test `tests/integration/test_hooks_us4.py`: a `Block`
  prevents the model call (normalized termination); an `Annotate` makes the model
  receive the augmented prompt (FR-007, SC-006). (FAIL first)
- [ ] T018 [US4] Wire `src/loopplane/loop/loop.py`: fire user_prompt_submit before the
  first model turn; apply `PromptBlock`/`PromptAnnotate`. Depends on T016.
- [ ] T019 [US4] Wire session_start: fire on a session's first `drive`
  (`src/loopplane/loop/loop.py` + `src/loopplane/controller/controller.py`).
  Depends on T018.

**Checkpoint**: US4 works.

---

## Phase 7: User Story 5 — session / subagent / file lifecycle (P3)

- [ ] T020 [US5] Integration test `tests/integration/test_hooks_us5.py`: process_setup
  fires at most once across two sessions; session_end fires on terminate/detach;
  file_changed fires after a successful write/edit-class tool and not on failure;
  subagent_start/stop bracket a delegated run (FR-013/FR-014/FR-019). (FAIL first)
- [ ] T021 [US5] Wire `src/loopplane/controller/controller.py`: add optional
  `hooks: HookRegistry | None = None`; own one `HookDispatcher`; inject it into each
  session's Gateway/Loop and the Coordinator; fire process_setup (once) and
  session_end. Depends on Phase 2.
- [ ] T022 [US5] Wire file_changed in `src/loopplane/gateway/gateway.py` via the
  descriptor write/edit capability tag (fire after success only). Depends on T012.
- [ ] T023 [US5] Wire `src/loopplane/orchestration/coordinator.py`: optional `hooks`;
  fire subagent_start before and subagent_stop after each delegated `run_loop`.
  Depends on Phase 2.

**Checkpoint**: all five user stories work independently.

---

## Phase 8: Boundary, public-safety, and polish

- [ ] T024 [P] Boundary test `tests/integration/test_hooks_boundary.py`: `loopplane.hooks`
  imports only allowed surfaces; hooks never invoke a tool or re-emit/mutate the
  event bus (Constitution V/VI); the default-absent path adds no events.
- [ ] T025 [P] Public-safety test `tests/integration/test_hooks_public_safety.py`:
  payloads and the on-failure diagnostic carry no secret, private path, internal
  name, or raw exception detail (FR-015, SC-005).
- [ ] T026 [P] Zero-behavior-change test: a representative run with `hooks=None`
  produces the same normalized events/outcome as before this feature (SC-003).
- [ ] T027 [P] Add `examples/hooks_quickstart.py` — credential-free scripted-model
  observe + gate walkthrough (quickstart.md).
- [ ] T028 [P] Add `docs/hooks.md` — the hook guide.
- [ ] T029 Update `docs/api-reference.md` with the `loopplane.hooks` public names
  (the unit-014 `test_api_reference` contract enforces the `__all__` bijection).
- [ ] T030 Update `docs/README.md` and `examples/README.md` indexes for the new
  guide/example (the unit-014 `test_docs_examples_index` contract enforces
  index↔tree consistency).
- [ ] T031 Run `ruff format --check`, `ruff check`, `mypy` (strict), and the full
  `pytest` suite; fix to green.
- [ ] T032 Final review: set unit 015 to **Verified** in
  `docs/loopplane-agent-board.md` (§3 row + §4) and commit.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational core)** blocks all user stories.
- **US1–US5 (Phases 3–7)** each depend only on Phase 2 and are independently
  testable; within the Gateway, T012 → T014 → T022 touch the same file and are
  sequential. T016 → T018 → T019 share `loop.py` and are sequential.
- **Phase 8** depends on the desired user stories being complete; T029/T030 are
  required for the unit-014 release contract tests to stay green.

### Parallel opportunities

- T002–T005 (unit tests, different files) run in parallel.
- T024–T028 (boundary/safety tests, example, docs — different files) run in parallel.

## Implementation Strategy

- **MVP** = Phase 1 + 2 + Phase 3 (US1): the registry/dispatcher plus tool-call
  observation. Validate, then add US2 (gating), then US3–US5.
- Commit after each green checkpoint; push after each safe commit (board §11).
- Per board §8, a Dynamic Workflow may accelerate independent test groups during
  implement, but final integration and the `pytest` run happen in the main session.

## Notes

- `[P]` = different files, no ordering dependency.
- Every test is written to FAIL first, then made to pass by its implementation task.
- Hooks stay additive: every seam is an optional `hooks` parameter defaulting to
  absent, so omitting it reproduces today's behavior exactly (FR-011/FR-020/SC-003).
