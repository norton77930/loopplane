# Tasks: Durable USD Ledger

**Feature**: 062-usd-ledger | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0010](../../docs/adr/0010-usd-ledger-monthly-budget.md)

**Scope**: additive — a NEW `loopplane.ledger` package (a `UsdLedger` Protocol + File/SQLite/Postgres
backends) mirroring 060's checkpoint store; pure storage, no loop/budget/event change. Exact Decimal;
atomic per-`(principal,month)` increment; import-guarded; no new dependency. Per ADR 0010.

**Tests**: requested (offline-safe; the concurrent-no-lost-update test is load-bearing).

## Phase 1: Protocol + package (Foundational)

- [ ] T001 Create `src/loopplane/ledger/base.py` — the `UsdLedger` Protocol:
  `async def add(self, principal_id: str, month: str, usd: Decimal) -> Decimal` (the new
  post-increment total; atomic per `(principal_id, month)`) + `def get(self, principal_id: str,
  month: str) -> Decimal` (sync; unseen → `Decimal(0)`). Docstrings state `month` is an opaque
  caller-derived `YYYY-MM` string + exact-Decimal money. Mirror `checkpoint/base.py`'s Protocol style.

## Phase 2: Backends (P1) 🎯

- [ ] T002 [File] `src/loopplane/ledger/file.py` `FileUsdLedger`: per-`(principal,month)` JSON file
  (Decimal-as-string) under a per-key `anyio.Lock` (`_locks: dict[tuple[str,str], anyio.Lock]`);
  `add` = lock → read (or 0) → sum (exact Decimal) → write+flush → return the new total; `get` = read
  or `Decimal(0)`. Single-process-honest. Mirror `checkpoint/file.py`'s structure.
- [ ] T003 [SQLite] `src/loopplane/ledger/sqlite.py` `SqliteUsdLedger`: a `ledger(principal_id TEXT,
  month TEXT, usd_total TEXT, PRIMARY KEY(principal_id,month))` table (created on connect); `add` =
  under the per-key lock + a transaction, UPSERT the exact-Decimal sum (read current, add in Python,
  write back as TEXT) and return the new total; `get` = SELECT or `Decimal(0)`. Mirror
  `checkpoint/sqlite.py`.
- [ ] T004 [Postgres] `src/loopplane/ledger/postgres.py` `PostgresUsdLedger`: a `ledger(..., usd_total
  NUMERIC, PRIMARY KEY(principal_id,month))` table; `add` = a single `INSERT ... ON
  CONFLICT(principal_id,month) DO UPDATE SET usd_total = ledger.usd_total + EXCLUDED.usd_total
  RETURNING usd_total` (the only cross-PROCESS-safe path) via ADR 0008's sync thread-bridge (async
  `add` wraps psycopg in `anyio.to_thread.run_sync`; sync `get` direct); IMPORT-GUARD `psycopg`
  inside the module/constructor (a clear error naming `loopplane[postgres]`) so `loopplane.ledger`
  imports without the extra. NUMERIC ↔ Decimal (no float). The DSN is never logged/echoed. Mirror
  `checkpoint/postgres.py`.

## Phase 3: Export + docs (P1)

- [ ] T005 `src/loopplane/ledger/__init__.py`: export `UsdLedger`, `FileUsdLedger`, `SqliteUsdLedger`,
  `PostgresUsdLedger` (`__all__`). Add a NEW `loopplane.ledger` package section to
  `docs/api-reference.md` (so the api-reference bijection — which enumerates packages with `__all__` —
  stays exact). Confirm `loopplane.ledger` imports WITHOUT the `postgres` extra (the psycopg import
  is guarded, not at module top level).

## Phase 4: Tests (P1/P2) — offline-safe

- [ ] T006 Add `tests/usd_ledger_stub.py` — a faithful in-memory psycopg stub for the Postgres ledger
  (modelling the exact CREATE/UPSERT-RETURNING/SELECT SQL with a loud AssertionError fall-through),
  mirroring `tests/pg_stub.py`. Then a shared parametrized ledger contract test (File / SQLite /
  Postgres-via-stub; `pytest.importorskip("psycopg")` for the Postgres param): round-trip + `add`
  returns the new total; `get` unseen = `Decimal(0)`; exact-Decimal no-float-drift (large + fractional);
  the **load-bearing concurrent test** — N concurrent `add`s to the same `(principal,month)` →
  `get` == N × amount exactly (no lost increment). Plus the Postgres import-guard test (construct
  without psycopg → clear error) + DSN-not-echoed. Use BENIGN placeholders (no `secret = "..."` DSN
  literals — cf. the 060 → da618da public-safety fix).

## Phase 5: Gates

- [ ] T007 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive). Confirm: the structural audits
  (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the api-reference-bijection
  test (the new `loopplane.ledger` section) pass; `import loopplane.ledger` works WITHOUT the
  `postgres` extra; SCHEMA_VERSION unchanged (no event change). Do NOT run the full pytest
  concurrently with a verify Workflow (MCP load flake).

## Dependencies

- T001 → T002/T003/T004 (the backends) → T005 (export) → T006 (tests) → T007 (gates last).

## Implementation strategy

- A new package mirroring `loopplane.checkpoint` (060). May be done inline or via a fork; then the
  four gates + the structural audits + the api-reference bijection + an adversarial verify (atomic
  no-lost-update per backend; exact-Decimal no float; import-guard keeps the base install psycopg-free;
  the Postgres stub is faithful [the contract parity is real]; DSN public-safe; additive/no
  runtime change) before commit — Workflow if available, else MANUAL. Commit only on a clean review /
  GO; fix + re-verify FRESH otherwise.
- Additive; ADR 0010; the store ONLY (enforcement is 063).

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
