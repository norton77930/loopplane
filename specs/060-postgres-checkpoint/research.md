# Research: PostgreSQL Checkpoint Backend

The fork is settled by the maintainer (sync thread-bridge) + **[ADR 0008](../../docs/adr/0008-postgres-checkpoint.md)**. No open `NEEDS CLARIFICATION`.

## Decision 1 — A 3rd backend behind the EXISTING Protocol (ADR 0008 D1)

**Decision**: `PostgresCheckpointStore` implements the current `CheckpointStore` Protocol unchanged
(`append`/`set_title` async; `load`/`list_sessions`/`delete_session` sync), reusing `records.py` over
the same `records(session_id, sequence, recorded_at, data)` table (PK `(session_id, sequence)`),
mirroring `SqliteCheckpointStore` (corrupt-row tolerance, per-session append serialization).

**Rationale**: Drop-in third backend; reuse-first (the Protocol + record encoding already exist).

## Decision 2 — Sync thread-bridge (maintainer-chosen; ADR 0008 D2)

**Decision**: Use the **sync** psycopg driver. The async Protocol methods (`append`/`set_title`) wrap
the psycopg work in `anyio.to_thread.run_sync` (so the event loop is not blocked on network I/O); the
sync Protocol methods (`load`/`list_sessions`/`delete_session`) call psycopg directly (as SQLite
does). The `CheckpointStore` Protocol + ALL call sites + the File/SQLite backends stay UNCHANGED.

**Rationale**: Smallest, safest, byte-identical at the contract; a backend-add should not break the
unit-002 Protocol + every call site + both existing backends.

**Alternatives considered**: an async-Protocol rewrite (psycopg async + a fully-async Protocol) —
REJECTED by the maintainer: larger, contract-changing, no proportional gain over the thread bridge.

## Decision 3 — Import-guarded extra; default unchanged (ADR 0008 D3)

**Decision**: A NEW `loopplane[postgres]` extra (`psycopg[binary]>=3`), import-guarded so the base
install + non-postgres users are unaffected. The default backend stays File/SQLite (byte-identical
when Postgres is not configured); the host selects Postgres (a DSN) where it selects File/SQLite.

**Rationale**: Impose nothing on existing deployments; no hard dependency.

## Decision 4 — Same contract + offline-safe tests (ADR 0008 D4/D5)

**Decision**: Match the SQLite backend's contract (round-trip/ordering/corrupt-row tolerance/
per-session serialization) — a shared/parametrized contract test against a **faithful offline stub**
(no running DB); any live-DB test skips when unavailable. The DSN/credential is never echoed (VII).

**Rationale**: Deterministic, offline (the suite's NFR); the Postgres backend proves the same contract
as SQLite without infrastructure.

## Out of scope (ADR 0008 D6)

Connection pooling / migration tooling beyond table creation; the G22 Phase C per-user-monthly USD
ledger (a separate durable store); G20 multi-tenant concurrency (unit 061).
