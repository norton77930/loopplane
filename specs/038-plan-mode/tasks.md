---
description: "Task list for Plan Mode (read-only investigation → human approval → execute) (spec 038)"
---

# Tasks: Plan Mode (read-only investigation → human approval → execute)

**Input**: Design documents from `/specs/038-plan-mode/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/plan-mode.md

**Tests**: REQUIRED (Constitution X). Write tests FIRST and confirm they FAIL before
implementing each unit. Every test is offline and deterministic (a scripted
`InteractionBroker`; the internal-tool harness; the governance helpers). No network,
no real model.

**Organization**: Grouped by user story (US1 plan-mode policy P1, US2 approve→execute
P2, US3 reject/no-human P3, US4 off-is-a-no-op P1). US1 + US4 are the foundation (the
gate and its no-op default must exist before approval matters). The holder + the
`RunContext` field are shared infrastructure both the policy and the tool depend on.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Single project: `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The per-run holder, the additive `RunContext` field, and the test harness.

- [ ] T001 In `src/loopplane/context.py`, add a minimal `PlanModeState` dataclass (`active: bool = True`) and an additive `RunContext.plan_mode: PlanModeState | None = None` field (after `interactions`); no other change.
- [ ] T002 In `tests/governance_helpers.py`, add an additive `decide_with_context(policy, the_call, the_descriptor, context)` runner (awaits `policy(call, descriptor, context, None)`) so a policy that reads `RunContext` can be exercised; leave the existing `decide` (which passes `None`) unchanged.

**Checkpoint**: The holder + field exist; the context-bearing test runner is ready.

---

## Phase 2: User Story 1 - Plan-mode policy denies non-read-only, allows read-only + allowlist (Priority: P1) 🎯 MVP + User Story 4 (off is a no-op, P1)

**Goal**: `plan_mode_policy` denies non-read-only tools (except the allowlist) while
active, allows read-only tools, and is a no-op when inactive/absent — composed
deny-wins + fail-closed through the existing combinators.

**Independent Test**: With an active holder, decide `write_file` → deny, each read-only
tool → allow, each allowlisted tool → allow; with an inactive/absent holder, decide
everything → allow.

### Tests for User Story 1 + 4 ⚠️ (write first, must FAIL)

- [ ] T003 [US1] Create `tests/unit/test_plan_mode_policy.py` (using `tests/governance_helpers.py` `call`/`descriptor` + the new `decide_with_context`, and `loopplane.context.PlanModeState`/`RunContext`): (a) active + `write_file` (read_only=False) → `PolicyDeny`; (b) active + `run_command` (read_only=False) → `PolicyDeny`; (c) active + each of `read_file`/`grep`/`glob_files`/`search_files` (read_only=True) → `PolicyAllow`; (d) active + `ask_user` and `exit_plan_mode` (read_only=False, allowlisted) → `PolicyAllow`; (e) **inactive** holder (`active=False`) + `write_file` → `PolicyAllow` (no-op); (f) **absent** holder (`context.plan_mode is None`) + `write_file` → `PolicyAllow` (US4-1); (g) explicit `state=` argument overrides the context holder.
- [ ] T004 [US1] In `tests/unit/test_plan_mode_policy.py`, add composition tests: `safe_failure(all_of(plan_mode_policy(active), <raising policy>))` → `PolicyDeny` (fail-closed, US1-4); `all_of(plan_mode_policy(active), allow_all)` denying `write_file` → deny-wins; an **off** policy composed with another decider equals that decider alone for `write_file` (off-equals-no-policy, US4).

### Implementation for User Story 1 + 4

- [ ] T005 [US1] Create `src/loopplane/governance/plan_mode.py`: `PLAN_MODE_ALLOWLIST = frozenset({"ask_user", "exit_plan_mode"})` and `plan_mode_policy(state=None, *, allowlist=PLAN_MODE_ALLOWLIST) -> PolicyDecider`. The returned async decider resolves `S = state if state is not None else context.plan_mode`; if `S is None or not S.active` → `allow()`; elif `descriptor.read_only` → `allow()`; elif `descriptor.name in allowlist` → `allow()`; else `deny("plan mode is active: <name> is not a read-only tool")`. Reads the descriptor + holder only; never invokes a tool. Export `plan_mode_policy` from `src/loopplane/governance/__init__.py` (additive `__all__`, alphabetically placed).
- [ ] T006 [US1] Run `uv run pytest tests/unit/test_plan_mode_policy.py -q` and confirm all US1/US4 policy tests pass.

