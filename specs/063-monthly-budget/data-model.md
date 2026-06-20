# Data Model: Per-User-Monthly USD Cap

Additive; extends 055's `BudgetChecker`. No event/content change (reuses `budget-exceeded`). Per
[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md).

## BudgetChecker (modified — additive optional monthly dimension)

| Field (new, optional) | Type | Notes |
| --------------------- | ---- | ----- |
| `ledger` | `UsdLedger \| None = None` | the 062 durable store; None → no monthly enforcement. |
| `principal_id` | `str \| None = None` | the run's principal (from the controller). |
| `clock` | `Callable[[], datetime]` (default `lambda: datetime.now(UTC)`) | derives the `YYYY-MM` month. |
| `per_user_monthly_usd` | `Decimal \| None = None` | the monthly cap (None → off). |
| `_monthly_total` (internal) | `Decimal` | the latest ledger-returned monthly total. |

| Method | Change |
| ------ | ------ |
| `record_turn(usage) -> Decimal \| None` | now **async**: after computing the (priced) cost, if the monthly dim is set, `await ledger.add(principal_id, month, cost)` → set `_monthly_total` (FAIL-OPEN: on an exception, a diagnostic flag + skip — no accumulation, no raise). Returns the turn cost (or None unpriced) as before. |
| `exceeded() -> bool` | + a monthly arm: `per_user_monthly_usd is not None and _monthly_total > per_user_monthly_usd`. |

## RuntimeConfig / controller (modified — additive)

| Surface | Type | Notes |
| ------- | ---- | ----- |
| `RuntimeConfig.per_user_monthly_usd` | `Decimal \| None = None` | the monthly cap (from_mapping + validate non-negative). |
| host-supplied `usd_ledger` | `UsdLedger \| None` | forwarded by assembly → `RuntimeController`. |
| `RuntimeController(usd_ledger=…, per_user_monthly_usd=…)` | ctor kwargs | `_assemble` builds the monthly dim with `principal_id` on create AND resume. |

## Rules (from FRs + ADR 0010)

| Rule | Source |
| ---- | ------ |
| BudgetChecker + optional (ledger, principal_id, clock, per_user_monthly_usd) | FR-001, D1 |
| record_turn async → await ledger.add → fold into exceeded(); loop awaits; reuse budget-exceeded (no schema bump) | FR-002, D2 |
| FAIL-OPEN on a ledger exception (allow + diagnostic, never crash/deny) | FR-003, D3 |
| default-off byte-identical (no monthly dim → 055 path; record_turn awaits nothing) | FR-004, D5 |
| principal_id threaded on create AND resume (close the gap) | FR-005, D4 |
| controller wiring (usd_ledger + RuntimeConfig.per_user_monthly_usd); foundational imports only | FR-006 |
| DSN + principal_id public-safe (never echoed) | FR-007 |
