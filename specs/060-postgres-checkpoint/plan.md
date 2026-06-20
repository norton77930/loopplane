# Implementation Plan: PostgreSQL Checkpoint Backend

**Branch**: `060-postgres-checkpoint` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/060-postgres-checkpoint/spec.md`

**Maintainer DECISION (consulted at plan, FR-004)**: **sync thread-bridge** — keep the existing sync
`CheckpointStore` Protocol unchanged; psycopg (sync) via `anyio.to_thread`. Recorded in
**[ADR 0008](../../docs/adr/0008-postgres-checkpoint.md)**. The async-Protocol rewrite was rejected.

## Summary

Add `PostgresCheckpointStore`, a 3rd `CheckpointStore` backend mirroring `SqliteCheckpointStore`:
the same Protocol (`append`/`set_title` async; `load`/`list_sessions`/`delete_session` sync), the
same `records.py` encoding, the same table `records(session_id, sequence, recorded_at, data)` (PK
`(session_id, sequence)`), the same corrupt-row tolerance + per-session append serialization — over
**psycopg (sync)**. Per the maintainer fork: the async methods wrap psycopg in
`anyio.to_thread.run_sync` (the event loop is never blocked on network I/O); the sync methods call
psycopg directly (as SQLite does). `psycopg[binary]>=3` is behind a NEW import-guarded
`loopplane[postgres]` extra; the default backend stays File/SQLite (byte-identical when Postgres is
not configured). The `CheckpointStore` Protocol + ALL call sites + the File/SQLite backends are
UNCHANGED. No runtime/loop/gateway/event change.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: NEW optional extra `loopplane[postgres] = ["psycopg[binary]>=3"]`
(import-guarded, mirroring the existing extra pattern). No base/runtime dep change.

**Storage**: a Postgres `records` table (same shape as SQLite); host-supplied DSN/connection.

**Testing**: pytest, **offline-safe** — the backend's contract is exercised against the SAME shared
assertions as the SQLite backend, using a faithful in-memory/stub connection (or `psycopg`'s test
facilities) so NO running database is required; a live-DB test (if any) skips when unavailable.

**Target Platform**: cross-platform library (Postgres optional).

**Constraints**: additive; the existing sync `CheckpointStore` Protocol + all call sites + File/SQLite
backends UNCHANGED (the sync thread-bridge); default backend stays File/SQLite (byte-identical); the
new dep import-guarded; DSN public-safe; no runtime/event change. ADR 0008.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-006 + ADR 0008. ✅
- **IV. Boundary**: A new backend behind the EXISTING `CheckpointStore` Protocol; the runtime/loop/
  gateway untouched; the Protocol + call sites unchanged (sync bridge). ✅
- **V. Tool Gateway**: N/A — no tool/execution path. ✅
- **VI. Event Bus / content**: No event-schema/SCHEMA_VERSION/content change. ✅
- **VII. Public-safe**: The DSN/credential is host config; never echoed. ✅
- **IX. Reference-not-clone**: Mirrors the SQLite backend + reuses `records.py`. ✅
- **X. Testable Evolution**: Additive; default-unchanged byte-identical; reversible; offline-tested. ✅

**Result**: PASS — additive; the maintainer chose the sync thread-bridge so there is **no breaking
002 Protocol change**; ADR 0008 records it. Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/060-postgres-checkpoint/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/postgres-checkpoint.md
└── checklists/requirements.md
docs/adr/0008-postgres-checkpoint.md   # the fork decision (sync thread-bridge)
```

### Source Code (repository root)

```text
src/loopplane/checkpoint/postgres.py   # NEW: PostgresCheckpointStore (mirrors SqliteCheckpointStore;
                                       #   psycopg sync; async methods via anyio.to_thread; reuses
                                       #   records.py; import-guards psycopg)
src/loopplane/checkpoint/__init__.py   # MODIFIED: export PostgresCheckpointStore (additive __all__)
pyproject.toml                         # MODIFIED: + [project.optional-dependencies] postgres =
                                       #   ["psycopg[binary]>=3"]
docs/api-reference.md                  # MODIFIED: + PostgresCheckpointStore under loopplane.checkpoint
tests/<checkpoint contract test>       # NEW/MODIFIED: parametrize the store contract over Postgres
                                       #   (offline stub) alongside SQLite; offline-safe
```

**Structure Decision**: `PostgresCheckpointStore` is a near-copy of `SqliteCheckpointStore`'s
structure: a `records` table (created on connect), `append` (async → `to_thread` an INSERT+commit
under a per-session lock), `load`/`list_sessions`/`delete_session` (sync, direct psycopg), `set_title`
(async → `to_thread`), all reusing `records.py` for the `data` column. `psycopg` is imported inside
the module guarded (a clear error naming `loopplane[postgres]` when absent) OR the whole module is
import-guarded by the `__init__` export — keep `loopplane.checkpoint` importable without psycopg
(confirm the bijection/import tests pass without the extra). The default backend selection is
unchanged. Tests reuse/parametrize the SQLite contract assertions against a faithful offline stub.

## Complexity Tracking

> A third backend behind an existing Protocol, mirroring the SQLite one + reusing records.py, via the
> maintainer-chosen sync thread-bridge (Protocol + call sites unchanged). A small ADR (0008); one
> optional dependency; default-unchanged byte-identical. Not a Constitution violation.
