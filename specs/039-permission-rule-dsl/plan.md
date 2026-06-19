# Implementation Plan: Declarative permission rule DSL (host-suppliable allow/deny/ask rules)

**Branch**: `039-permission-rule-dsl` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/039-permission-rule-dsl/spec.md`

## Summary

Add a LoopPlane-native **declarative permission rule DSL**: a host can supply an ordered
rule set — each rule a `tool` (exact name or `fnmatch` pattern), an optional `match` (a map
of input-field → regex and/or a path-glob for path-shaped fields), and a `decision`
(`allow` | `deny` | `ask`), plus a top-level `default` — that the Tool Gateway enforces at
its **decide stage**. The mechanism is **additive and enforced only at the Tool Gateway
decide stage** (Constitution V), mirroring the spec-034 `network_policy` / spec-038
`plan_mode_policy` precedent:

- A **`rule_dsl_policy` decider** (`src/loopplane/governance/rule_dsl.py`) that, for a call,
  selects the rules whose **`tool` matcher AND every `match` pattern** match
  (`call.tool_name` + the string form of `call.input` fields), combines them with a
  documented **SAFE** precedence (**deny-wins**, then **ask**, then **allow** — reusing
  `resolve_rules`' deny-wins semantics for the name dimension), and falls back to the
  **`default`** decision on no match. It returns the **existing** `PolicyVerdict`: `allow`
  → `PolicyAllow`, `deny` → `PolicyDeny`, `ask` → it **reuses the existing approval
  round-trip** (`context.interactions.request_approval`, the same path the Human Approval
  boundary's `_escalate` uses) and maps the `ApprovalResolution` to `PolicyAllow` /
  `PolicyDeny`. It is composed through the **existing** combinators (`all_of` deny-wins +
  `safe_failure` fail-closed) in `host/assembly.py::_build_decider` — **no new gateway
  stage**.
- The DSL's rule shapes (`PermissionRuleSpec`, `PermissionRuleSet`) live with the decider in
  `governance/rule_dsl.py` and are **compiled eagerly** at policy construction: an invalid
  regex (or an invalid `decision`/`default`) raises a clear config error there
  (fail-closed) — never a silent allow at decide time.
- An additive, default-empty, public-safe **`RuntimeConfig.permission_rules:
  PermissionRuleSet | None = None`** field (coerced in `from_mapping` from a plain mapping
  `{"rules": [...], "default": "..."}`), wired through `host/assembly.py::_build_decider`
  so that when rules are present the policy is composed in; default (absent/empty) leaves
  existing runs **byte-identical**.

The verdict-model finding (recorded in `research.md`) drives the shape: `PolicyVerdict` is
**binary** (`PolicyAllow | PolicyDeny` — no `PolicyAsk`), and "ask" is **decider
behaviour** that calls `request_approval`. So `rule_dsl_policy` is an **async,
context-reading** decider (like `plan_mode_policy`), not a context-free `as_decider`
wrapper.

The change is purely additive: **no core agent-loop change**, **no gateway-pipeline
change**, **no event-bus / event-schema change**, **no approval-boundary change**, and
**no existing-tool / descriptor behaviour change**. **No ADR** (a decide-stage policy that
reuses the existing approval events and the existing verdict union — neither the Tool
Gateway execution path (V) nor the Event Bus / schema (VI) changes, and no boundary is
blurred (IV)). This is a **Tier-2 governance unit**.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Standard library (`re`, `fnmatch`) + the existing `loopplane`
internals only (the `governance` combinators, the `PolicyVerdict` / `PolicyAllow` /
`PolicyDeny` types, `resolve_rules` / `PermissionRule` for the matcher semantics, the
`InteractionBroker.request_approval` round-trip, `ToolCallRequest` / `ToolDescriptor` /
`RunContext`). No new runtime dependency. `pydantic` is already in core (reused for the
frozen rule shapes, matching `PermissionRule`).

**Storage**: N/A — the rule set is an in-memory `RuntimeConfig` field; nothing is
persisted, no file is read.

**Testing**: pytest (offline, deterministic), mirroring `tests/governance_helpers.py`
(`call` / `descriptor` / `decide` / `decide_with_context`) and the scripted
`InteractionBroker` round-trip from `tests/contract/test_approval.py` (the
`approval-requested` → `resolve_approval` pattern) for the `ask` path. Additive assembly
tests in `tests/contract/test_host_config.py` for the `permission_rules` wiring. No
network, no real model.

**Target Platform**: Cross-platform library runtime (Windows/macOS/Linux)

**Project Type**: Single project — embeddable Python library/runtime

**Performance Goals**: Interactive single-call latency; the decider is a linear scan over
the (typically small) rule list with pre-compiled regexes; no new per-call work on the
no-rules path (no DSL policy installed when `permission_rules` is absent).

**Constraints**: Enforcement at the Gateway decide stage only (V); no new gateway stage; no
core agent-loop change; no event-schema change; no approval-boundary change; default-empty
so existing runs are byte-identical; rules public-safe (no secret, VII).

**Scale/Scope**: One new governance module (`rule_dsl.py`: two frozen rule shapes + the
`rule_dsl_policy` decider with eager regex compilation), one additive `RuntimeConfig` field
+ its `from_mapping` coercion, the `_build_decider` composition, plus deterministic offline
unit tests + additive assembly tests + the api-reference bijection bullets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I — Spec-First**: PASS. Plan traces to spec 039; tasks will trace to this plan.
- **II — Greenfield**: PASS. New code written fresh; no legacy code copied; the reference
  harnesses inform the *concept* only (IX), re-derived as a decide-stage policy reusing
  LoopPlane's own rule/verdict/approval machinery.
- **III — Harness Before Loop Automation**: PASS. No scheduler/validator/evaluator/
  auto-iteration. The rule DSL is a **governance policy**, not loop automation: the human is
  the approver (for `ask`) and the existing loop drives the turns unchanged.
- **IV — Runtime Boundary Clarity**: PASS. No boundary is blurred. The policy is a
  decide-stage `PolicyDecider` (the Tool Gateway's existing seam); the `ask` round-trip is
  the **existing** `InteractionBroker.request_approval` (the Human Approval boundary),
  reused verbatim — no new cross-component channel, no reach-through. → **No ADR required.**
- **V — Tool Gateway Ownership** (key gate): PASS. All enforcement is at the Gateway
  **decide stage**; the rule DSL is a *policy*, never a bypass. The decider never resolves or
  executes a tool; it only returns allow/deny (and, for `ask`, requests a human decision and
  maps it to allow/deny). It is composed through the **existing** combinators — **no new
  gateway stage**.
- **VI — Event Bus**: PASS. **No event-schema change.** `ask` reuses the existing
  `request_approval` round-trip, which emits the existing `approval-requested` /
  `approval-resolved` events; no new event type, no `SCHEMA_VERSION` bump. The loop emits
  the same normalized events as today.
- **VII — Public-Safe**: PASS. No secret, no internal path. `RuntimeConfig.permission_rules`
  carries only tool names, patterns, and decisions; a contract test asserts the config still
  declares no secret field, and the DSL types carry no credential.
- **VIII / IX — No SDK Replacement / Reference-not-clone**: PASS. No framework adopted. The
  rule DSL is re-derived as a LoopPlane decide-stage policy reusing the existing
  rule/verdict/approval machinery, not a copy of a reference harness's implementation.
- **X — Testable Evolution**: PASS. Deterministic offline tests for the policy (arg-regex
  deny + non-match-falls-to-default, path-glob deny, allow rule, `ask` round-trip via a
  scripted broker, deny-wins, default-on-no-match, invalid-regex-is-a-config-error,
  fail-closed, empty-equals-no-policy) and the assembly wiring + `from_mapping` round-trip +
  no-secret. Rollback = delete `governance/rule_dsl.py` + its export, the
  `RuntimeConfig.permission_rules` field + coercion, the `_build_decider` composition, the
  api-reference bullets, and the new test module (all additive, reversible).

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/039-permission-rule-dsl/
├── plan.md              # This file
├── research.md          # Phase 0 output (verdict-model finding + precedence + matcher choices)
├── data-model.md        # Phase 1 output (the rule shapes)
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── rule-dsl.md      # Policy + rule-shape + config contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/loopplane/
├── governance/
│   ├── rule_dsl.py         # NEW: PermissionRuleSpec + PermissionRuleSet + rule_dsl_policy.
│   │                       #   Eager regex compilation at construction (fail-closed); a call
│   │                       #   matches a rule iff its tool fnmatches AND every `match` field
│   │                       #   (regex or path-glob) matches; combine deny>ask>allow; fall back
│   │                       #   to default; allow→PolicyAllow, deny→PolicyDeny, ask→reuse
│   │                       #   context.interactions.request_approval and map the resolution.
│   └── __init__.py         # MODIFY: export rule_dsl_policy (+ the rule shapes) (additive __all__)
├── host/
│   ├── config.py           # MODIFY: RuntimeConfig + permission_rules: PermissionRuleSet | None
│   │                       #   = None (+ from_mapping coercion from {"rules": [...],
│   │                       #   "default": "..."}); no secret
│   └── assembly.py         # MODIFY: _build_decider composes rule_dsl_policy via the existing
│   │                       #   all_of + safe_failure when permission_rules is present;
│   │                       #   preserve the None fast-path otherwise
├── approval/
│   ├── decisions.py        # USE (unchanged): PolicyAllow / PolicyDeny / PolicyVerdict
│   ├── rules.py            # USE (unchanged): the fnmatch matcher semantics (resolve_rules)
│   └── interactions.py     # USE (unchanged): InteractionBroker.request_approval (the ask path)
├── model/
│   └── boundary.py         # USE (unchanged): ToolCallRequest (.tool_name + .input), ToolDescriptor
├── context.py              # USE (unchanged): RunContext.interactions (the ask round-trip)
└── gateway/                # USE (unchanged): decide stage already passes (call, descriptor, context, emitter)

docs/
├── api-reference.md        # MODIFY: + rule_dsl_policy (+ rule shapes) bullets under loopplane.governance
└── loopplane-agent-board.md# MODIFY: + 039 §3 row; §4 update

tests/
├── governance_helpers.py   # USE (unchanged): call / descriptor / decide / decide_with_context
└── unit/
    ├── test_rule_dsl_policy.py   # NEW: arg-regex deny / non-match-default / path-glob deny /
    │                             #   allow / ask round-trip (scripted broker) / deny-wins /
    │                             #   default / invalid-regex-config-error / fail-closed /
    │                             #   empty-equals-no-policy
    └── (tests/contract/test_host_config.py)  # MODIFY (additive): permission_rules wiring →
                                  #   decider denies the matching call; from_mapping; no-secret
```

**Structure Decision**: Single-project library layout. The DSL is a new cohesive
`governance/rule_dsl.py` (sibling to `network.py` / `plan_mode.py`), composed through the
**existing** `_build_decider` combinators. The rule shapes live with the decider (they are
the decider's own input vocabulary, compiled eagerly there) rather than in `approval/rules.py`
— that module holds the *runtime* `PermissionRule`/`resolve_rules` the Human Approval
boundary uses, which the DSL **reuses for matcher semantics** but does not extend. The
`RuntimeConfig.permission_rules` field carries the host-suppliable set; the only wiring is
the additive `_build_decider` composition (no controller / per-run change is needed — `ask`
reads the per-run `RunContext` the Gateway already hands the decider).

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
