# Research: Per-User-Monthly USD Cap

Settled by **[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md)** (authored at 062; all
forks settled). No open `NEEDS CLARIFICATION`.

## Decision 1 — Extend 055's BudgetChecker (ADR 0010 D5/D6)

**Decision**: Add an OPTIONAL monthly dimension to `BudgetChecker` (`budget/__init__.py`): a
`UsdLedger` + `principal_id` + a `YYYY-MM` month (injectable clock) + `per_user_monthly_usd`.
`record_turn` becomes async: `await ledger.add(principal_id, month, cost)` → fold the returned
monthly total into `exceeded()`. Reuses the SAME in-loop enforcement point + the EXISTING
`budget-exceeded` reason + stop-after-overage.

**Rationale**: The monthly cap is the durable cross-session counterpart of 055's per-session total;
extending the single checker keeps one enforcement point (the maintainer's chosen seam).

**Alternatives considered**: a separate `MonthlyBudgetGuard` collaborator (rejected by the maintainer
— a second collaborator + a second turn-loop block; extend-BudgetChecker is the smaller surface).

## Decision 2 — record_turn async; the loop awaits (ADR 0010 D6)

**Decision**: `record_turn` is `async`; `loop.py:328-329` becomes `(await
self._budget_checker.record_turn(increment.usage)) is None`. The 055 tests that call `record_turn`
are updated to `await`. RUNTIME default-off is byte-identical (no monthly dim → no ledger await →
same events).

**Rationale**: `ledger.add` is async (it commits durably). An approved signature change (ADR 0010
D6); the loop is already at an await point.

## Decision 3 — FAIL-OPEN on a ledger outage (ADR 0010 D9)

**Decision**: A `ledger.add` exception → catch it, emit a public-safe diagnostic, and allow the turn
(no monthly accumulation, no termination) — never crash, never deny. Mirrors 055's unpriced-model
fail-soft.

**Rationale**: Maintainer-chosen — availability over cost-safety; a ledger outage must not become a
service outage.

## Decision 4 — principal_id on create AND resume (ADR 0010 D8)

**Decision**: The controller `_assemble` builds the monthly dim with `principal_id`; resume passes
the persisted `principal_id` (read from the checkpoint) so the cap enforces on resumed sessions —
closing the gap where resume omitted it.

**Rationale**: Without it, a resumed session would silently skip the monthly cap (a fail-open hole) —
a correctness fix, tested.

## Decision 5 — Default-off + config wiring (ADR 0010 D10)

**Decision**: `RuntimeConfig.per_user_monthly_usd` (`Decimal | None`, default None) + a host-supplied
`usd_ledger`; `_assemble` builds the monthly dim only when both are present. No monthly dim → the 055
path unchanged (byte-identical).

**Rationale**: Impose nothing on existing deployments; reuse the optional-collaborator pattern.

## Out of scope (ADR 0010)

A durable write-ahead pending-charge (best-effort run-end accrual accepted); distributed ledgers; the
cap+N-turns overage bound under concurrent same-principal runs (accepted — atomic add keeps the
ledger exact).
