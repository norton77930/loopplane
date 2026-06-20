# Feature Specification: Server-Side Pricing

**Feature Branch**: `053-pricing`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Server-side pricing (G21 Phase A only): a PricingTable mapping a model to its per-token USD rates + a pure function computing the USD cost of a TokenUsage record, host-injected and default-off / pure-metadata. Unit 053, Tier-3 (cost). Additive, no ADR. DO NOT implement USD budget caps / enforcement (G22 Phase B/C) — deferred."

## ⚠️ Scope note (read first)

This is **G21 Phase A — pricing as pure metadata only**. It computes a USD cost from a
token-usage record; it does **NOT** enforce anything. **G22 USD budget caps / enforcement (per
message / session / user-monthly) are explicitly DEFERRED** — they cross the Agent Loop boundary
(reading usage mid-run), add a new `budget-exceeded` termination cause (an Event Bus schema
change, Constitution VI), and need a durable ledger, each requiring a later ADR. If anything in
planning drifts toward caps/enforcement/a new termination reason, STOP and consult the maintainer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compute the USD cost of token usage (Priority: P1)

A host (or an observability/reporting layer) computes the **USD cost** of a turn's or run's token
usage from a host-supplied price list — so cost can be surfaced (e.g. a `/cost`-style view) without
the runtime hard-coding any prices.

**Why this priority**: This is gap G21 (Phase A) and the unit's value — LoopPlane has token-usage
accounting (`TokenUsage`) but no money. A pure usage→USD function unlocks cost reporting.

**Independent Test**: given a `PricingTable` with a model's input/output per-token rates and a
`TokenUsage` (input/output token counts), the cost function returns the exact USD amount
(`input_tokens × input_rate + output_tokens × output_rate`) as an exact decimal.

**Acceptance Scenarios**:

1. **Given** a `PricingTable` with rates for model M, **When** the cost of a `TokenUsage` for M is
   computed, **Then** it equals `input × input_rate + output × output_rate` exactly (decimal money,
   no float drift).
2. **Given** a `PricingTable` with no entry for model M, **When** a cost for M is requested, **Then**
   the result is a clear "unknown/None" (no guessed price, no crash).

---

### User Story 2 - Pricing is host-injected, default-off, pure metadata (Priority: P2)

The pricing table is **host-supplied** (no bundled price feed, no network); with no pricing
configured the runtime behaves exactly as today (pricing is purely additive metadata, computed on
demand — it changes no run behavior).

**Why this priority**: Prices change + vary per host/contract; the runtime must not ship or fetch
prices, and must not alter any execution path. This keeps it offline, public-safe, and byte-
identical when unused.

**Independent Test**: with no pricing configured, the existing run/loop behavior is unchanged
(pricing is a separate pure component); a host-constructed `PricingTable` is used only when the
host asks for a cost.

**Acceptance Scenarios**:

1. **Given** no pricing configured, **When** a run executes, **Then** behavior is byte-identical to
   today (pricing computes nothing unless explicitly invoked).
2. **Given** a host-supplied `PricingTable`, **When** the host computes a cost, **Then** it uses the
   host's rates (no bundled/default prices).

---

### Edge Cases

- **unknown model**: cost is `None` (or a clear "no price for <model>"), never a guessed value.
- **zero usage / zero rates**: cost is `0` (exact).
- **very large token counts / fractional per-token rates**: exact decimal arithmetic (no float
  rounding error); rates are per-token (or per-million, fixed in planning) with a documented unit.
- **pricing not configured**: no cost computed; no behavior change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `PricingTable` value object mapping a model identifier to
  its per-token USD rates (input + output), constructed from **host-supplied** data (no bundled
  prices, no network).
- **FR-002**: The system MUST provide a **pure** function that computes the USD cost of a
  `TokenUsage` record under a `PricingTable`, using **exact decimal** arithmetic (no float money
  drift): `cost = input_tokens × input_rate + output_tokens × output_rate`.
- **FR-003**: An **unknown model** (no table entry) MUST yield a clear "no price" result (`None`),
  never a guessed/zero-masked price and never a crash.
- **FR-004**: Pricing MUST be **pure metadata** — it MUST NOT enforce anything, MUST NOT alter any
  run/loop/turn behavior, and MUST NOT introduce a budget cap, a termination cause, or any Event
  Bus / content-model change. (G22 caps are out of scope / deferred.)
- **FR-005**: Pricing MUST be **default-off / additive**: with no pricing configured the runtime is
  byte-identical to today; the `PricingTable` + cost function are a standalone component a host
  invokes on demand.
- **FR-006**: Pricing data + computed costs MUST be **public-safe** (VII): the table carries only
  model ids + numeric rates (no secrets); the cost is a number.
- **FR-007**: The capability MUST reuse `loopplane.model.TokenUsage`; it MUST add no new runtime
  dependency (stdlib `decimal`); no ADR.

### Key Entities *(include if feature involves data)*

- **PricingRate**: a model's input + output per-token USD rates (exact decimals).
- **PricingTable**: a host-supplied mapping `model id → PricingRate`; immutable value object.
- **Cost function**: a pure `(TokenUsage, model, PricingTable) -> USD Decimal | None`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a priced model, the computed USD cost equals `input × input_rate + output ×
  output_rate` exactly (decimal) in 100% of covered scenarios, including large counts + fractional
  rates (no float drift).
- **SC-002**: An unknown model yields a clear "no price" (`None`); zero usage/rates yield exact `0`.
- **SC-003**: With no pricing configured, the runtime is byte-identical to today — the existing test
  suite passes unchanged; no event-schema / content-model change is introduced.
- **SC-004**: No bundled prices, no network, no new runtime dependency; pricing is pure metadata
  (no enforcement).

## Assumptions

- Pricing lives in a small standalone component (e.g. `loopplane.pricing` or a value object beside
  the governance/cost code) reusing `loopplane.model.TokenUsage`; it is **not** wired into the
  loop/controller (no enforcement) — a host/observability layer calls the cost function on demand.
- Rates are **host-supplied**; the unit ships **no** prices. The rate unit (per-token vs
  per-million-tokens) is fixed in planning with a documented convention; arithmetic is `decimal`.
- **Out of scope / DEFERRED (G22, needs a later ADR)**: USD budget caps + enforcement (per message
  / session / user-monthly), a `budget-exceeded` termination reason, a durable usage/cost ledger,
  and any mid-run cost gating.
- Default-off; pure metadata; public-safe (VII); reuse-first (X); no ADR. Per Constitution IX the
  concept is borrowed from the reference harnesses but re-derived.
