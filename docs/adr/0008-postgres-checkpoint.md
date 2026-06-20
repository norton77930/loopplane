# ADR 0008: PostgreSQL checkpoint backend (sync thread-bridge)

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (chose the **sync thread-bridge** fork at the 060 plan consult);
  spec 060 (postgres-checkpoint).
- **Related**: the checkpoint **CheckpointStore** Protocol (unit 002), Constitution **IV** (a new
  backend behind the existing Protocol — no boundary change), **X** (additive, default-unchanged
  byte-identical, reversible), **VII** (the DSN/credential is host config, never echoed). Eighth ADR
  (after 0001–0007).

## Context

The checkpoint layer is a `CheckpointStore` Protocol (base.py:26) — `append`/`set_title` async,
`load`/`list_sessions`/`delete_session` sync — with two backends today: `File` and `SQLite` (both
reuse `records.py` over `(session_id, sequence, recorded_at, data)`, PK `(session_id, sequence)`).
Gap G19 wants a **networked/shared** store for multi-process / durable deployments. The design
question (a maintainer fork) was the concurrency model: a **sync thread-bridge** (keep the sync
Protocol; psycopg via threads) vs an **async-Protocol rewrite** (make the Protocol fully async +
psycopg async).

## Decision

- **D1 — A third backend behind the EXISTING Protocol.** Add `PostgresCheckpointStore` implementing
  the current `CheckpointStore` Protocol unchanged (`append`/`set_title` async;
  `load`/`list_sessions`/`delete_session` sync), reusing `records.py`
  (`serialize_record`/`deserialize_record`) over the same `records (session_id, sequence,
  recorded_at, data)` table (PK `(session_id, sequence)`), mirroring `SqliteCheckpointStore`
  (corrupt-row tolerance, per-session append serialization).
- **D2 — Sync thread-bridge (MAINTAINER-CHOSEN).** Use the **sync** psycopg driver. The async
  Protocol methods (`append`/`set_title`) wrap the psycopg work in `anyio.to_thread.run_sync` so the
  event loop is never blocked on network I/O; the sync Protocol methods
  (`load`/`list_sessions`/`delete_session`) call psycopg directly (mirroring SQLite's sync methods).
  **The `CheckpointStore` Protocol, ALL call sites, and the File + SQLite backends are UNCHANGED /
  byte-identical.** The async-Protocol rewrite is **REJECTED** — it would break the unit-002 Protocol
  contract + every call site + both existing backends for no proportional gain over the thread bridge.
- **D3 — Import-guarded optional extra; default unchanged.** A NEW `loopplane[postgres]` extra
  (`psycopg[binary]>=3`), import-guarded so the base install + non-postgres users are unaffected. The
  **default backend stays File/SQLite** — byte-identical when Postgres is not configured. The host
  selects the Postgres backend (a DSN) where it selects File/SQLite today.
- **D4 — Same contract behavior.** Round-trip (append→load preserves order + content), ordering by
  `sequence`, corrupt-row tolerance (skipped + reported), per-session append serialization — matching
  the SQLite backend (a shared/parametrized contract test).
- **D5 — Public-safe + offline-testable.** The DSN/credential is host config and is never echoed
  (VII). Tests skip when no Postgres is available (or use a faithful stub) — the suite never requires
  a running database.
- **D6 — Deferred.** Connection pooling / migration tooling beyond table creation; the G22 Phase C
  per-user-monthly USD ledger (a separate durable store); G20 multi-tenant concurrency (unit 061).

## Consequences

- **Enables G19**: a drop-in third, networked checkpoint backend; additive + default-unchanged.
- **No contract/boundary change (the sync bridge)**: the `CheckpointStore` Protocol + all call sites
  + the File/SQLite backends are untouched; byte-identical when Postgres is not configured. One new
  optional dependency (`psycopg[binary]`), import-guarded. Reversible (remove the backend + extra).
- **Honest cost**: the sync methods block on network I/O (the Protocol is sync) — acceptable + the
  same shape as SQLite's sync methods; the async methods are off-loaded via `to_thread`. The
  async-native path was consciously not taken (it is the deferred larger rewrite).
- **Deferred (documented)**: pooling/migrations, the Phase C ledger, G20 concurrency.
