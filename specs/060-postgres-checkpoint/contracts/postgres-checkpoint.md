# Contract: PostgreSQL Checkpoint Backend

A 3rd `CheckpointStore` backend behind the EXISTING Protocol (sync thread-bridge). Per
[ADR 0008](../../docs/adr/0008-postgres-checkpoint.md). Default backend stays File/SQLite
(byte-identical); psycopg behind the import-guarded `loopplane[postgres]` extra.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `loopplane.checkpoint.PostgresCheckpointStore` | a `CheckpointStore` impl | NEW (additive `__all__`); same Protocol as File/SQLite. |
| `loopplane[postgres]` extra | `["psycopg[binary]>=3"]` | NEW optional extra; import-guarded. |

## Behavior

| Case | Result |
| ---- | ------ |
| `append` then `load` | The records are returned ordered by `sequence`, content preserved (reused `records.py`). |
| `list_sessions` / `set_title` / `delete_session` | Behave exactly like the SQLite backend (same Protocol contract). |
| Corrupt/garbage row on `load` | Skipped + reported in the problems list (mirroring SQLite). |
| Concurrent appends to one session | Serialized (per-session lock) / PK `(session_id, sequence)`. |
| No Postgres configured (default) | File/SQLite — byte-identical to today. |
| Base install (no `postgres` extra) | `loopplane.checkpoint` imports; the Postgres backend errors clearly only when constructed without psycopg. |

## Invariants

- Implements the EXISTING `CheckpointStore` Protocol UNCHANGED (`append`/`set_title` async;
  `load`/`list_sessions`/`delete_session` sync) — the Protocol + ALL call sites + the File/SQLite
  backends are byte-identical (the sync thread-bridge; no unit-002 contract change).
- Async methods off-load psycopg via `anyio.to_thread.run_sync`; sync methods call psycopg directly
  (as SQLite does). Reuses `records.py` over the same `(session_id, sequence, recorded_at, data)`
  table (PK `(session_id, sequence)`).
- The `psycopg[binary]>=3` dependency is import-guarded behind `loopplane[postgres]`; the base install
  + the existing checkpoint suite are unaffected; the default backend stays File/SQLite.
- Public-safe: the DSN/credential is host config, never echoed (VII). No event-schema/content change.
- Offline-testable: the contract is proven against a faithful stub; the suite never requires a running
  database.
- Out of scope (deferred): pooling/migration tooling; the G22 Phase C ledger; G20 concurrency.
