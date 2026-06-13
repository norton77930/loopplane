# Implementation Plan: Sandbox, Policy & Governance Layer

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-loopplane-sandbox-policy-governance/spec.md`

## Summary

Build the **Sandbox, Policy & Governance** layer (Phase-9) that lets a host constrain **which tool calls are
permitted — before any tool runs**. A new additive sub-package, `loopplane.governance`, ships reusable,
deterministic, public-safe **policy deciders** shaped to the Tool Gateway's decide-stage `PolicyDecider`
interface: a **permission** policy (reusing the Phase-1 `resolve_rules` engine), a **path** containment
policy, a **capability** policy, a **budget** policy with a **cost model**, a **quota** policy, a **deny-wins
combinator**, **safe-failure** governance (default-deny), and a named **sandbox profile**. Every policy
returns a Phase-1 `PolicyVerdict` (allow / deny-with-reason) and **never executes, resolves, or OS-sandboxes
a tool** — the **Tool Gateway stays the single chokepoint** that executes tools (Constitution V). The layer
composes only the public Phase-1 policy/approval contracts; it never bypasses the gateway and is distinct
from the Phase-1 Human Approval boundary. Design detail lives in [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–8).

**Primary Dependencies**: the public Phase-1 policy/approval surface — `PolicyAllow` / `PolicyDeny` /
`PolicyVerdict` / `PolicyDecider`, the permission engine (`PermissionRule` / `RuleEffect` / `RuleScope` /
`resolve_rules`) from `loopplane.approval`; the `ToolCallRequest` / `ToolDescriptor` models from
`loopplane.model`; and the `RunContext` (`loopplane.context`) / `EventEmitter` (`loopplane.events`) the
decider signature carries. Plus the stdlib. **No new third-party dependency.**

**Storage**: None. Budget/quota state is in-process per decider instance for a run; persistent cross-restart
state is a reserved extension point.

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted `ToolCallRequest` / `ToolDescriptor` + a no-op run context and event emitter are
the deterministic instruments (NFR-001, SC-002) — no gateway, no execution.

**Target Platform**: Cross-platform library embedded in a host process; a pure-decision layer with no host,
transport, or UI dependency.

**Performance Goals**: Negligible — each decider is an O(1)–O(rules) decision. Determinism preserved
(NFR-001).

**Constraints**: returns `PolicyVerdict` only (FR-001); **no tool invocation** (NFR-006, SC-005);
default-deny (NFR-005, SC-003); deterministic (NFR-001, SC-002); reuse the Phase-1 rule engine, never
re-implement precedence (FR-082, SC-009); public-safe (NFR-002, SC-006); distinct from Human Approval
(FR-082).

**Scale/Scope**: One new package (~8 modules), one example, one doc, unit/integration/contract suites.
**No Phase-1/2/3 source is modified.**

## Dependency on Phase 1

This phase is **strictly additive** and consumes only public Phase-1 policy contracts — it composes them and
re-derives none of them (NFR-003, FR-082):

- **`loopplane.approval`**: `PolicyAllow` / `PolicyDeny` / `PolicyVerdict` / `PolicyDecider` (the verdict +
  the decide-stage interface the gateway consults), and `PermissionRule` / `RuleEffect` / `RuleScope` /
  `resolve_rules` (the permission policy reuses this engine — no re-implemented precedence).
- **`loopplane.model`**: `ToolCallRequest` (`call_id` / `tool_name` / `input`) and `ToolDescriptor` (declared
  capabilities) — the decision inputs.
- **`loopplane.context`** / **`loopplane.events`**: `RunContext` and `EventEmitter` — the trailing decider
  signature parameters (accepted; most policies decide from the call + descriptor alone).

**Non-duplication guarantee (FR-082, SC-009)**: the layer contains **no** tool execution, no rule-precedence
re-implementation, and no human-approval interaction orchestration. It only produces deciders that return
verdicts; the gateway executes, the Phase-1 engine resolves rule precedence, and the Phase-1 Human Approval
boundary owns interactive approval.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.governance` depends on the public `loopplane.approval`,
`loopplane.model`, `loopplane.context`, and `loopplane.events`; the gateway, runtime, host, and every
loop-layer sibling have **zero** knowledge of the governance layer.

