# Feature Specification: Cost Surfacing

**Feature Branch**: `064-cost-surfacing`

**Created**: 2026-06-21

**Status**: Draft — P1 (review backlog batch 064–072, unit 1/9)

**Input**: User description: "P1 (053/062 tail): server-side cost SURFACING — read-only web/API endpoints exposing a run/session's accumulated USD + a principal's current-month USD spend, over the 055 BudgetChecker state + the 062 UsdLedger. Additive (new owner-scoped GET routes, 404 on non-owner; no loop/event/content change); no ADR. Closes 'pricing computes USD but nothing is queryable'."

## ⚠️ Boundary note (read first)

053 computes USD and 062 records durable per-`(principal, month)` spend, but **nothing exposes
it** — a host/UI can only observe the `budget-exceeded` termination, never the running cost. This
unit adds **read-only** surfacing: web/API GET endpoints for (a) a session's accumulated USD and (b)
a principal's current-month USD. **Additive** — new owner-scoped GET routes reusing the existing
auth/ownership pattern (`_require`/`_owned_or_404`); a small read accessor so the per-session
`BudgetChecker` spend is queryable; the controller's host-supplied `UsdLedger` read via `get`. **No
loop / event / content / schema change; no new `TerminationReason`; no ADR.** Default-off honest:
when no pricing/budget is configured a session reports cost as "not tracked"; when no `usd_ledger` is
configured the monthly endpoint reports "not tracked". The DSN + `principal_id` are never echoed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A host reads a session's accumulated USD (Priority: P1)

A host/UI queries the running USD cost of a session it owns, so it can show spend-so-far (not just
wait for a `budget-exceeded` stop).

**Why this priority**: This is the core value — the cost data already exists (055's per-session
accumulator) but is unreachable; surfacing it is the smallest high-value step.

**Independent Test** (offline, the in-process app + a budget-configured session): GET the session's
cost endpoint → returns the accumulated USD (Decimal, as a string) for the owner; a non-owner gets
404; a session with no budget configured reports cost "not tracked".

**Acceptance Scenarios**:

1. **Given** an owned session with budget tracking, **When** the owner GETs its cost, **Then** the
   response carries the session's accumulated USD (exact, string-encoded).
2. **Given** a session owned by another principal, **When** a non-owner GETs its cost, **Then** 404
   (no existence/cost leak), reusing the existing ownership pattern.
3. **Given** a session with no pricing/budget configured, **When** the owner GETs its cost, **Then**
   the response cleanly reports cost is not tracked (not an error/crash).

---

### User Story 2 - A principal reads its current-month USD spend (Priority: P1)

A principal queries its own current-month accumulated USD (the durable 062 ledger total), so a
host/UI can show monthly spend against a cap.

**Why this priority**: The durable monthly figure (062/063) is the budget users most want to see; it
already exists in the ledger but is host-internal/unrouted.

**Independent Test**: with a `usd_ledger` configured + a pre-seeded `(principal, month)` total, GET
the monthly-spend endpoint as that principal → the ledger total; with no ledger configured → "not
tracked".

**Acceptance Scenarios**:

1. **Given** a configured `usd_ledger` + a principal with recorded spend, **When** the principal GETs
   its monthly spend, **Then** the response carries that principal's current-month USD total (the
   caller's OWN principal only — never another's).
2. **Given** no `usd_ledger` configured, **When** a principal GETs its monthly spend, **Then** the
   response cleanly reports monthly spend is not tracked.

---

### Edge Cases

- **no budget/pricing**: the session-cost endpoint reports "not tracked" (default-off; no crash).
- **no `usd_ledger`**: the monthly-spend endpoint reports "not tracked".
- **non-owner / unknown session**: 404 (no existence or cost leak), reusing `_owned_or_404`.
- **month boundary**: monthly spend uses the same UTC `YYYY-MM` derivation as 063 (consistent).
- **public-safety**: the response carries only the principal's own id + a Decimal amount — never a
  DSN, secret, another principal's data, or an internal path.
- **exact money**: USD is exact `Decimal`, string-encoded in the response (never float).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add a read-only web/API endpoint returning a session's accumulated USD spend (the 055
  `BudgetChecker` per-session total), for the session OWNER only; a non-owner / unknown session → 404
  (reuse `_require`/`_owned_or_404`).
- **FR-002**: Add a read-only web/API endpoint returning the calling principal's current-month USD
  spend (`UsdLedger.get(principal_id, month)`), `month` = the UTC `YYYY-MM` derivation consistent
  with 063; a principal can read ONLY its own spend.
- **FR-003**: Provide the minimal read accessor needed so a session's accumulated USD is queryable
  after/between runs (e.g. retain or expose the per-session `BudgetChecker` spend). Additive; no loop
  / controller-run-path behaviour change.
- **FR-004**: **Default-off honest** — when no pricing/budget is configured, the session-cost
  endpoint reports cost "not tracked"; when no `usd_ledger` is configured, the monthly endpoint
  reports "not tracked". Never a crash; the rest of the runtime is byte-identical.
- **FR-005**: No loop / Event Bus / content-model / checkpoint change; no new `TerminationReason`; no
  `SCHEMA_VERSION` bump; no new dependency; no ADR. Read-only (no mutation of budget/ledger state).
- **FR-006**: Public-safe — responses carry only the caller's own `principal_id` + an exact `Decimal`
  USD (string-encoded); never a DSN, secret, another principal's data, or an internal path.

### Key Entities *(include if feature involves data)*

- **Session cost (read view)**: `{ session_id, usd_spent: Decimal-as-string | null (not tracked) }`.
- **Monthly spend (read view)**: `{ principal_id, month: "YYYY-MM", usd_spent: Decimal-as-string |
  null (not tracked) }`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner of a budget-tracked session can read its accumulated USD via a GET endpoint
  (exact, string-encoded); a non-owner gets 404 — 100% of covered cases.
- **SC-002**: A principal can read its own current-month USD spend from the ledger; never another
  principal's; no ledger → "not tracked".
- **SC-003**: Default-off byte-identical (no pricing/budget/ledger → endpoints report "not tracked",
  the rest unchanged); no `SCHEMA_VERSION` bump / new reason / new dependency; the four gates +
  structural audits + the existing webapi suite pass.

## Assumptions

- Reuses webapi's auth/ownership (`require` dependency, `_require`/`_owned_or_404`), 055's
  `BudgetChecker` per-session spend, 062's `UsdLedger.get`, and 063's UTC `YYYY-MM` month derivation.
- **Out of scope**: the `/cost` slash COMMAND surface (that is 065); historical/per-run cost
  breakdowns, cost streaming/push, billing/invoicing, cross-principal admin views, mutation of
  budget/ledger; a CLI cost view beyond what 065 adds.
- Additive; default-off byte-identical; read-only; public-safe; offline-testable. No ADR (additive
  webapi read surface within the established host/ownership boundary).
