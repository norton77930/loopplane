# Quickstart / Validation: Per-User-Monthly USD Cap

See [contracts/monthly-budget.md](contracts/monthly-budget.md), [data-model.md](data-model.md), and
[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md). Extends 055's BudgetChecker with a
durable per-user-monthly cap (062's UsdLedger); additive, default-off, reuses `budget-exceeded`.

## Run the budget tests

```powershell
pytest tests/ -k "budget or monthly or ledger" -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; with no monthly dim the 055 behavior + events are byte-identical (the existing
budget tests pass, now awaiting `record_turn`); SCHEMA_VERSION unchanged.

## Validation scenarios (mirror the acceptance scenarios)

1. **Monthly cap crossed → terminate** — a `per_user_monthly_usd` cap + a `UsdLedger` pre-seeded near
   the cap; a run whose turn crosses the monthly total terminates `budget-exceeded` (after the
   crossing turn, output retained). (FR-001/002, SC-001)
2. **Durable accrual** — each turn's cost is added to `(principal_id, month)` via `await ledger.add`.
   (FR-002)
3. **Default-off byte-identity** — no monthly dim → 055 events/behavior byte-identical (existing
   budget tests pass). (FR-004, SC-002)
4. **Fail-open** — a ledger that raises on `add` → the run is NOT terminated (a public-safe
   diagnostic); never crash/deny. (FR-003, SC-002)
5. **Resume enforces** — a resumed session + a monthly cap → enforces `budget-exceeded` (principal_id
   threaded on resume). (FR-005, SC-001)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway` — controller/loop must not
import the tools layer; `test_public_safety`) + the events serialize/`SCHEMA_VERSION` tests (unchanged
— reuses `budget-exceeded`, no new reason). NOTE: run the full pytest + any verify Workflow at
DIFFERENT times (the real-subprocess MCP tests flake under CPU load); scan new test files for
forbidden tokens before committing.
