---
description: "Task list for Sandbox, Policy & Governance Layer (009)"
---

# Tasks: Sandbox, Policy & Governance Layer

**Input**: Design documents from `/specs/009-loopplane-sandbox-policy-governance/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL before
implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases PA–PF map below; Foundational (the
decider adapter) blocks all stories. US1 is the permission gate (the MVP).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/governance/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Phase-1 policy contracts: `PolicyAllow` / `PolicyDeny` /
`PolicyVerdict` / `PolicyDecider` + `PermissionRule` / `resolve_rules` (`loopplane.approval`),
`ToolCallRequest` / `ToolDescriptor` (`loopplane.model`), and `RunContext` / `EventEmitter`
(`loopplane.context` / `loopplane.events`, signature only). It MUST NOT import the `ToolGateway`
implementation, a Phase-1 runtime control internal (`loopplane.controller`, `loopplane.gateway`), the Human
Approval interaction symbols (`InteractionBroker`), a Phase-2 host symbol, or a sibling layer. Every policy
**returns a verdict and never executes a tool** (Constitution V). See
[contracts/governance-boundary.md](./contracts/governance-boundary.md). No Phase-1/2/3 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create the `loopplane.governance` package skeleton: `src/loopplane/governance/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [ ] T002 [P] Add governance test helpers in `tests/governance_helpers.py`: a `call(tool_name, **input)` builder over the public `ToolCallRequest`; a `descriptor(name="t", *, source="s", read_only=False, concurrency_safe=False)` builder over `ToolDescriptor`; and an `async def decide(policy, the_call, the_descriptor)` that awaits the decider with `None` for the (ignored) run context and event emitter and returns the verdict.

---

## Phase 2: Foundational (Blocking Prerequisites — the decider adapter)

**Purpose**: The verdict helpers and the adapter every policy uses to target the gateway's decider shape.
**⚠️ Blocks US1–US5.**

- [ ] T003 [P] Write unit tests in `tests/unit/test_governance_core.py` (MUST FAIL first): `allow()` returns a `PolicyAllow`; `deny(reason)` returns a `PolicyDeny` carrying the reason; `as_decider` wraps a simple `(call, descriptor) -> verdict` into a `PolicyDecider` that, when awaited (with any run context / emitter), returns that verdict and never touches the trailing params (FR-001, FR-002).
- [ ] T004 [P] Implement `src/loopplane/governance/base.py`: `SimpleDecision` alias, `allow()`, `deny(reason)`, and `as_decider(decision)` (an async four-parameter `PolicyDecider` that ignores the run context / emitter and never invokes) (FR-001, FR-002).
- [ ] T005 Populate `src/loopplane/governance/__init__.py` exports for `allow`, `deny`, `as_decider`.
- [ ] T006 Run `pytest tests/unit/test_governance_core.py --basetemp=".pytmp"` → green (gate for Foundational).

**Checkpoint**: The verdict helpers and the decider adapter are ready.

---

## Phase 3: User Story 1 - Gate tool calls by permission rules (Priority: P1) 🎯 MVP

**Goal**: A permission policy decides a call by the Phase-1 `resolve_rules` over a set of rules; allowed ⇒
allow, denied ⇒ deny, unmatched ⇒ deny (safe default).

**Independent Test**: With scripted rules and calls, assert an allowed tool ⇒ allow, a denied tool ⇒ deny, an
unmatched tool ⇒ deny; the permission verdict matches `resolve_rules` for the same inputs.

- [ ] T007 [P] [US1] Write integration tests in `tests/integration/test_governance_us1.py` (MUST FAIL first): `permission_policy([...])` over scripted `PermissionRule`s yields allow for an allowed tool, deny for a denied tool, and deny for an unmatched tool (default-deny); `default="allow"` makes an unmatched tool allow; the verdict matches `resolve_rules(rules, tool_name)` for the same inputs; no tool is invoked (US1 scenarios 1–3; SC-001/003/009).
- [ ] T008 [US1] Implement `src/loopplane/governance/permission.py`: `permission_policy(rules, *, default="deny")` calling the Phase-1 `resolve_rules` and mapping deny/allow/None→default to a verdict via `as_decider` (FR-010–FR-011, FR-082).
- [ ] T009 [US1] Export `permission_policy`; run `pytest tests/integration/test_governance_us1.py --basetemp=".pytmp"` → green.

**Checkpoint**: MVP — a host gates which tools may run, safe by default.

---