**Checkpoint**: The plan-mode gate is enforceable and provably a no-op when off — the foundation the tool depends on.

---

## Phase 3: User Story 2 + 3 - `exit_plan_mode`: approve clears (execute); reject / no-human keeps (Priority: P2/P3)

**Goal**: `exit_plan_mode` submits the plan through the existing human round-trip;
approve clears the holder (so a subsequent `write_file` decision allows); reject / no
human keeps it active and returns a clear normalized outcome.

**Independent Test**: Drive `exit_plan_mode` against a scripted broker (approve / reject
/ no-reviewer); assert the holder state and the output shape, then decide `write_file`.

### Tests for User Story 2 + 3 ⚠️ (write first, must FAIL)

- [ ] T007 [US2] Create `tests/unit/test_plan_mode_tool.py` (the `_context`/`_invoke` harness from `tests/unit/test_internal_file_tools.py`, `pytest.mark.anyio`, plus a scripted `InteractionBroker`): with a broker that has a reviewer attached and pre-answers `["approve"]` to the next question (drive the answer via a background task or a pre-seeded answerer), calling `exit_plan_mode` with a `plan` (a) sets `context.plan_mode.active is False` and (b) yields a non-error `TextBlock`; then (c) `plan_mode_policy()` decides `write_file` over that same context → `PolicyAllow`.
- [ ] T008 [US3] In `tests/unit/test_plan_mode_tool.py`, add: (a) a broker scripted to answer `["reject"]` → `context.plan_mode.active` stays `True`, the output is a clear non-approval `TextBlock`, and a subsequent `write_file` decision → `PolicyDeny`; (b) a broker with **no reviewer attached** (so `ask_question` returns `None`) → `context.plan_mode.active` stays `True`, the output is an `ErrorOutput`, and `write_file` still → `PolicyDeny`.

### Implementation for User Story 2 + 3

- [ ] T009 [US2] In `src/loopplane/tools/internal.py`, add the `exit_plan_mode` descriptor to `_DESCRIPTORS` (`network=False`, `read_only=False`, `concurrency_safe=False`; the `plan` string input schema from `data-model.md`) and register `"exit_plan_mode": self._exit_plan_mode` in the `invoke` handler map.
- [ ] T010 [US2] In `src/loopplane/tools/internal.py`, implement `_exit_plan_mode(call_input, context)`: read `plan = str(call_input["plan"])`; if `context.interactions is None` → `ErrorOutput("no user is available to approve the plan")` and return (do **not** flip); build one `Question` ("Approve this plan? …" carrying the plan, options `["approve", "reject"]`); `answers = await context.interactions.ask_question([question])`; if `answers is None` → `ErrorOutput("no user is available to approve the plan")` (leave plan mode active); if the first answer lower-cased is `"approve"` → if `context.plan_mode is not None`: `context.plan_mode.active = False`; yield `TextBlock("plan approved; proceeding to execute")`; else → `TextBlock("plan not approved; remaining in plan mode")` (leave active).
- [ ] T011 [US2] Run `uv run pytest tests/unit/test_plan_mode_tool.py -q` and confirm all US2/US3 tool tests pass.

**Checkpoint**: `exit_plan_mode` clears plan mode on approval and safely keeps it otherwise.

---

## Phase 4: Host wiring (enter plan mode via config) + assembly tests

**Goal**: `RuntimeConfig.plan_mode` starts a run in plan mode; `_build_decider`
installs the policy; the controller builds the per-run holder.

### Tests (write first, must FAIL)

- [ ] T012 In `tests/contract/test_host_config.py`, add additive tests: (a) `RuntimeConfig(model, tools=(write_file tool,), plan_mode=True)` → `_build_decider(...)` is not `None` and **denies** `write_file` for a `RunContext(plan_mode=PlanModeState(active=True))` and **allows** it for a `RunContext` with `plan_mode=None` (proving the installed policy is a no-op without a holder); (b) `RuntimeConfig.from_mapping({"model": m, "plan_mode": True}).plan_mode is True` and the default is `False`; (c) `RuntimeConfig` still declares no secret field.

### Implementation

