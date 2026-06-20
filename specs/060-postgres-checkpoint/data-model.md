# Data Model: PostgreSQL Checkpoint Backend

Additive; inside `loopplane.checkpoint`. No Protocol/runtime/event change (sync thread-bridge). Per
[ADR 0008](../../docs/adr/0008-postgres-checkpoint.md).

## PostgresCheckpointStore (new — a 3rd CheckpointStore backend)

Implements the EXISTING `CheckpointStore` Protocol (unchanged):

| Method | Sync/async | Behavior (mirrors SqliteCheckpointStore) |
| ------ | ---------- | ---------------------------------------- |
| `append(record)` | async | `to_thread`: INSERT (session_id, sequence, recorded_at, data) under a per-session lock; `serialize_record` for `data`. |
| `load(session_id)` | sync | SELECT ordered by `sequence`; `deserialize_record`; corrupt rows skipped + reported. |
| `list_sessions()` | sync | the session summaries (latest recorded_at / title). |
| `set_title(session_id, title)` | async | `to_thread`: update the session title. |
| `delete_session(session_id)` | sync | delete the session's rows. |

Backing table (created on connect): `records(session_id text, sequence int, recorded_at text/timestamptz,
data text, PRIMARY KEY (session_id, sequence))` — the same shape as SQLite.

## loopplane[postgres] extra (new)

`psycopg[binary]>=3`, import-guarded (a clear error naming the extra when constructed without it);
the base install + `loopplane.checkpoint` import stay psycopg-free.

## Rules (from FRs + ADR 0008)

| Rule | Source |
| ---- | ------ |
| 3rd backend, EXISTING Protocol unchanged, reuse records.py + same table shape | FR-001, D1 |
| sync thread-bridge: async methods via anyio.to_thread; sync methods direct; Protocol/call sites unchanged | FR-004, D2 |
| import-guarded loopplane[postgres]; default backend stays file/sqlite (byte-identical) | FR-002, D3 |
| same contract: round-trip/ordering/corrupt-row tolerance/per-session serialization | FR-003, D4 |
| additive; no runtime/loop/gateway/event change | FR-005 |
| offline-safe tests (skip / faithful stub); DSN public-safe | FR-006, D5 |
