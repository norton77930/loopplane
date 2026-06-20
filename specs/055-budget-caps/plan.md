# Implementation Plan: USD Budget Caps (In-Loop Enforcement)

**Branch**: `055-budget-caps` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/055-budget-caps/spec.md`

**Boundary review**: settled by **[ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md)**
(maintainer-approved at the G22 design boundary review; authored at this plan step, no re-consult).
Two boundary crossings — an in-loop enforcement point (IV) + a new `budget-exceeded`
`TerminationReason` (VI, additive within `SCHEMA_VERSION = 1`, **no bump**) — both approved.
Everything else is additive + default-off (byte-identical when no caps are set).

## Summary

Wire 053's pricing into the Agent Loop to enforce per-message / per-session USD caps. A per-run
cost accumulator reads each turn's `TurnEnd.usage` (`loop.py` turn cycle), converts to USD via the
host-supplied `PricingTable.cost`, and a small checker compares the running total to the caps;
when crossed, the loop terminates via the existing `emitter.run_terminated(reason,
turns_completed); return` pattern (next to the turn-budget guard at `loop.py:135-138` / after
`turns_completed += 1`), retaining the crossing turn's output. The terminate reason is a NEW
`budget-exceeded` member on the `TerminationReason` Literal (`events/envelope.py:194`) — additive,
no `SCHEMA_VERSION` bump, never reusing `cancelled`. Threaded additively: optional
`RuntimeConfig` caps (`per_message_usd` / `per_session_usd`, `Decimal | None`, default `None`) +
an optional `budget_checker` collaborator on `AgentLoop` (default `None`, the assembler/hooks/
summarizer pattern) + per-session spend on the controller's session state + a host-supplied
model-id string (the `ModelBoundary` exposes none). Default-off → byte-identical. Stop-after-
overage; unpriced model (`cost` None) → fail-soft (skip + diagnostic). **Phase C (durable
per-user-monthly ledger) is out of scope (deferred).**

## Technical Context

**Language/Version**: Python 3.11+; stdlib `decimal`.

**Primary Dependencies**: none new — reuses `loopplane.pricing.PricingTable.cost` (053),
`loopplane.model.TokenUsage`/`TurnEnd`, the loop's emitter + terminate pattern.

**Storage**: in-memory per-session spend on the controller session state (no persistence; resets
on resume — documented).

**Testing**: pytest, offline — a scripted model emitting `TokenUsage` + a `PricingTable`: a run
crossing a cap terminates `budget-exceeded` (output retained); under-cap completes; unpriced →
fail-soft (no terminate + diagnostic); default-off byte-identity; the new reason serializes/replays
with no `SCHEMA_VERSION` change; every `TerminationReason` consumer handles it.

**Target Platform**: cross-platform library.

**Constraints**: additive at signatures (optional caps + optional collaborator); default-off
byte-identical; the ONE event-vocabulary growth is additive within `SCHEMA_VERSION = 1` (no bump);
contained + public-safe (VII); no new dependency; ADR 0005. Phase C deferred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-008 + ADR 0005. ✅
- **III. Agent Harness Before Loop Automation**: An opt-in cost-safety primitive (default-off). ✅
- **IV. Runtime Boundary Clarity**: The new in-loop enforcement point is recorded in ADR 0005; the
  loop seam is an optional collaborator (default None). ✅
- **V. Tool Gateway Ownership**: N/A — no tool/execution path added. ✅
- **VI. Event Bus Ownership**: ONE additive `TerminationReason` member (`budget-exceeded`); no
  `SCHEMA_VERSION` bump; the runtime-events contract + a round-trip test are updated; consumers
  audited. No other event/content change. ✅ (ADR 0005)
- **X. Testable Evolution**: Additive; default-off byte-identical; reversible; offline-tested. ✅

**Result**: PASS — the two boundary crossings (in-loop enforcement + the additive `TerminationReason`)
are **maintainer-approved and recorded in ADR 0005**; no breaking 001/002 contract change, no
`SCHEMA_VERSION` bump. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/055-budget-caps/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/budget-enforcement.md
└── checklists/requirements.md
docs/adr/0005-usd-budget-enforcement.md   # the approved boundary decision
specs/011-* contracts/runtime-events.md   # MODIFIED: document the new budget-exceeded reason
```

### Source Code (repository root)

```text
src/loopplane/events/envelope.py        # MODIFIED: + "budget-exceeded" TerminationReason member
src/loopplane/loop/loop.py              # MODIFIED: optional budget_checker collaborator (default
                                        #   None); per-turn usage->USD accumulate (TurnEnd branch)
                                        #   + cap check + terminate("budget-exceeded") in the turn loop
src/loopplane/<budget checker>          # NEW (small): the accumulator/checker value object
                                        #   (a pure usage->USD running total + cap test); reuse pricing
src/loopplane/controller/controller.py  # MODIFIED: optional usd_caps + PricingTable + model-id ->
                                        #   build the budget_checker in _assemble; per-session spend on _Session
src/loopplane/host/config.py            # MODIFIED: RuntimeConfig.per_message_usd / per_session_usd
                                        #   (Decimal|None, default None) + from_mapping + validate_config
docs/api-reference.md                   # MODIFIED (if a new public name is exported)
tests/unit/test_budget_caps.py          # NEW: offline coverage
tests/contract/<events>                 # MODIFIED: the budget-exceeded round-trip + consumer audit
```

**Structure Decision**: The new reason is one Literal member (envelope.py). Enforcement is an
optional `budget_checker` collaborator on `AgentLoop` (the assembler/hooks/summarizer default-None
pattern), built in the controller's `_assemble` from optional `RuntimeConfig` caps + a host-supplied
`PricingTable` + model-id; per-session spend lives on `_Session`. Default-off → the new turn-loop
block is skipped → byte-identical. The checker is a small pure value object (running total + cap
test) reusing `loopplane.pricing.PricingTable.cost`. The `budget_checker` is threaded as an
optional param (no neutral-Protocol-in-context dance needed — it is constructed by the controller,
which already builds the loop; but it must NOT make the loop import `loopplane.tools`/pricing in a
way that trips the boundary audit — pricing is a foundational package, not the tools layer, so this
is safe; confirm at implement).

## Complexity Tracking

> No unjustified complexity. The two boundary crossings (in-loop enforcement + the additive
> `TerminationReason`) are justified by ADR 0005 (maintainer-approved) and gated default-off; no
> `SCHEMA_VERSION` bump, no breaking contract. Not a Constitution violation.
