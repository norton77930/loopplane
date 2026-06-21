# Implementation Plan: Pre-Turn Cost Guard

**Branch**: `068-pre-turn-cost-guard` (main-only autopilot) | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/068-pre-turn-cost-guard/spec.md`

**Boundary**: settled by **[ADR 0014](../../docs/adr/0014-pre-turn-cost-guard.md)** (board
pre-settled: "add pre-turn estimate"). This extends ADR 0005's USD budget enforcement with an
optional pre-model-call guard; it reuses `budget-exceeded`, adds no event-schema version bump, and
keeps post-turn actual-cost enforcement authoritative.

## Summary

Add a default-off pre-turn USD cost guard before `AgentLoop` calls the model. After the request is
assembled, estimate request input tokens with the same local request-size heuristic used by prompt
assembly, combine that with a host-configured maximum output token estimate, price the estimate via
the host's existing `PricingTable`, and compare it against the known remaining per-message and
per-session USD caps on the existing `BudgetChecker`. If the estimate would exceed a known cap,
terminate the run with `budget-exceeded` before the model call. If any input is unavailable
(pricing, model id, max-output estimate, request-token estimate, or active known cap), fail open and
let the existing post-turn checker remain the final enforcement layer.

## Technical Context

**Language/Version**: Python 3.11+; stdlib `decimal`.

**Primary Dependencies**: none new - reuses `loopplane.pricing.PricingTable`, 055's
`loopplane.budget.BudgetChecker`, `ModelRequest`, and the loop's existing terminate path.

**Storage**: none new. Pre-turn checks do not reserve spend and do not write ledger state.

**Testing**: pytest, offline - a scripted model with call counting plus pricing/caps: predicted
overage refuses before the model call; under-estimate proceeds and post-turn accounting still
enforces; incomplete estimate inputs fail open; default-off behavior is unchanged.

**Target Platform**: cross-platform library.

**Project Type**: Python runtime library with CLI/web host surfaces already layered above it.

**Performance Goals**: bounded synchronous estimate before a model call; no network, no file IO, no
provider call, and no durable ledger mutation.

**Constraints**: additive; default-off; fail-open; reuse `budget-exceeded`; no `SCHEMA_VERSION`
bump; no new dependency; no raw price/cap/prompt values in diagnostics; no Tool Gateway change.

**Scale/Scope**: one optional guard on the per-session budget checker plus host/controller/loop
wiring. Durable per-user-monthly predictive enforcement remains out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001...FR-010 and ADR 0014. PASS.
- **III. Agent Harness Before Loop Automation**: A bounded opt-in cost-safety primitive; no new
  scheduler/evaluator/automation layer. PASS.
- **IV. Runtime Boundary Clarity**: The check occurs at the Agent Loop model-call boundary after
  request assembly and before `stream_turn`; ADR 0014 records this boundary extension. PASS.
- **V. Tool Gateway Ownership**: N/A - no tool resolution, authorization, or execution path changes.
  PASS.
- **VI. Runtime Event Bus Ownership**: Reuses existing `budget-exceeded`; no new event type, no
  termination reason addition, no schema version bump. PASS.
- **VII. Public-Safe Documentation**: Diagnostics and docs must not include prompt text, private
  paths, raw prices, cap amounts, principals, tokens, or secrets. PASS.
- **X. Testable Evolution**: Default-off, reversible, offline-testable; post-turn accounting remains
  authoritative. PASS.

**Post-design re-check**: PASS. The design remains additive and default-off; ADR 0014 records the
only new boundary decision. Complexity Tracking is not required.

## Project Structure

### Documentation (this feature)

```text
specs/068-pre-turn-cost-guard/
├── plan.md
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── pre-turn-cost-guard.md
└── checklists/
    └── requirements.md

docs/adr/0014-pre-turn-cost-guard.md
```

### Source Code (repository root)

```text
src/loopplane/budget/__init__.py        # MODIFIED: non-mutating pre-turn estimate/decision on
                                        # BudgetChecker; expose remaining per-message/session view
src/loopplane/loop/assembly.py          # MODIFIED: public request-token estimation helper reusing
                                        # the existing char-per-token heuristic
src/loopplane/loop/loop.py              # MODIFIED: after _assemble(...) and before stream_turn(...),
                                        # call the checker and terminate budget-exceeded on refusal
src/loopplane/controller/controller.py  # MODIFIED: accept/pass pre_turn_max_output_tokens to the
                                        # per-session BudgetChecker
src/loopplane/host/config.py            # MODIFIED: RuntimeConfig.pre_turn_max_output_tokens
                                        # (int|None, default None) + from_mapping + validation
src/loopplane/host/assembly.py          # MODIFIED: forward pre_turn_max_output_tokens
docs/api-reference.md                   # MODIFIED if RuntimeConfig public reference lists the new
                                        # config field
tests/unit/test_pre_turn_cost_guard.py  # NEW: focused offline coverage
tests/unit/test_budget_caps.py          # MODIFIED only if shared checker behavior needs coverage
```

**Structure Decision**: Keep the guard inside the existing budget seam. `RuntimeConfig` gets one
host-owned opt-in scalar (`pre_turn_max_output_tokens`). The controller passes it into the same
per-session `BudgetChecker` that already holds caps, pricing, model id, and spend totals.
`BudgetChecker` performs a non-mutating pre-turn decision using an estimated input count and the
configured max-output estimate. `AgentLoop` invokes that decision after assembling the
`ModelRequest` and before the model call. The loop emits `budget-exceeded` and returns on refusal;
otherwise it calls the model and the existing post-turn `record_turn`/`exceeded` path remains
authoritative.

## Complexity Tracking

> No unjustified complexity. The extra loop check is a small ADR-recorded extension of the existing
> 055 budget seam. Durable monthly-budget prediction/reservation is intentionally not added; it
> would require a separate ledger reservation/read model and is outside this unit.
