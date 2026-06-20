# Quickstart / Validation: PostgreSQL Checkpoint Backend

See [contracts/postgres-checkpoint.md](contracts/postgres-checkpoint.md),
[data-model.md](data-model.md), and [ADR 0008](../../docs/adr/0008-postgres-checkpoint.md). A 3rd
`CheckpointStore` backend (sync thread-bridge); additive, default-unchanged.

## Install the extra (for the backend + its tests)

```powershell
pip install -e ".[postgres]"   # psycopg[binary]>=3
```

## Run the checkpoint tests

```powershell
pytest tests/ -k "checkpoint or postgres or sqlite" -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; with no Postgres configured the default File/SQLite backends + the existing
checkpoint tests pass unchanged. The Postgres contract is proven against a faithful offline stub; a
live-DB test (if any) skips when unavailable. Base/non-postgres installs are unaffected (psycopg is
import-guarded).

## Validation scenarios (mirror the acceptance scenarios)

1. **Round-trip** — append records → `load` returns them ordered by `sequence`, content preserved.
   (FR-001, SC-001)
2. **Contract parity** — `list_sessions`/`set_title`/`delete_session` + corrupt-row tolerance match
   the SQLite backend (the shared/parametrized contract test). (FR-003, SC-001)
3. **Default-unchanged** — no Postgres → File/SQLite byte-identical; existing checkpoint tests pass.
   (FR-002, SC-002)
4. **Import-guarded** — base install (no `postgres` extra) imports `loopplane.checkpoint`; the
   Postgres backend errors clearly only when constructed without psycopg. (FR-002, SC-002)
5. **Protocol unchanged** — the `CheckpointStore` Protocol + call sites + File/SQLite backends are
   untouched (the sync thread-bridge). (FR-004, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the api-reference bijection (the new `PostgresCheckpointStore` export documented).
