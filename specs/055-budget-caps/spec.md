# Feature Specification: USD Budget Caps (In-Loop Enforcement)

**Feature Branch**: `055-budget-caps`

**Created**: 2026-06-20

**Status**: Draft — **plan authors the maintainer-approved [ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md)**

**Input**: User description: "G22 Phase B (on top of 053 pricing): multi-level USD budget caps with in-loop enforcement — accumulate per-turn USD cost (from TokenUsage × the pricing table) and terminate a run when a per-message or per-session USD cap is exceeded. Unit 055, Tier-3 cost. Additive + default-off; the one non-additive piece is a new `budget-exceeded` TerminationReason (Event Bus vocabulary, VI — additive within SCHEMA_VERSION=1, no bump; maintainer-approved). Phase C (durable per-user-monthly ledger) is DEFERRED."

## ⚠️ Boundary note (read first)

053 shipped pricing (`loopplane.pricing.PricingTable.cost`) as pure metadata, deliberately
**unwired**. This unit WIRES cost into the **Agent Loop turn cycle** to enforce USD caps — because
USD is computed from `TokenUsage`, which only exists post-turn on `TurnEnd.usage` (the decide-stage
governance decider never sees usage). That crosses two Constitution-protected boundaries: the Agent
Loop (IV) and the **Event Bus vocabulary** (VI — a new `budget-exceeded` `TerminationReason`). Both
are recorded in the **maintainer-approved [ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md)**
(authored at the plan step). Everything else is additive + default-off (byte-identical when no caps
are set). The per-user-monthly durable ledger (Phase C) is **out of scope / deferred**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run stops when it exceeds its USD budget (Priority: P1)

A host configures a per-message and/or per-session USD cap; when a run's accumulated cost (token
usage × the host's pricing) crosses the cap, the run **terminates** with a clear `budget-exceeded`
reason — so spend is bounded without the host watching token counts.

**Why this priority**: This is gap G22 (Phase B) and the unit's value — 053 made cost computable
but enforced nothing; a USD cap is what actually protects a budget.

**Independent Test**: with a per-message USD cap + a pricing table + a scripted model emitting
token usage, a run whose cumulative cost crosses the cap terminates with `budget-exceeded`; under
the cap it completes normally.

**Acceptance Scenarios**:

1. **Given** a per-message USD cap + pricing, **When** the accumulated turn cost crosses the cap,
   **Then** the run terminates with the `budget-exceeded` reason (after the turn that crossed it),
   keeping that turn's output (never orphaned).
2. **Given** a per-session USD cap, **When** the running total across the session's runs crosses
   it, **Then** the next run terminates `budget-exceeded`; under the cap, runs complete.

---

### User Story 2 - Default-off, byte-identical; fail-soft on unpriced models (Priority: P2)

With no caps configured the runtime behaves **exactly as today** (no cost accounting, no new
behavior). When a cap IS set but the model has no price in the table, enforcement is **fail-soft**
(the cap is not enforced for that turn + a diagnostic is emitted) — never a crash, never a guessed
price.

