# Contract: `CheckpointStore` interface

The durable session-record boundary the runtime depends on (Constitution IV). Any
implementation MUST satisfy this contract; the two shipped implementations
(`FileCheckpointStore`, `SqliteCheckpointStore`) are verified against it by one shared,
parametrized contract suite.

## Surface (unchanged from the prior concrete class)

```python
async def append(self, record: CheckpointRecord) -> None
def load(self, session_id: str) -> tuple[list[CheckpointRecord], list[str]]
def list_sessions(self) -> list[SessionSummary]
```

The interface is **single-tenant**: every operation is keyed by `session_id`. No
`principal_id` / ownership parameter exists in this unit (deferred to Phase C).

## Behavioral obligations

1. **Durable append (FR-006)**: `append` MUST persist the record so it survives a crash
   immediately after the call returns — the filesystem store flushes, the SQLite store
   commits, **before** returning. Appends for one `session_id` MUST be serialized so
   concurrent appends do not interleave or corrupt the stream.
2. **Ordered load (FR-006)**: `load` MUST return a session's records in **append order**.
   A record that cannot be decoded MUST be **skipped and reported** as a problem string,
   and MUST NOT fail the whole load. An unknown/empty session MUST return `([], [])`.
3. **Listing + recency (FR-007)**: `list_sessions` MUST return one `SessionSummary` per
   session with `created_at`/`label` from the session's meta record, ordered
   **most-recent-first**. A missing/never-written store MUST return `[]`, not raise.
   `last_active_at` MAY be derived per backend (file mtime vs. latest `recorded_at`); both
   MUST represent most-recent activity and order correctly.
4. **Round-trip fidelity**: records written by `append` MUST come back from `load`
   value-equal (the shared `serialize_record`/`deserialize_record` encoding guarantees
   this across both backends).

## Parity test matrix (shared suite, both backends)

| Case | Assertion |
|---|---|
| append → load | records returned in order, value-equal, `problems == []` |
| corrupt record among good | good records load; the corrupt one is reported; no raise |
| missing/never-written store | `load` → `([], [])`; `list_sessions` → `[]` |
| multiple sessions, recency | `list_sessions` ordered most-recent-first |
| meta (`created_at`/`label`) | surfaced in the `SessionSummary` |

## Non-obligations

- No cross-session query, search, retention, or compaction.
- No multi-process / multi-writer concurrency beyond per-session serialization.
- No migration between backends.