- [ ] T013 In `src/loopplane/host/config.py`, add `plan_mode: bool = False` to `RuntimeConfig` (after `allow_network`) and coerce it in `from_mapping` (`bool(data.get("plan_mode", False))`).
- [ ] T014 In `src/loopplane/controller/controller.py`, add a `plan_mode: bool = False` constructor kwarg (stored as `self._plan_mode`); in `drive()`, construct `RunContext(..., plan_mode=PlanModeState(active=True) if self._plan_mode else None)`. Import `PlanModeState` from `loopplane.context`. **No other controller/loop change.**
- [ ] T015 In `src/loopplane/host/assembly.py`: (a) in `_build_decider`, when `config.plan_mode` is `True`, append `plan_mode_policy()` (the context-reading form) to the composed `deciders` and ensure a decider is built (extend the `approval_needed`/`network_gate_needed` gate with a `plan_mode_needed = config.plan_mode`); (b) pass `plan_mode=config.plan_mode` into the `RuntimeController(...)` kwargs (additive). Preserve the `None` fast-path when plan mode is off *and* nothing else needs a decider.
- [ ] T016 Run `uv run pytest tests/contract/test_host_config.py -q` and confirm the new wiring tests pass.

**Checkpoint**: Plan mode is enterable via config end-to-end; off is unchanged.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T017 Regression: run `uv run pytest tests/unit/test_internal_file_tools.py tests/contract/test_tool_gateway.py tests/unit/test_network_policy.py -q` and confirm the existing internal tools, the gateway, and the network policy are unchanged by the additive holder/field/descriptor.
- [ ] T018 Docs: in `docs/api-reference.md`, add a `- `plan_mode_policy` — …` bullet under `### `loopplane.governance``; confirm the bijection (`uv run pytest tests/contract/test_api_reference.py -q`).
- [ ] T019 Quality gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` — all green.
- [ ] T020 Run the `quickstart.md` validation commands and confirm expected outcomes.
- [ ] T021 [P] Update tracking: `CHANGELOG.md` (a `- **038**` entry after 037), `docs/loopplane-agent-board.md` (a `038-plan-mode` Verified row after 037 + §4 update, noting it opens Tier-2), `CLAUDE.md` (SPECKIT block → `specs/038-plan-mode/plan.md`), and `.specify/feature.json` (`specs\\038-plan-mode`).

---

## Dependencies & Execution Order

- **T001–T002 (Setup)** → everything (the holder + field + test runner are shared).
- **US1+US4 (T003–T006)** is the foundation: the policy + its no-op default must exist
  and be tested before the tool/wiring. **US1/US4 → US2/US3 → host wiring.**
- **US2+US3 (T007–T011)** depend on the holder (T001) and the policy (T005, to assert the
  `write_file` flip).
- **Host wiring (T012–T016)** depends on the policy (T005), the holder (T001), and the
  config flag (T013); it threads them through assembly + the controller.
- Within each story: tests (T003/T004, T007/T008, T012) FAIL first → implementation → verify.
- **Polish (T017–T021)** after all stories.

## Parallel Opportunities

- Limited: the policy (`governance/plan_mode.py`) and the tool (`tools/internal.py`) are
  separate files but the tool tests assert the policy's verdict (so the policy lands
  first). T021 (tracking-doc updates) is `[P]` (different files).

## Implementation Strategy

- **MVP** = Phase 1 + Phase 2 (US1 policy + US4 no-op default) — the safety foundation,
  independently shippable and the precondition for the tool.
- Then add US2/US3 (`exit_plan_mode`) and the host wiring incrementally; each leaves the
  baseline set, the loop, the gateway, and every existing policy intact.

## Notes

- **No new dependency.** No frontend. **No event/gateway/loop/schema change**, **no new
  gateway stage** (the plan-mode gate reuses the existing decide-stage combinators).
  **No ADR** (a decide-stage policy; touches neither Tool Gateway execution (V) nor the
  Event Bus / schema (VI), and blurs no boundary (IV)).
- The **only** per-run wiring is in `controller.drive()` (the single place `RunContext`
  is built) — one additive kwarg + one line; the loop/turn cycle is untouched. Flag this
  for the reviewer.
- No secret anywhere: `RuntimeConfig.plan_mode` is a bare boolean.
- Rollback = delete `governance/plan_mode.py` + its export, the `PlanModeState` holder +
  the `RunContext.plan_mode` field, the `exit_plan_mode` descriptor/handler, the
  `RuntimeConfig.plan_mode` flag, the controller kwarg + `drive()` line, the
  `_build_decider` composition, the api-reference bullet, and the new test modules.
