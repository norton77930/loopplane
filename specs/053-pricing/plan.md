# Implementation Plan: Server-Side Pricing

**Branch**: `053-pricing` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/053-pricing/spec.md`

**Boundary review**: **ADDITIVE — no ADR, no contract change, no consult** (the additive half of
the Tier-3 design-workflow's 053 split; G22 caps are deferred). A standalone pure component;
nothing in the loop/controller/gateway is touched, so it is byte-identical when unused.

## Summary

Add a standalone `loopplane.pricing` module: `PricingRate` (a model's input + output per-token USD
rates, exact `Decimal`), `PricingTable` (an immutable host-supplied mapping `model id →
PricingRate`), and a **pure** cost computation `PricingTable.cost(usage: TokenUsage, model: str) ->
Decimal | None` = `input_tokens × input_rate + output_tokens × output_rate` (exact decimal; `None`
for an unknown model). Reuses `loopplane.model.TokenUsage`. The module ships **no prices** (host-
supplied), makes **no network call**, and is **not wired into the loop/controller** — it is pure
metadata a host/observability layer invokes on demand, so the runtime is byte-identical when
unused. **No enforcement / caps / termination cause** (G22 deferred). No new dependency (stdlib
`decimal`); no event-schema/content-model change; no ADR.

## Technical Context

**Language/Version**: Python 3.11+; stdlib `decimal` for exact money.

**Primary Dependencies**: none new — reuses `loopplane.model.TokenUsage`.

**Storage**: none (the table is an in-memory value object the host constructs).

**Testing**: pytest, offline — exact-decimal cost for priced models (incl. large counts +
fractional rates), unknown-model → `None`, zero usage/rates → `0`, immutability, and the
default-off byte-identity (the module is standalone; importing it changes nothing).

**Target Platform**: cross-platform library.

**Constraints**: additive / reuse-first; pure metadata (NO enforcement, NO loop/controller wiring);
default-off byte-identical; public-safe (model ids + numbers only, VII); exact `Decimal` (no float
drift); no new dependency; no event-schema/content-model change; no ADR.

**Scale/Scope**: one new small module (`src/loopplane/pricing.py`) + its `__all__` export + an
api-reference section + tests. The smallest Tier-3 unit; inline implement.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007. ✅
- **III. Agent Harness Before Loop Automation**: A passive cost-reporting primitive (no automation,
  no enforcement). ✅
- **IV. Runtime Boundary Clarity**: A standalone pure module; nothing in the loop/controller/gateway
  is touched. ✅
- **V. Tool Gateway Ownership**: N/A — pricing is not a tool; it adds no execution path. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change; no new
  `TerminationReason` (G22 deferred). ✅
- **X. Testable Evolution**: Additive; pure; byte-identical when unused; reversible; offline-tested. ✅

**Result**: PASS — purely additive standalone metadata; no boundary crossing, no enforcement, no
ADR. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/053-pricing/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/pricing.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/pricing.py            # NEW: PricingRate + PricingTable (+ cost) + __all__
docs/api-reference.md               # MODIFIED: a new `loopplane.pricing` section (unit-014 bijection)
tests/unit/test_pricing.py          # NEW: offline coverage
```

**Structure Decision**: A single new top-level module `loopplane/pricing.py` (the simplest fit —
no package needed) exporting `PricingRate` + `PricingTable` via `__all__`, documented in
`docs/api-reference.md` so the unit-014 api-reference bijection stays exact. It reuses
`loopplane.model.TokenUsage` and is imported by nobody in the runtime (a host/observability layer
calls `PricingTable.cost(...)` on demand) — so the loop/controller/gateway are untouched and the
default (no pricing) is byte-identical.

## Complexity Tracking

> No Constitution violations — section intentionally empty. The smallest, most contained Tier-3
> unit: one standalone pure module, no wiring, no enforcement, no ADR.
