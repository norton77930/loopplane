# Quickstart / Validation: Cost Surfacing

See [contracts/cost-surfacing.md](contracts/cost-surfacing.md), [data-model.md](data-model.md).
Read-only web/API surfacing of computed USD (055 spend + 062 ledger). Additive, owner-scoped,
default-off honest, public-safe; no schema/reason/dependency/ADR.

## Run the tests

```powershell
pytest tests/ -k "cost or surfacing or webapi" -q
pytest -q   # full suite (additive proof)
```

Expected: green; default-off (no budget/ledger) → endpoints return `usd_spent: null`; the rest of the
webapi suite byte-identical; SCHEMA_VERSION unchanged.

## Validation scenarios (mirror the acceptance scenarios)

1. **Owner reads session cost** — a budget-configured owned session → `GET /sessions/{id}/cost`
   returns the accumulated USD (exact Decimal string). (FR-001, SC-001)
2. **Non-owner → 404** — another principal GETs the session cost → 404 (no leak). (FR-001, SC-001)
3. **No budget → not tracked** — a session with no cap → `usd_spent: null`. (FR-004)
4. **Principal reads its monthly spend** — a configured `usd_ledger` pre-seeded for the principal →
   `GET /cost/monthly` returns that principal's current-month USD; never another's. (FR-002, SC-002)
5. **No ledger → not tracked** — no `usd_ledger` → `/cost/monthly` returns `usd_spent: null`.
   (FR-004, SC-002)
6. **Public-safe** — responses carry only the caller's own id + a Decimal string; no DSN/secret.
   (FR-006)

## Manual gate checks (autopilot)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the
events serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the api-reference bijection (the new
view/accessor names are additive — update `docs/api-reference.md` if any new public name is exported).
NOTE: run the full pytest + any verify Workflow at DIFFERENT times (CPU-contention flake); scan new
test files for forbidden tokens before committing.
