# Quickstart / Validation: Durable USD Ledger

See [contracts/usd-ledger.md](contracts/usd-ledger.md), [data-model.md](data-model.md), and
[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md). A NEW `loopplane.ledger` package — a
durable per-`(principal_id, month)` USD accumulator; additive, pure storage (enforcement is 063).

## Install the extra (for the Postgres backend + its tests)

```powershell
pip install -e ".[postgres]"   # the EXISTING extra (psycopg[binary]>=3) — reused, not new
```

## Run the ledger tests

```powershell
pytest tests/ -k "ledger" -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; `loopplane.ledger` imports without the `postgres` extra (the `psycopg` import is
guarded); no runtime/event change.

## Validation scenarios (mirror the acceptance scenarios)

1. **Round-trip + new total** — `add(p, "2026-06", 0.10)` then `add(p, "2026-06", 0.05)` → the second
   returns `0.15`; `get(p, "2026-06") == 0.15`. (FR-001/002, SC-001)
2. **Unseen key** — `get(p, unseen) == Decimal(0)`. (FR-001, SC-001)
3. **Atomic, no lost update** — N concurrent `add`s of the same amount to one key → `get` == N ×
   amount exactly (File + SQLite in-process; the Postgres atomic-upsert SQL asserted via the stub).
   (FR-002, SC-002)
4. **Exact money** — large/fractional accumulation has no float drift (Decimal; TEXT/NUMERIC).
   (FR-004, SC-003)
5. **Import-guarded** — base install (no `postgres` extra) imports `loopplane.ledger`; the Postgres
   backend errors clearly only when constructed without `psycopg`. (FR-005, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the api-reference bijection (the new `loopplane.ledger` package section). NOTE: scan new files for
forbidden tokens before committing (no `secret = "..."` DSN literals; use benign placeholders — cf.
the 060 → da618da public-safety fix).