```text
platform developer
     │ configures policies (permission / path / capability / budget / quota / sandbox)
     ▼
loopplane.governance.<policy>(...) -> PolicyDecider     (an async (call, descriptor, context, emitter) -> verdict)
     │ compose with deny-wins all_of(...) + safe_failure(...)
     ▼
ToolGateway(decide=<the composed PolicyDecider>)        ◄── Phase-1: the gateway consults it BEFORE executing
     │ allow ⇒ the gateway executes; deny ⇒ the gateway blocks the call
     ▼
Tool Gateway is the ONLY thing that executes tools (Constitution V)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/governance-boundary.md](./contracts/governance-boundary.md)):

- The layer integrates **only** by producing `PolicyDecider`s the gateway consults; it never executes,
  resolves, or OS-sandboxes a tool and never starts a run (FR-002, FR-080, NFR-006).
- It reuses the Phase-1 `resolve_rules` engine for permission precedence and never re-implements it (FR-010,
  FR-082, SC-009).
- It imports only `loopplane.approval`, `loopplane.model`, `loopplane.context`, `loopplane.events`, and
  stdlib; it does **not** import the `ToolGateway` implementation, a Phase-1 runtime control internal
  (`loopplane.controller`), a Phase-2 host symbol, or a sibling layer (FR-081, NFR-003).

## Project Structure

### Documentation (this feature)

```text
specs/009-loopplane-sandbox-policy-governance/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── policies.md             # the deciders: permission, path, capability, budget, quota, combinators, sandbox
│   └── governance-boundary.md  # PolicyDecider integration, the boundary + non-execution audit
├── checklists/requirements.md
└── tasks.md                    # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/governance/
├── __init__.py        # public exports
├── base.py            # SimpleDecision + as_decider + deny()/allow helpers (FR-001, FR-002)
├── permission.py      # permission_policy over resolve_rules (FR-010-FR-011)
├── path.py            # path_policy (deterministic lexical containment) (FR-020-FR-021)
├── capability.py      # capability_policy (FR-030)
├── budget.py          # CostModel + budget_policy + quota_policy (FR-040-FR-050)
├── combine.py         # all_of (deny-wins) + safe_failure + default_deny (FR-060, FR-071)
└── sandbox.py         # sandbox_profile (FR-070)

examples/
└── governance_quickstart.py  # runnable: build policies, compose a sandbox, decide scripted calls (public-safe)

docs/
└── sandbox-policy-governance.md  # public-safe guide: permission/path/capability/budget/quota -> combine -> sandbox

tests/
├── unit/
│   └── test_governance_core.py     # as_decider, deny-wins all_of, safe_failure, default_deny, cost model
├── integration/
│   ├── test_governance_us1.py      # US1: permission policy over resolve_rules, default-deny (SC-001/003/009)
│   ├── test_governance_us2.py      # US2: path containment, traversal/absolute/missing -> deny (SC-004)
│   ├── test_governance_us3.py      # US3: budget + cost + quota ceilings (SC-007)
│   ├── test_governance_us4.py      # US4: capability + deny-wins combinator (SC-008)
│   └── test_governance_us5.py      # US5: safe-failure + sandbox profile (SC-003)
└── contract/
    └── test_governance_boundary.py # import-boundary + no-invoke audit + determinism (SC-002/005/009)
