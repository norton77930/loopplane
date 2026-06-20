# Contract: Per-User-Monthly USD Cap

Extends 055's in-loop budget enforcement with a durable per-user-monthly cap backed by 062's
`UsdLedger`. Per [ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md). Default-off
byte-identical; reuses the existing `budget-exceeded` reason (no schema bump).

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `BudgetChecker` monthly dim | optional `ledger` + `principal_id` + `clock` + `per_user_monthly_usd` | NEW (additive, optional). |
| `BudgetChecker.record_turn` | `async` | sync→async (ADR 0010 D6); the loop awaits it. |
| `RuntimeConfig.per_user_monthly_usd` | `Decimal \| None = None` | the monthly cap (off by default). |
| host-supplied `usd_ledger` | `UsdLedger \| None` | the durable store. |

## Behavior

| Case | Result |
| ---- | ------ |
| No monthly dim (default) | Byte-identical to 055: `record_turn` adds no ledger await; behavior + events unchanged. |
| Monthly cap + ledger; principal's monthly total crosses the cap | The run terminates `budget-exceeded` after the crossing turn (output retained); the existing reason. |
| Each turn (priced) | The cost is added durably to `(principal_id, month)` via `await ledger.add` (atomic) and folded into the cap check. |
| Ledger outage / `add` raises | **Fail-open**: allow the turn + a public-safe diagnostic; never crash, never deny. |
| Resumed session + a monthly cap | Enforces (the `principal_id` is threaded on resume — the gap closed). |
| Unpriced model | The turn cost is `None` → nothing added to the ledger (055's fail-soft). |
| Concurrent same-principal runs (061) | Each reads the same pre-run total; worst-case overage ≈ cap + N turns (the atomic add keeps the ledger exact) — accepted. |

## Invariants

- Default-off (`per_user_monthly_usd` None AND no `usd_ledger`) is byte-identical to 055 at runtime
  (no ledger await; same events). The `record_turn` sync→async is an approved ADR 0010 signature
  change (the loop + the 055 tests await it).
- The monthly cap reuses the SAME enforcement point + the EXISTING `budget-exceeded`
  `TerminationReason` + stop-after-overage — NO new reason, NO `SCHEMA_VERSION`/content change.
- FAIL-OPEN on a ledger outage (allow + diagnostic, never crash/deny). The cap enforces on create AND
  resume (`principal_id` threaded; the resume gap closed).
- Additive; the controller/loop import only `loopplane.budget`/`loopplane.ledger` (foundational) —
  the no-execution-outside-the-gateway audit stays green. Public-safe (DSN + principal_id never
  echoed).
- Out of scope (deferred): write-ahead pending-charge; distributed ledgers; the concurrency overage
  bound (accepted).
