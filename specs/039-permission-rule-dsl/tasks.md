---
description: "Task list for the declarative permission rule DSL (spec 039)"
---

# Tasks: Declarative permission rule DSL (host-suppliable allow/deny/ask rules)

**Input**: Design documents from `/specs/039-permission-rule-dsl/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rule-dsl.md

**Tests**: REQUIRED (Constitution X). Write tests FIRST and confirm they FAIL before
implementing each unit. Every test is offline and deterministic (the governance helpers; a
scripted `InteractionBroker` for the `ask` round-trip). No network, no real model.

**Organization**: Grouped by user story (US1 arg-regex deny P1, US2 path-glob deny + allow
P1, US3 ask + precedence + default P2, US4 invalid-regex fail-closed P1, US5 empty-no-op
P1). US1/US2/US4/US5 need only the call+descriptor (use `decide`/`decide_with_context`);
US3's `ask` uses the scripted-broker round-trip.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Single project: `src/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the seams + the test harness; no new harness file is needed
(`tests/governance_helpers.py` already has `call` / `descriptor` / `decide` /
`decide_with_context`).

- [ ] T001 Confirm the reused seams by reading: `src/loopplane/approval/decisions.py` (the binary `PolicyVerdict` — no `PolicyAsk`), `src/loopplane/approval/approval.py::HumanApproval._escalate` (how `ask` reuses `request_approval`), `src/loopplane/approval/rules.py` (the `fnmatch` matcher + `resolve_rules` deny-wins), and `src/loopplane/host/assembly.py::_build_decider` (the `safe_failure(all_of(...))` composition). No code change.

**Checkpoint**: The verdict-model finding (binary verdict; `ask` = `request_approval`) and the composition point are confirmed.

---

## Phase 2: User Story 1 + 2 + 5 - matching (arg-regex / path-glob / allow), default, no-op (Priority: P1) 🎯 MVP

**Goal**: `rule_dsl_policy` matches a call by tool matcher AND every `match` (arg-regex /
path-glob), returns allow/deny, falls back to `default`, and is a no-op when empty — composed
deny-wins + fail-closed through the existing combinators.

**Independent Test**: Build the policy over the US1/US2 rules; decide matching / non-matching
calls; assert the verdicts and the default fall-through; an empty set with `default="allow"`
composed with another decider equals that decider alone.

### Tests for User Story 1 + 2 + 5 ⚠️ (write first, must FAIL)

- [ ] T002 [US1] Create `tests/unit/test_rule_dsl_policy.py` (using `tests/governance_helpers.py` `call`/`descriptor`/`decide`/`decide_with_context`, and `loopplane.governance.{PermissionRuleSet, PermissionRuleSpec, rule_dsl_policy}`): (a) `{tool: "run_command", match: {command: "^rm -rf"}, decision: "deny"}` + `default="allow"` → `run_command(command="rm -rf /")` → `PolicyDeny`; (b) same → `run_command(command="ls -la")` → `PolicyAllow` (default fall-through); (c) same rule, tool `read_file` → `PolicyAllow` (tool matcher gates first).
- [ ] T003 [US2] In the same file: (a) `{tool: "write_file", match: {path: "**/secrets/**"}, decision: "deny"}` → `write_file(path="app/secrets/key.pem")` → `PolicyDeny`; (b) same → `write_file(path="app/notes.md")` → `PolicyAllow` (default); (c) `{tool: "read_file", decision: "allow"}` → `read_file(path="x")` → `PolicyAllow`; (d) a Windows-style `write_file(path="app\\secrets\\k")` still → `PolicyDeny` (path normalized to `/`).
- [ ] T004 [US1/US2] In the same file: (a) a `match` naming an **absent** field (`{command: "^rm"}` on a `run_command` call with **no** `command` input) → the rule does **not** match → falls to `default` (`PolicyAllow`); (b) a non-string field under a regex `match` (e.g. an int) → coerced to its string form for the test.
- [ ] T005 [US5] In the same file: an **empty** `rule_dsl_policy(PermissionRuleSet(default="allow"))` composed `all_of(rule_dsl_policy(empty), allow_all)` decides a call identically to `allow_all` alone (`PolicyAllow`) — off/empty equals no policy.

### Implementation for User Story 1 + 2 + 5