```

**Structure Decision**: one new sub-package `loopplane.governance`, mirroring the Phase-1..8
one-package-per-boundary convention so the layer is a single, clearly-bounded, independently revertible
addition. It depends inward on the public Phase-1 policy/approval contracts only. No Phase-1/2/3 source is
modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| PA — Foundational + permission (US1) | `base.py` (`SimpleDecision`, `as_decider`, helpers), `permission.py` + package skeleton + `__init__` + scripted helpers — **blocks all stories** | `test_governance_core.py` + `test_governance_us1.py` green (SC-001/003/009) | Revert package; nothing depends on it |
| PB — Path policy (US2) | `path.py` (deterministic lexical containment) | `test_governance_us2.py` green; traversal/absolute/missing ⇒ deny (SC-004) | Revert PB |
| PC — Budget, cost, quota (US3) | `budget.py` (`CostModel`, `budget_policy`, `quota_policy`) | `test_governance_us3.py` green; ceilings enforced (SC-007) | Revert PC |
| PD — Capability + combinator (US4) | `capability.py`, `combine.py` (`all_of` deny-wins) | `test_governance_us4.py` green; deny-wins (SC-008) | Revert PD |
| PE — Safe-failure + sandbox (US5) | `combine.py` (`safe_failure`, `default_deny`), `sandbox.py` (`sandbox_profile`) | `test_governance_us5.py` green; raise ⇒ deny (SC-003) | Revert PE |
| PF — Example, docs, boundary | `examples/governance_quickstart.py`, `docs/sandbox-policy-governance.md`, `test_governance_boundary.py` + public-safety `PHASE9_TARGETS` | boundary + no-invoke + determinism green; example runs; scan clean (SC-002/005/006/009) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| A silent **allow** on a fault or ambiguity (Constitution-level safety breach) | Default-deny everywhere: a no-match, a malformed/missing argument, a raising policy, or an empty combinator maps to **deny**; a safe-failure wrapper + dedicated tests assert it (FR-011, FR-071, NFR-005, SC-003) |
| Executing or OS-sandboxing a tool (Constitution V breach) | The layer returns verdicts only and never holds an execution path; a no-invoke contract test + the import audit forbid execution surfaces (FR-002, FR-080, NFR-006, SC-005) |
| Re-implementing rule precedence (divergence from Phase-1) | The permission policy calls the Phase-1 `resolve_rules`; a test asserts its verdicts match the engine (FR-010, FR-082, SC-009) |
| Reaching the gateway implementation or a runtime internal | Import-boundary audit: `loopplane.governance` imports only `approval` / `model` / `context` / `events` + stdlib; references no `ToolGateway` / `loopplane.controller` / host symbol (FR-081, NFR-003) |
| A path escape slipping through (traversal / absolute) | Pure lexical containment normalizes `.`/`..` without filesystem access and rejects any path not under the root; traversal/absolute/missing tests assert 0 escapes (FR-020, FR-021, SC-004) |
| Non-determinism in budget/quota ordering | State is a simple in-process counter/tally mutated deterministically by the call sequence; a determinism test runs the same sequence twice (NFR-001, SC-002/007) |
| Scope creep into OS sandboxing / remote policy | Out-of-scope list + reserved extension points (FR-090–FR-094); Constitution III gate; only deterministic, offline, decision-only policies ship |

**Rollback posture**: `loopplane.governance` is purely **additive** over Phase 1 — small, task-scoped
commits, each phase (PA–PF) independently revertible. The layer owns no execution path and only in-process
per-instance counters, so reverting any or all leaves the gateway, runtime, and every loop layer untouched.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.governance` written fresh; composes the public policy contracts; no legacy code copied (FR-082) |
| III | Agent Harness Before Loop Automation | PASS | A deterministic, offline decision layer over the existing policy seam; ships **no** OS sandbox/remote/dynamic policy and names every reserved extension point (FR-090–FR-094) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (decide allow/deny at the gateway's policy seam); depends inward on public policy contracts; no execution logic (FR-002, FR-080, FR-081) |
| V | Tool Gateway Ownership | PASS | **Central**: every policy returns a verdict and never executes, resolves, or OS-sandboxes a tool; execution stays the gateway's; a no-invoke contract test enforces it (FR-002, FR-080, NFR-006) |
| VI | Runtime Event Bus Ownership | PASS | Accepts the `EventEmitter` the decider signature carries but emits no competing stream; verdicts are plain return values |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; deny reasons are public-safe; scan extended with PHASE9 targets (NFR-002, SC-006) |
| VIII | No SDK Replacement | PASS | No policy framework introduced; pure stdlib composition over LoopPlane's own policy seam |
| IX | Reference, Not Clone | PASS | Policy/governance concepts re-derived public-safe from the spec and the public contracts; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (PA–PF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; determinism + default-deny + non-execution first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and no
Phase-1/2/3 modification. The layer executes nothing and owns only in-process per-instance counters.
Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
