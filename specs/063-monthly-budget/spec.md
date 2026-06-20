# Feature Specification: Per-User-Monthly USD Cap

**Feature Branch**: `063-monthly-budget`

**Created**: 2026-06-21

**Status**: Draft — per **ADR 0010** (authored at 062; all forks settled; no consult)

**Input**: User description: "G22 Phase C (2/2, the LAST unit): per-user-monthly USD cap enforcement. Extend 055's BudgetChecker with an optional monthly dimension backed by the 062 durable UsdLedger — a `per_user_monthly_usd` cap; `record_turn` becomes async (`await ledger.add(...)` → fold the returned monthly total into `exceeded()`); reuse the existing `budget-exceeded` reason (no new reason / SCHEMA bump); FAIL-OPEN on a ledger outage; thread principal_id into the BudgetChecker on create AND resume; default-off byte-identical."

## ⚠️ Boundary note (read first)

This is the **enforcement half** of G22 Phase C — it wires the 062 durable `UsdLedger` into 055's
in-loop budget enforcement to add a per-user-monthly USD cap. Per **ADR 0010**: extend 055's
`BudgetChecker` with an OPTIONAL monthly dimension (a `UsdLedger` + `principal_id` + a `YYYY-MM`
month from an injectable clock + a `per_user_monthly_usd` cap). `record_turn` becomes **async** (it
`await ledger.add(...)`) — this ripples to the loop's `record_turn` call site + the 055 tests (now
awaited). The monthly check rides the SAME in-loop enforcement point + the SAME existing
`budget-exceeded` `TerminationReason` + stop-after-overage — **no new reason, no `SCHEMA_VERSION`
bump**. **FAIL-OPEN** on a ledger outage (allow + diagnostic). **Default-off byte-identical** (no
ledger + no monthly cap → the 055 path is unchanged; `record_turn` awaits nothing new). `principal_id`
is threaded on create AND resume (closing a fail-open gap). **All forks settled at design — no
consult.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run stops when a principal crosses its monthly USD cap (Priority: P1)

A host configures a per-user-monthly USD cap + a durable `UsdLedger`; when a principal's accumulated
monthly cost (across sessions/runs) crosses the cap, the run terminates with `budget-exceeded` — the
durable, cross-session counterpart of 055's per-message/session caps.

**Why this priority**: This completes G22 — a monthly budget that survives across sessions (055's
in-memory per-session counter cannot); the durable ledger (062) makes it possible.

**Independent Test** (offline, the ledger + a scripted model): with a `per_user_monthly_usd` cap + a
ledger pre-seeded near the cap for a principal, a run whose turn cost crosses the monthly total
terminates `budget-exceeded` (after the crossing turn, output retained); under the cap it completes.

**Acceptance Scenarios**:

1. **Given** a monthly cap + a ledger, **When** a principal's monthly total crosses the cap, **Then**
   the run terminates `budget-exceeded` (after the crossing turn; the existing reason).
2. **Given** the cap, **When** each turn runs, **Then** its cost is added to the principal's
   `(principal_id, month)` ledger total (durably, atomically) and folded into the cap check.

---

### User Story 2 - Default-off byte-identical; fail-open on a ledger outage (Priority: P1)

With no monthly cap + no ledger configured, behavior is exactly 055 (byte-identical). When a cap IS
configured but the ledger is unreachable, enforcement is **fail-open** (allow the turn + a public-safe
diagnostic) — never a crash, never a wrongful denial.

**Why this priority**: The change must impose nothing on existing deployments, and a ledger outage
must degrade to availability (cost-safety yields to not breaking the run), per the maintainer fork.

**Independent Test**: no monthly dim → the 055 events/behavior byte-identical; a ledger that raises
on `add` → the run is NOT terminated for budget (a warning diagnostic), it completes.

**Acceptance Scenarios**:

1. **Given** no `usd_ledger` + no `per_user_monthly_usd`, **When** runs execute, **Then** behavior +
   events are byte-identical to 055 (`record_turn` awaits nothing new).
2. **Given** a monthly cap + a failing ledger, **When** a run executes, **Then** it is NOT terminated
   (a public-safe diagnostic notes the ledger outage); fail-open, never crash/deny.

---

### User Story 3 - Monthly caps enforce on resumed sessions (Priority: P2)

A principal's monthly cap is enforced on a RESUMED session, not just a freshly-created one — the
`principal_id` is threaded into the `BudgetChecker` on both create and resume (closing a gap where
resume omitted it).

**Why this priority**: Without threading `principal_id` on resume, a resumed session would silently
skip the monthly cap (a fail-open gap) — a correctness hole the unit closes + tests.

**Independent Test**: a resumed session with a monthly cap + a principal near the cap → the run still
enforces `budget-exceeded` (the `BudgetChecker` got `principal_id` on resume).