- [ ] T006 [US1] Create `src/loopplane/governance/rule_dsl.py`: `PermissionRuleSpec` (frozen pydantic: `tool: str`, `match: Mapping[str, str] | None = None`, `decision: Literal["allow","deny","ask"]`) and `PermissionRuleSet` (frozen: `rules: tuple[PermissionRuleSpec, ...] = ()`, `default: Literal["allow","deny","ask"] = "allow"`). A `_PATH_FIELDS`/path-shaped helper (`path`, `file`, `*_path`). A compiled-rule structure built **eagerly** in `rule_dsl_policy`: for each `match` entry, compile a regex via `re.compile` (non-path field) or `re.compile(fnmatch.translate(pattern))` (path field). Implement `rule_dsl_policy(rules) -> PolicyDecider` returning an async decider that: selects matching rules (`fnmatchcase(call.tool_name, rule.tool)` AND every compiled `match` present-and-matching, normalizing a path field's `str(value)` to `/`), combines **deny>ask>allow**, falls back to `rules.default`; maps `allow`→`allow()`, `deny`→`deny(reason)`, `ask`→`_escalate` via `context.interactions.request_approval` (→ allow/deny; no broker → deny). Reads the call+descriptor (+ context for ask) only; never invokes a tool. Export `rule_dsl_policy` + `PermissionRuleSet` + `PermissionRuleSpec` from `src/loopplane/governance/__init__.py` (additive `__all__`, alphabetically placed).
- [ ] T007 [US1] Run `uv run pytest tests/unit/test_rule_dsl_policy.py -q` and confirm the US1/US2/US5 tests pass.

**Checkpoint**: The rule DSL matches + decides allow/deny + default and is provably a no-op when empty.

---

## Phase 3: User Story 3 + 4 - ask round-trip, precedence, invalid-regex, fail-closed (Priority: P2/P1)

**Goal**: `ask` reuses the existing approval round-trip (approve→allow, reject/no-human→deny);
deny-wins on conflict; an invalid regex is a construction error; the composed chain fails
closed.

**Independent Test**: Drive the `ask` rule against a scripted broker (approve / reject /
no-reviewer); assert the verdict. Build a policy over a bad regex and assert it raises. Wrap a
raising decider in `safe_failure(all_of(...))` and assert deny.

### Tests for User Story 3 + 4 ⚠️ (write first, must FAIL)

- [ ] T008 [US3] In `tests/unit/test_rule_dsl_policy.py`, add the `ask` round-trip (the scripted-`InteractionBroker` pattern from `tests/contract/test_approval.py`: a background task waits for the emitted `approval-requested` then calls `broker.resolve_approval(request_id, decision=…, scope="once")`): (a) an `{tool: "echo", decision: "ask"}` rule with a broker scripted to **allow** → `PolicyAllow`; (b) scripted to **deny** → `PolicyDeny`; (c) a context with **no broker** (`interactions=None`) → `PolicyDeny` (no reviewer); (d) `default="ask"` with no matching rule + an approving broker → `PolicyAllow`.
- [ ] T009 [US3] In the same file (no broker needed): (a) a matching `allow` rule + a matching `deny` rule on the same tool → `PolicyDeny` (deny-wins); (b) a call matching **no** rule with `default="deny"` → `PolicyDeny`; with `default="allow"` → `PolicyAllow`.
- [ ] T010 [US4] In the same file: (a) `rule_dsl_policy(PermissionRuleSet(rules=(PermissionRuleSpec(tool="run_command", match={"command": "["}, decision="deny"),)))` **raises** at construction (an invalid regex is a clear config error — `pytest.raises`); (b) `safe_failure(all_of(rule_dsl_policy(<rule>), <raising decider>))` decides → `PolicyDeny` (fail-closed); (c) `all_of(rule_dsl_policy(<deny rule>), allow_all)` denying a matching call → `PolicyDeny` (deny-wins in the composed chain).

### Implementation for User Story 3 + 4

- [ ] T011 [US4] In `src/loopplane/governance/rule_dsl.py`, ensure the regex/path-glob compilation in `rule_dsl_policy` happens **at construction** (so T010a raises there), with a clear error message naming the offending tool/field (public-safe — no secret). The `ask` escalation (`request_approval` → map resolution; `PolicyDeny("no reviewer available …")` when `context.interactions is None`) is implemented in the decider from T006; this task confirms the ask + fail-closed paths are correct.
- [ ] T012 [US3] Run `uv run pytest tests/unit/test_rule_dsl_policy.py -q` and confirm all US3/US4 tests pass.

**Checkpoint**: `ask` reuses the existing round-trip; precedence + default + fail-closed + invalid-regex are correct.

---

## Phase 4: Host wiring (supply rules via config) + assembly tests

**Goal**: `RuntimeConfig.permission_rules` carries the rule set; `_build_decider` composes
`rule_dsl_policy` when rules are present; absent → unchanged.

### Tests (write first, must FAIL)

- [ ] T013 In `tests/contract/test_host_config.py`, add additive tests (mirroring the network/plan-mode wiring tests): (a) `RuntimeConfig(model, tools=(run_command tool,), permission_rules=PermissionRuleSet(rules=(PermissionRuleSpec(tool="run_command", match={"command": "^rm -rf"}, decision="deny"),), default="allow"))` → `_build_decider(...)` is not `None` and **denies** `run_command(command="rm -rf /")` and **allows** `run_command(command="ls")`; (b) `RuntimeConfig.from_mapping({"model": m, "permission_rules": {"rules": [{"tool": "run_command", "match": {"command": "^rm -rf"}, "decision": "deny"}], "default": "allow"}})` round-trips (`.permission_rules` is a `PermissionRuleSet` with one rule) and the default is `None`; (c) `RuntimeConfig` still declares no secret field (the existing `test_runtime_config_declares_no_secret_field` covers this — confirm it still passes); (d) `permission_rules=None` (or an empty set with no other policy + egress on) keeps the allow-all fast-path (`_build_decider(...) is None`).

### Implementation

- [ ] T014 In `src/loopplane/host/config.py`, add `permission_rules: PermissionRuleSet | None = None` to `RuntimeConfig` (after `plan_mode`) and a `_coerce_permission_rules(value)` helper used in `from_mapping`: pass a `PermissionRuleSet` through; build one from a mapping `{"rules": [ {tool, match?, decision}, ... ], "default": ...}` (coercing each rule dict to `PermissionRuleSpec`); `None` → `None`. Import `PermissionRuleSet`/`PermissionRuleSpec` from `loopplane.governance`.
- [ ] T015 In `src/loopplane/host/assembly.py::_build_decider`: (a) compute `rules_needed = config.permission_rules is not None and bool(config.permission_rules.rules)`; include it in the early gate so a decider is built when rules are present; (b) when `rules_needed`, append `rule_dsl_policy(config.permission_rules)` to the composed `deciders` (after `network_policy`/`plan_mode`). Import `rule_dsl_policy`. Preserve the `None` fast-path when no rules **and** nothing else needs a decider.
- [ ] T016 Run `uv run pytest tests/contract/test_host_config.py -q` and confirm the new wiring tests pass.

**Checkpoint**: Rules are suppliable via config end-to-end; absent is unchanged.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T017 Regression: run `uv run pytest tests/contract/test_approval.py tests/unit/test_network_policy.py tests/unit/test_plan_mode_policy.py tests/contract/test_tool_gateway.py -q` and confirm the approval boundary, the existing policies, and the gateway are unchanged by the additive module/field/composition.
- [ ] T018 Docs: in `docs/api-reference.md`, add `- `rule_dsl_policy` — …`, `- `PermissionRuleSet` — …`, `- `PermissionRuleSpec` — …` bullets under `### `loopplane.governance``; confirm the bijection (`uv run pytest tests/contract/test_api_reference.py -q`).
- [ ] T019 Quality gates: `uv run ruff check .`, `uv run ruff format .` then `uv run ruff format --check .`, `uv run mypy`, `uv run pytest -q` — all green.
- [ ] T020 Run the `quickstart.md` validation commands and confirm expected outcomes.
- [ ] T021 [P] Update tracking: `CHANGELOG.md` (a `- **039**` entry after 038), `docs/loopplane-agent-board.md` (a `039-permission-rule-dsl` Verified row after 038 + §4 update), `CLAUDE.md` (SPECKIT block → `specs/039-permission-rule-dsl/plan.md`), and `.specify/feature.json` (`specs\\039-permission-rule-dsl`).

---

## Dependencies & Execution Order

- **T001 (Setup)** → confirms the seams (no code).
- **US1+US2+US5 (T002–T007)** is the foundation: the matcher + allow/deny/default + the
  no-op default must exist before `ask`/precedence/wiring.
- **US3+US4 (T008–T012)** depend on the policy (T006); they add the `ask` round-trip,
  precedence, the construction-time invalid-regex error, and fail-closed.
- **Host wiring (T013–T016)** depends on the policy (T006) and the config field (T014); it
  threads them through assembly.
- Within each story: tests FAIL first → implementation → verify.
- **Polish (T017–T021)** after all stories.

## Parallel Opportunities

- Limited: the policy (`governance/rule_dsl.py`) is one file; the config + assembly changes
  build on it. T021 (tracking-doc updates) is `[P]` (different files).

## Implementation Strategy

- **MVP** = Phase 1 + Phase 2 (US1/US2 matching + allow/deny/default + US5 no-op) — the
  safety foundation, independently shippable and the precondition for `ask`/wiring.
- Then add US3/US4 (`ask` round-trip + precedence + fail-closed + invalid-regex) and the host
  wiring incrementally; each leaves the baseline set, the loop, the gateway, the approval
  boundary, and every existing policy intact.

## Notes

- **No new dependency** (`re` + `fnmatch` are stdlib; `pydantic` is already core). No
  frontend. **No event/gateway/loop/schema/approval change**, **no new gateway stage** (the
  DSL reuses the existing decide-stage combinators). **No ADR** (a decide-stage policy that
  reuses the existing approval events + the existing verdict union; touches neither Tool
  Gateway execution (V) nor the Event Bus / schema (VI), and blurs no boundary (IV)).
- **No per-run / controller change**: `ask` reads the per-run `RunContext` the Gateway
  already hands the decider (unlike 038, which needed a holder + a controller line). The only
  wiring is the additive `_build_decider` composition + the config field.
- No secret anywhere: `RuntimeConfig.permission_rules` carries only tool names + patterns +
  decisions (the no-secret contract test still passes).
- Rollback = delete `governance/rule_dsl.py` + its export, the `RuntimeConfig.permission_rules`
  field + coercion, the `_build_decider` composition, the api-reference bullets, and the new
  test module.
