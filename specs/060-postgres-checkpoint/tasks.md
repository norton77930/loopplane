# Tasks: PostgreSQL Checkpoint Backend

**Feature**: 060-postgres-checkpoint | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0008](../../docs/adr/0008-postgres-checkpoint.md)

**Scope**: additive — a 3rd CheckpointStore backend (PostgresCheckpointStore) mirroring the SQLite
backend, via the maintainer-chosen SYNC thread-bridge (the existing sync Protocol + call sites +
File/SQLite backends UNCHANGED). New import-guarded loopplane[postgres] extra; default-unchanged
byte-identical. Confined to loopplane.checkpoint.

**Tests**: requested (offline-safe).

## Phase 1: Dependency (Foundational)

- [ ] T001 Add to `pyproject.toml` `[project.optional-dependencies]`:
  `postgres = ["psycopg[binary]>=3"]` (alongside anthropic/net/openai/web/oauth). No base/runtime
  dep change.

## Phase 2: The backend (P1) 🎯

- [ ] T002 Create `src/loopplane/checkpoint/postgres.py` `PostgresCheckpointStore` mirroring
  `SqliteCheckpointStore`: the EXISTING `CheckpointStore` Protocol (async `append`/`set_title`; sync
  `load`/`list_sessions`/`delete_session`), reusing `records.py`
  (`serialize_record`/`deserialize_record`) over a `records(session_id, sequence, recorded_at, data,
  PRIMARY KEY (session_id, sequence))` table (created on connect), same corrupt-row tolerance +
  per-session append lock. Use the SYNC psycopg driver: the async methods wrap the psycopg
  INSERT/UPDATE in `anyio.to_thread.run_sync`; the sync methods call psycopg directly. **IMPORT-GUARD**
  `psycopg` inside the module/constructor (a clear error naming `loopplane[postgres]` when absent) so
  importing `loopplane.checkpoint` does NOT require psycopg. The DSN/credential is held but NEVER
  logged/echoed.

## Phase 3: Export + docs (P1)

- [ ] T003 Export `PostgresCheckpointStore` from `src/loopplane/checkpoint/__init__.py` (additive
  `__all__`) and add it to `docs/api-reference.md` under `loopplane.checkpoint` (so the api-reference
  bijection stays exact). Confirm `loopplane.checkpoint` still imports WITHOUT the `postgres` extra
  (the psycopg import must be deferred/guarded, not at the package/module top level).

## Phase 4: Tests (P1/P2) — offline-safe

- [ ] T004 Add Postgres checkpoint tests (OFFLINE — a faithful in-memory/stub psycopg connection, NO
  running DB; `pytest.importorskip("psycopg")` where the real driver is needed): run the SAME
  contract assertions the SQLite backend satisfies — append→load round-trip (ordered by `sequence`,
  content preserved), `list_sessions`/`set_title`/`delete_session`, corrupt-row tolerance (skipped +
  reported). Prefer parametrizing/sharing the existing SQLite contract test over the Postgres backend
  with a stub connection so no infrastructure is required; any live-DB test must skip when
  unavailable. Assert the DSN/token is never echoed.

## Phase 5: Gates

- [ ] T005 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-unchanged byte-identity). Confirm: the structural
  audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the
  api-reference-bijection test (the new `PostgresCheckpointStore` documented) + the existing
  checkpoint suite (File/SQLite) pass unchanged; the base install imports `loopplane.checkpoint`
  without the `postgres` extra (psycopg import-guarded). SCHEMA_VERSION unchanged (no event change).

## Dependencies

- T001 → T002 → T003 → T004 → T005 (gates last).

## Implementation strategy

- Confined to `loopplane.checkpoint` (a new backend + the extra + tests). May be done inline or via a
  fork; then the four gates + the structural audits + the api-reference bijection + an adversarial
  verify (Protocol/call-sites unchanged [sync bridge]; records.py reuse + contract parity with SQLite;
  import-guard keeps the base install psycopg-free; default-unchanged byte-identity; DSN public-safe)
  before commit — Workflow if available, else MANUAL. Commit only on a clean review / GO; fix +
  re-verify FRESH otherwise.
- Additive; ADR 0008 (sync thread-bridge); pooling/migrations + G22 Phase C + G20 concurrency deferred.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 1 low (informational). 100% requirement
coverage (FR-001..FR-006 and SC-001..003 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ **ADR 0008** ↔ data-model ↔ contract ↔ tasks agree
(PostgresCheckpointStore mirroring SqliteCheckpointStore via the maintainer-chosen sync thread-bridge
— existing Protocol unchanged, reuses records.py, sync psycopg with async methods via
`anyio.to_thread`; import-guarded `loopplane[postgres]`; default backend stays File/SQLite). **Additive
— the maintainer FORK (sync thread-bridge) means NO unit-002 Protocol/contract change**; the Protocol
+ ALL call sites + File/SQLite backends are byte-identical; no event-schema/SCHEMA_VERSION/content
change. No Constitution violation (I/IV/V/VI/VII/IX/X). Low note (informational): the offline test
stub must faithfully model the psycopg connection/cursor (execute/fetchall/commit) so the contract
parity with SQLite is real; and the psycopg import MUST stay deferred/guarded so `loopplane.checkpoint`
imports without the `postgres` extra (verify the bijection/import tests pass without it). **Cleared
for `/speckit-implement`.**
