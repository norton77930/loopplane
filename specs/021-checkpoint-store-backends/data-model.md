# Data Model: Checkpoint Store Backends (unit 021)

Entities for the extracted checkpoint interface and its two backends. Types are
illustrative; the authority is the spec's requirements and the contracts.

## `CheckpointStore` (Protocol) — `checkpoint/base.py`

The durable session-record boundary the runtime depends on. **Signatures are unchanged
from today's concrete class** (only the location and the Protocol-ness are new).

```python
class CheckpointStore(Protocol):
    async def append(self, record: CheckpointRecord) -> None: ...
    def load(self, session_id: str) -> tuple[list[CheckpointRecord], list[str]]: ...
    def list_sessions(self) -> list[SessionSummary]: ...
```

- **append**: durably persist one record for `record.session_id`, **flushed/committed
  before returning**; serialized per session.
- **load**: return the session's records **in append order** plus a list of
  human-readable **problems** (e.g., skipped corrupt records); a missing session →
  `([], [])`.
- **list_sessions**: identity + recency for all sessions, **most-recent-first**; a
  missing/never-written store → `[]`.

## `SessionSummary` (dataclass, frozen) — `checkpoint/base.py`

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` | session identity (directory / table key) |
| `label` | `str \| None` | from the session's `SessionMetaRecord` |
| `created_at` | `datetime` | from the session meta payload |
| `last_active_at` | `datetime` | **file**: records-file mtime · **sqlite**: max `recorded_at` |

## `FileCheckpointStore` — `checkpoint/file.py`

The existing implementation, **moved unchanged** and renamed. `__init__(self, base_dir:
Path)`; append-only `records.jsonl` per session directory under `base_dir`; corrupt
lines skipped on load; missing root → empty listing.

## `SqliteCheckpointStore` — `checkpoint/sqlite.py`

New, optional, stdlib-`sqlite3` backend. `__init__(self, db_path: Path)`; opens/creates
the database and ensures the schema.

### Schema

```sql
CREATE TABLE IF NOT EXISTS records (
    session_id   TEXT    NOT NULL,
    sequence     INTEGER NOT NULL,
    recorded_at  TEXT    NOT NULL,
    data         TEXT    NOT NULL,          -- serialize_record(record), reused verbatim
    PRIMARY KEY (session_id, sequence)
);
```

- **append**: `INSERT` the row with `data = serialize_record(record)`; `commit()` before
  return; serialized per session by an `anyio.Lock`.
- **load**: `SELECT data FROM records WHERE session_id=? ORDER BY sequence`; run
  `deserialize_record` on each; a `None` (corrupt) becomes a reported problem — same
  semantics as the filesystem store.
- **list_sessions**: group by `session_id`; read the `SessionMetaRecord` for
  `created_at`/`label`; `last_active_at = max(recorded_at)`; order most-recent-first.

## `StorageConfig.checkpoint_backend` — `host/config.py`

| Field | Type | Default | Notes |
|---|---|---|---|
| `checkpoint_backend` | `Literal["file", "sqlite"]` | `"file"` | additive; unset → filesystem (unchanged) |

`_coerce_storage` reads `value.get("checkpoint_backend", "file")` in its dict branch.
`host/assembly.py`: `"sqlite"` → `SqliteCheckpointStore(root / "checkpoints.sqlite3")`,
otherwise `FileCheckpointStore(root)`. The artifact store continues to use `root`.

## Shared / reused (unchanged) — `checkpoint/records.py`

`CheckpointRecord` union, `SessionMetaRecord`, `serialize_record`, `deserialize_record`,
`RECORD_SCHEMA_VERSION`. Both backends use these; **no second record format** is
introduced.
