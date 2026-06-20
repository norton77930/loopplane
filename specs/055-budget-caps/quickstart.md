# Quickstart / Validation: USD Budget Caps

See [contracts/budget-enforcement.md](contracts/budget-enforcement.md),
[data-model.md](data-model.md), and [ADR 0005](../../docs/adr/0005-usd-budget-enforcement.md).
Wires 053's pricing into the Agent Loop to enforce USD caps; additive + default-off; the one
event-vocabulary growth (`budget-exceeded`) is additive within `SCHEMA_VERSION = 1` (no bump).

## Run the unit tests

```powershell
pytest tests/unit/test_budget_caps.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the new budget tests + the existing event-schema tests pass unchanged (the Literal
grew, no `SCHEMA_VERSION` bump). With no caps (default), behavior + the event stream are
byte-identical.

## Validation scenarios (mirror the acceptance scenarios)

1. **Cap crossed → terminate** — a per-message USD cap + a `PricingTable` + a scripted model
   emitting usage; the run terminates `budget-exceeded` after the crossing turn, that turn's output
   retained. (FR-001/002, SC-001)
2. **Under cap → complete** — below the cap, the run completes `natural-completion`. (SC-001)
3. **Per-session cap** — the running total across a session's runs crosses → a later run terminates
   `budget-exceeded`; resets on resume. (FR-002/006)
4. **Default-off byte-identity** — no caps → no accounting, no new events, byte-identical to today.
   (FR-004, SC-002)
5. **Unpriced fail-soft** — a cap + an unpriced model → NOT terminated; a `warning` diagnostic is
   emitted; the run completes. (FR-005, SC-002)
6. **Reason is distinct + schema-stable** — the stop reason is `budget-exceeded` (NOT `cancelled`);
   it serializes/replays with no `SCHEMA_VERSION` change. (FR-003, SC-003)
7. **Consumer audit** — CLI render / checkpoint rebuild / web/API handle `budget-exceeded` without
   mishandling (esp. rebuild does NOT strand the input, unlike `cancelled`). (FR-003, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the events serialize/round-trip + `SCHEMA_VERSION` tests (must still pass — additive, no bump).