**Why this priority**: The change must impose nothing on hosts that don't opt in (053's invariant),
and must degrade safely when pricing is incomplete (053's fail-soft stance).

**Independent Test**: no caps → behavior + events byte-identical to pre-055; a cap set + an unpriced
model → the run is NOT terminated (a warning diagnostic is emitted), it completes.

**Acceptance Scenarios**:

1. **Given** no USD caps configured, **When** runs execute, **Then** behavior + the event stream
   are byte-identical to today (no accounting, no new events).
2. **Given** a cap + an unpriced model, **When** a run executes, **Then** it is not terminated for
   budget (a diagnostic notes the unpriced model); enforcement is skipped, not failed.

---

### User Story 3 - Honest, bounded, contained semantics (Priority: P3)

The cap terminates **after** the turn that crossed it (USD is only knowable post-turn; total spend
is bounded to roughly cap + one turn — it cannot pre-empt a single expensive turn). The
`budget-exceeded` reason is a distinct, additive `TerminationReason` (never a reused `cancelled`,
which would strand the user's input). All termination flows through the existing terminate path
(no orphaned output, contained, public-safe).

**Why this priority**: Over-promising (pre-emption) or mislabelling the stop (reusing `cancelled`)
would be incorrect/harmful; the semantics must be explicit + the event contract honest.

**Independent Test**: the terminating turn's output is retained; the reason is `budget-exceeded`
(not `cancelled`); existing event-schema tests still pass (the Literal grew, no SCHEMA_VERSION
bump) and every `TerminationReason` consumer handles the new value.

**Acceptance Scenarios**:

1. **Given** a budget stop, **When** the run terminates, **Then** the reason is `budget-exceeded`
   and the crossing turn's assistant output is kept in history (not orphaned).
2. **Given** the new reason, **When** events are serialized/replayed, **Then** the schema tests
   pass with no `SCHEMA_VERSION` bump and consumers (CLI render, checkpoint rebuild, web/API) do
   not mishandle it.

---

### Edge Cases

- **unpriced model + a cap**: fail-soft (warn diagnostic, no enforcement), not a crash.
- **no caps / cap = None**: byte-identical to today (no accounting).
- **a single turn far over the cap**: terminates after that turn (cannot pre-empt mid-turn).
- **resumed session**: the per-session USD counter resets on resume (simplest; documented) — the
  records do not currently reconstruct accumulated USD.
- **reused-reason hazard**: MUST NOT reuse `cancelled` (it triggers checkpoint rebuild's
  input-stranding cleanup → would silently drop the user's input).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accumulate a run's USD cost from each turn's `TokenUsage` × a
  host-supplied pricing table (reuse `loopplane.pricing.PricingTable.cost`), inside the Agent Loop
  turn cycle (where `TurnEnd.usage` is available).
- **FR-002**: The system MUST support configurable **per-message** and **per-session** USD caps;
  when the accumulated cost crosses a cap, the run MUST terminate with a `budget-exceeded` reason
  (after the turn that crossed it, retaining that turn's output).
- **FR-003**: A new `budget-exceeded` member MUST be added to the `TerminationReason` vocabulary —
  additive within the current schema version (**no `SCHEMA_VERSION` bump**); it MUST NOT reuse an
  existing reason (especially not `cancelled`).
- **FR-004**: The feature MUST be **opt-in and default-off** (byte-identical when no caps are
  configured): no cost accounting, no new behavior, no new events when unset.
- **FR-005**: Enforcement MUST be **fail-soft** when a model has no price (`cost` returns `None`):
  the cap is not enforced for that turn and a diagnostic is emitted — never a crash, never a guess.
- **FR-006**: Termination MUST flow through the existing terminate path (contained, public-safe, no
  orphaned output); the per-session counter resets on resume (documented).
- **FR-007**: The capability MUST be **additive at signatures** — optional `RuntimeConfig` caps +
  an optional checker collaborator on the Agent Loop + per-session spend on the session state (the
  established default-off-collaborator pattern); no breaking change to loop/controller signatures.
- **FR-008**: The mechanism MUST be recorded in **ADR 0005** (maintainer-approved), authored at
  the plan step. **G22 Phase C (durable per-user-monthly ledger) is DEFERRED** (a later unit + ADR).

### Key Entities *(include if feature involves data)*

- **UsdBudgetCaps**: a value object (per-message USD, per-session USD — `Decimal | None` each,
  default None) on `RuntimeConfig`.
- **Budget checker / accumulator**: the in-loop collaborator that, per turn, adds the turn's USD
  cost to the running total and signals when a cap is crossed.
- **`budget-exceeded` TerminationReason**: the new, additive run-termination reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With caps + pricing, a run crossing the cap terminates with `budget-exceeded` (after
  the crossing turn, output retained), and an under-cap run completes — in 100% of covered
  scenarios.
- **SC-002**: With no caps, behavior + the event stream are byte-identical to today (the existing
  suite passes unchanged); a cap + unpriced model is fail-soft (no termination, a diagnostic).
- **SC-003**: The `budget-exceeded` reason serializes/replays with **no `SCHEMA_VERSION` bump`**;
  every `TerminationReason` consumer (CLI render, checkpoint rebuild, web/API, apps/web) handles it.
- **SC-004**: No new runtime dependency; Phase C remains deferred; ADR 0005 records the model.

## Assumptions

- Reuses 053's `loopplane.pricing.PricingTable.cost` (the hard parent dependency) for usage→USD;
  reuses the existing turn-budget guard pattern + the terminate path in the Agent Loop. The host
  supplies the `PricingTable` + the model-id string (the `ModelBoundary` exposes no model id).
- Caps live on `RuntimeConfig` (the default-off `Decimal | None` pattern); per-session spend lives
  on the controller's session state; the Agent Loop gets an optional checker collaborator (default
  None → byte-identical). Exact `Decimal` money throughout.
- **Out of scope / DEFERRED**: G22 Phase C (a durable per-user-monthly USD ledger with atomic
  cross-session increments — multi-tenant-shaped, sequenced with Tier-4 G19/G20); pre-turn cost
  estimation / mid-turn pre-emption (would need a token estimator + blur the model boundary, IV).
- Default-off; contained; public-safe (VII); reuse-first (X). Per Constitution IX the concept is
  borrowed from the reference harnesses but re-derived.