## Phase 4: User Story 2 - Restrict tool arguments to an allowed path root (Priority: P2)

**Goal**: A path policy denies a call whose path argument escapes an allowed root.

**Independent Test**: A contained path ⇒ allow; a `..` traversal, an absolute outside path, and a
missing/non-string path ⇒ deny.

- [ ] T010 [P] [US2] Write integration tests in `tests/integration/test_governance_us2.py` (MUST FAIL first): `path_policy(root, key="path")` yields allow for a path within the root, deny for a `..` traversal, deny for an absolute path outside the root, and deny for a missing or non-string path argument (never a silent allow); deterministic (US2 scenarios 1–3; SC-004, NFR-001/NFR-005).
- [ ] T011 [US2] Implement `src/loopplane/governance/path.py`: `path_policy(allowed_root, *, key="path")` reading `call.input[key]`, normalizing the path lexically (POSIX-style `.`/`..`, no filesystem access), and denying any path not contained within the root (FR-020–FR-021).
- [ ] T012 [US2] Export `path_policy`; run `pytest tests/integration/test_governance_us2.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1 + US2 — tool gating and argument containment.

---

## Phase 5: User Story 3 - Bound cost and per-tool quota (Priority: P2)

**Goal**: Budget (cumulative cost/calls) + quota (per-tool) policies deny once a ceiling is reached, with a
deterministic cost model and inspectable spend.

**Independent Test**: Costed calls allowed until the budget is exhausted then denied (spend inspectable); a
tool denied once its quota is reached.

- [ ] T013 [P] [US3] Write integration tests in `tests/integration/test_governance_us3.py` (MUST FAIL first): `CostModel({...}).cost(name)` returns the weight or the default; `budget_policy(ceiling, cost_model=...)` allows calls until adding the next cost would exceed the ceiling then denies, and the running spend reflects the consumed cost; `quota_policy({tool: K})` denies the tool on its (K+1)th call; deterministic over the same sequence (US3 scenarios 1–2; SC-007, NFR-001).
- [ ] T014 [US3] Implement `src/loopplane/governance/budget.py`: `CostModel` (weights + default + `cost()`), a stateful `budget_policy(ceiling, *, cost_model=CostModel({}))` with an inspectable spend, and a stateful `quota_policy(limits)` (FR-040–FR-050).
- [ ] T015 [US3] Export `CostModel`, `budget_policy`, `quota_policy`; run `pytest tests/integration/test_governance_us3.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US3 — gating, containment, and cost/quota bounds.

---

## Phase 6: User Story 4 - Compose policies and gate by capability (Priority: P2)

**Goal**: A capability policy by declared descriptor flags + a deny-wins combinator.

**Independent Test**: `all_of(allow, deny)` ⇒ deny with the denier's reason; an empty `all_of()` ⇒ deny; a
read-only capability policy denies a mutating tool and allows a read-only tool.