**Acceptance Scenarios**:

1. **Given** a resumed session + a monthly cap, **When** the principal crosses the monthly total,
   **Then** the run terminates `budget-exceeded` (the cap enforces on resume, not just create).

---

### Edge Cases

- **no monthly dim (default)**: byte-identical to 055; `record_turn` adds no ledger await.
- **ledger outage / `add` raises**: fail-open — allow + a public-safe diagnostic; never crash/deny.
- **stop-after-overage**: the cap terminates after the turn that crossed it (USD knowable post-turn).
- **concurrent same-principal runs (061)**: each reads the same pre-run monthly total; worst-case
  overage ≈ cap + N turns (the atomic ledger add keeps the total exact) — accepted (ADR 0010 D12).
- **resume**: `principal_id` threaded → the cap enforces (not skipped).
- **unpriced model**: the per-turn cost is `None` → nothing added to the ledger (055's fail-soft).
- **month boundary**: a turn after a UTC month boundary counts to the new month (injectable clock).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Extend `BudgetChecker` with an OPTIONAL monthly dimension — a `UsdLedger` +
  `principal_id` + a `YYYY-MM` month (from an injectable clock, default `datetime.now(UTC)`) + a
  `per_user_monthly_usd: Decimal | None` cap.
- **FR-002**: `record_turn` becomes **async**: when the monthly dimension is configured + the turn has
  a price, `await ledger.add(principal_id, month, cost)` and fold the returned monthly total into
  `exceeded()`; the loop's `record_turn` call site is awaited. The monthly cap terminates with the
  EXISTING `budget-exceeded` `TerminationReason` after the crossing turn (no new reason, no
  `SCHEMA_VERSION` bump).
- **FR-003**: **FAIL-OPEN** — a ledger `add`/read exception → allow the turn + emit a public-safe
  diagnostic (mirroring 055's unpriced-model fail-soft); never crash, never deny.
- **FR-004**: **Default-off byte-identical** — with no `usd_ledger` AND no `per_user_monthly_usd`
  configured, behavior + events are exactly 055 (`record_turn` awaits nothing new; no ledger built).
- **FR-005**: Thread `principal_id` into the `BudgetChecker` on BOTH create AND resume (close the
  resume gap where `principal_id` was omitted) — so monthly caps enforce on resumed sessions.
- **FR-006**: Wire via the controller `_assemble` building the per-session `BudgetChecker` with a
  host-supplied `UsdLedger` + a new `RuntimeConfig.per_user_monthly_usd` (default `None`) +
  `principal_id`. Additive; the controller/loop import `loopplane.ledger`/`loopplane.budget` only
  (foundational), never the tools layer (the boundary audit stays green).
- **FR-007**: Public-safe — the DSN + `principal_id` are never echoed in output/errors/logs. Per
  ADR 0010 (all forks settled).

### Key Entities *(include if feature involves data)*

- **BudgetChecker (extended)**: + an optional `(ledger, principal_id, clock, per_user_monthly_usd)`
  monthly dimension; `record_turn` async; `exceeded()` folds the monthly total.
- **RuntimeConfig.per_user_monthly_usd**: `Decimal | None = None` (the monthly cap; off by default).
- **UsdLedger**: the 062 durable store (host-supplied), keyed by `(principal_id, month)`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a monthly cap + a ledger, a principal crossing the monthly total terminates the run
  `budget-exceeded` (after the crossing turn, output retained); each turn's cost is durably added to
  the ledger — 100% of covered scenarios; enforced on create AND resume.
- **SC-002**: With no monthly dim, behavior + events are byte-identical to 055 (the existing suite
  passes); a ledger outage is fail-open (no termination, a diagnostic); the DSN/principal_id never
  echoed.
- **SC-003**: No new `TerminationReason`, no `SCHEMA_VERSION` bump; the controller/loop import
  boundary stays clean; the four gates + the new tests pass.

## Assumptions

- Reuses 055's `BudgetChecker` + the in-loop enforcement point + the `budget-exceeded` reason +
  stop-after-overage (ADR 0005); 062's `UsdLedger` (the durable atomic per-`(principal,month)` add);
  the controller's already-plumbed `principal_id` (one missing hop on resume, closed); the
  optional-collaborator + default-off + controller-builds-per-session wiring.
- **Out of scope / DEFERRED (ADR 0010)**: a durable write-ahead pending-charge (best-effort run-end
  accrual is accepted — a crash mid-run loses that turn's increment, mirroring 055's
  resume-loses-accumulation honesty); distributed ledgers; the cap+N-turns overage bound under
  concurrent same-principal runs is accepted (atomic add keeps the ledger exact; only the read is
  stale).
- Additive; default-off byte-identical; offline-testable; public-safe. Per ADR 0010 (all forks
  settled at design — no consult). Per Constitution IX the concept is borrowed but re-derived.
