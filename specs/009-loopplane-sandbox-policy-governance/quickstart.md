# Quickstart & Validation: Sandbox, Policy & Governance Layer (Phase-9)

A validation guide for `loopplane.governance`. It proves the layer decides allow/deny deterministically at
the gateway's policy seam — over scripted tool calls and descriptors, with no gateway, no execution, and a
default-deny posture. Implementation detail lives in [data-model.md](./data-model.md) and
[contracts/](./contracts); these are runnable scenarios.

## Prerequisites

- The repo installed editable with dev tools: `python -m pip install -e .` and `pytest` + `anyio`.
- Phase 1 is Verified (the public `loopplane.approval` policy/rule contracts and the `loopplane.model`
  tool-call/descriptor models this layer composes).

## What the example shows

`examples/governance_quickstart.py` (public-safe, credential-free):

1. Builds a `permission_policy` from a couple of `PermissionRule`s, a `path_policy` rooted at a directory, a
   `capability_policy(require_read_only=True)`, and a `budget_policy`.
2. Composes them into a `sandbox_profile` (deny-wins, fail-safe).
3. Decides a handful of scripted `ToolCallRequest` / `ToolDescriptor` pairs and prints each verdict (allow /
   deny + reason) — invoking no tool.

Run:

```bash
python examples/governance_quickstart.py
```

Expected: allowed calls return **allow**; a denied tool, an escaping path, a non-read-only tool, or an
over-budget call returns **deny** with a public-safe reason; nothing is executed.

## Validation scenarios (map to user stories & success criteria)

| Scenario | How to validate | Proves |
|---|---|---|
| US1 — permission gate | `permission_policy([...])`: allowed ⇒ allow, denied ⇒ deny, unmatched ⇒ deny | SC-001, SC-003, FR-010-FR-011 |
| Reuses the engine | permission verdicts match `resolve_rules(rules, name)` for the same inputs | SC-009, FR-082 |
| Determinism | the same call/descriptor/state decided twice ⇒ identical verdict | SC-002, NFR-001 |
| US2 — path containment | a contained path ⇒ allow; `..` traversal, an absolute outside path, a missing/non-string path ⇒ deny | SC-004, FR-020-FR-021 |
| US3 — budget + quota | costed calls allowed until the ceiling then denied; spend inspectable; a tool denied at its quota | SC-007, FR-040-FR-050 |
| US4 — deny-wins combinator | `all_of(allow_policy, deny_policy)` ⇒ deny with the denier's reason; empty `all_of()` ⇒ deny | SC-008, FR-060 |
| US4 — capability | `capability_policy(require_read_only=True)`: mutating tool ⇒ deny, read-only ⇒ allow | SC-005, FR-030 |
| US5 — safe-failure | `safe_failure(raising_policy)` ⇒ deny (never allow); `default_deny()` ⇒ deny | SC-003, FR-071 |
| US5 — sandbox profile | `sandbox_profile(...)` composes its policies deny-wins and fail-safe | FR-070 |
| No execution | contract audit: no `.invoke(`/`.run(` reference; imports only approval/model/context/events | SC-005, FR-080/FR-081 |
| Public-safety | scan committed files + `PHASE9_TARGETS` | SC-006, NFR-002 |

## Test commands

```bash
python -m pytest tests/unit/test_governance_core.py tests/integration -k governance --basetemp=".pytmp" -q
python -m pytest tests/contract/test_governance_boundary.py --basetemp=".pytmp" -q

# Full gates (run before any commit touching source/tests)
python -m ruff format && python -m ruff check && python -m mypy
python -m pytest --basetemp=".pytmp" -q
```

Expected: all governance suites green; ruff + mypy(strict) clean; public-safety scan green.

## What this layer does NOT do

It never executes, resolves, or OS-sandboxes a tool (the Tool Gateway owns execution — Constitution V), and
it never orchestrates human approval (the Phase-1 Human Approval boundary owns that). No OS sandboxing, no
remote policy service, no hot-reload, no persistent budget/quota state, no ML cost (reserved — FR-090-FR-094).
It only decides allow/deny at the gateway's policy seam.