- [ ] T016 [P] [US4] Write integration tests in `tests/integration/test_governance_us4.py` (MUST FAIL first): `capability_policy(require_read_only=True)` yields deny for a non-read-only tool and allow for a read-only tool; `all_of(allow_policy, deny_policy)` yields deny with the denying policy's reason (deny-wins, short-circuit); `all_of(allow_policy, allow_policy)` yields allow; an empty `all_of()` yields deny (US4 scenarios 1–2; SC-008, FR-030/FR-060).
- [ ] T017 [P] [US4] Implement `src/loopplane/governance/capability.py`: `capability_policy(*, require_read_only=False, require_concurrency_safe=False)` (FR-030).
- [ ] T018 [US4] Implement `src/loopplane/governance/combine.py`: `all_of(*policies)` (deny-wins; empty ⇒ deny) (FR-060).
- [ ] T019 [US4] Export `capability_policy`, `all_of`; run `pytest tests/integration/test_governance_us4.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US4 — composable, capability-aware gating.

---

## Phase 7: User Story 5 - Fail safe and apply a named sandbox profile (Priority: P3)

**Goal**: Safe-failure governance (raise ⇒ deny) + a named sandbox profile bundling policies.

**Independent Test**: `safe_failure(raising_policy)` ⇒ deny (never allow); `default_deny()` ⇒ deny; a
`sandbox_profile(...)` composes its policies deny-wins and fail-safe.

- [ ] T020 [P] [US5] Write integration tests in `tests/integration/test_governance_us5.py` (MUST FAIL first): `safe_failure(policy_that_raises)` yields deny with a public-safe reason (never allow); `default_deny()` yields deny; `sandbox_profile(permission=…, path=…, capability=…, budget=…)` denies when any bundled policy denies and allows when all allow; a sandbox bundling a raising policy still yields deny (US5 scenarios 1–2; SC-003, FR-070/FR-071).
- [ ] T021 [US5] Extend `src/loopplane/governance/combine.py`: `safe_failure(policy, *, reason="policy error")` (any raise ⇒ deny) and `default_deny(reason="denied by default")` (FR-071).
- [ ] T022 [US5] Implement `src/loopplane/governance/sandbox.py`: `sandbox_profile(*, permission=None, path=None, capability=None, budget=None)` composing the supplied policies with `all_of` and wrapping in `safe_failure` (FR-070).
- [ ] T023 [US5] Export `safe_failure`, `default_deny`, `sandbox_profile`; run `pytest tests/integration/test_governance_us5.py --basetemp=".pytmp"` → green.

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Write contract tests in `tests/contract/test_governance_boundary.py`: an import-boundary audit (every `src/loopplane/governance/*.py` imports only `loopplane.approval` / `loopplane.model` / `loopplane.context` / `loopplane.events` / `loopplane.governance` + stdlib, and references no `ToolGateway` / `loopplane.controller` / `loopplane.gateway` / `InteractionBroker` / `loopplane.host` / sibling-layer token); a **no-invoke** audit (no `.invoke(` / `.run(` reference in any module); permission verdicts match `resolve_rules`; determinism (FR-080/FR-081/FR-082, NFR-003/NFR-006, SC-002/005/009).
- [ ] T025 [P] Extend `tests/contract/test_public_safety.py` with `PHASE9_TARGETS` (`src/loopplane/governance`, `examples/governance_quickstart.py`, `docs/sandbox-policy-governance.md`, `specs/009-loopplane-sandbox-policy-governance`) and a `test_phase9_governance_files_are_public_safe` scan.
- [ ] T026 [P] Create `examples/governance_quickstart.py`: a public-safe, credential-free runnable building a permission + path + capability + budget sandbox profile and deciding scripted calls (allow/deny + reason), invoking no tool (per [quickstart.md](./quickstart.md)).
- [ ] T027 [P] Create `docs/sandbox-policy-governance.md`: a public-safe guide — permission/path/capability/budget/quota → combine → sandbox, Constitution V (the gateway owns execution), the Human-Approval distinction, and the reserved extension points (FR-090–FR-094).
- [ ] T028 Finalize `src/loopplane/governance/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [ ] T029 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/governance_quickstart.py`; confirm the public-safety scan is green (SC-006); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (the decider adapter).
- **US1 (Phase 3)**: depends on Foundational. MVP (permission gate).
- **US2 (Phase 4)**, **US3 (Phase 5)**: depend on Foundational; independent of each other and of US1.
- **US4 (Phase 6)**: depends on Foundational; the combinator composes any deciders.
- **US5 (Phase 7)**: depends on US4 (`all_of`) for the sandbox profile; safe-failure extends `combine.py`.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- The adapter before the policies; `all_of` before the sandbox profile; each phase ends on its pytest gate.
- Commit per stable phase; push after each safe commit.

## Parallel Opportunities

- T002 (helpers) runs alongside the Phase-2 test authoring.
- Within Foundational: T003 (test) and T004 (base) are `[P]`.
- Across stories: `permission.py`, `path.py`, `budget.py`, `capability.py` are independent files — their
  `[P]` test-authoring and implementation can proceed in parallel once Foundational is green (US5 waits on
  US4's `all_of`).
- Polish: T024–T027 are independent files (`[P]`); T028/T029 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (the decider adapter) → Phase 3 US1 (permission gate).
2. **STOP and VALIDATE**: a host gates which tools may run, safe by default, with no tool invoked.

### Incremental Delivery

Foundational → US1 (MVP) → US2 (path) → US3 (budget/quota) → US4 (capability + combinator) → US5
(safe-failure + sandbox) → Polish. Each phase is an independently testable, revertible increment; no
Phase-1/2/3 source is modified.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- Every policy returns a verdict and **never invokes a tool**; tests assert no invocation and default-deny on
  every failure mode.
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: importing the `ToolGateway`/runtime internals/`InteractionBroker`/sibling layers; executing a tool;
  a silent allow on a no-match, malformed argument, raising policy, or empty combinator.
