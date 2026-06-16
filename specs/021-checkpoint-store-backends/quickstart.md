# Quickstart: Checkpoint Store Backends (unit 021)

Validates that the runtime persists and resumes through **either** backend behind the
same interface, and that the default is unchanged. All offline; no new dependency.

## Prerequisites

- `uv sync` (no extra needed — the SQLite store is stdlib).

## Scenario 1 — default (filesystem), unchanged

```python
from loopplane.host import RuntimeConfig, StorageConfig, LoopPlaneHost

cfg = RuntimeConfig(model=my_model, storage=StorageConfig(root="./sessions"))
# checkpoint_backend defaults to "file" → FileCheckpointStore, exactly as before.
host = LoopPlaneHost(cfg)
```

**Expected**: behavior identical to today; records land under `./sessions/<id>/records.jsonl`.

## Scenario 2 — opt into SQLite (one config value)

```python
cfg = RuntimeConfig(
    model=my_model,
    storage=StorageConfig(root="./sessions", checkpoint_backend="sqlite"),
)
host = LoopPlaneHost(cfg)
```

**Expected**: sessions persist to `./sessions/checkpoints.sqlite3`; a later run can
`resume` the session; `list_sessions()` returns the sessions most-recent-first. No
runtime code changed — only the config value.

## Scenario 3 — interchangeable behind the Protocol

```python
from loopplane.checkpoint import FileCheckpointStore, SqliteCheckpointStore

for store in (FileCheckpointStore(tmp), SqliteCheckpointStore(tmp / "cp.sqlite3")):
    await store.append(record)
    records, problems = store.load(record.session_id)
    assert records and not problems
    assert store.list_sessions()[0].session_id == record.session_id
```

**Expected**: both backends satisfy the same `CheckpointStore` contract
([contracts/checkpoint-store.md](./contracts/checkpoint-store.md)).

## Gate

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

**Expected**: all green; the shared parametrized contract suite passes for both backends;
the api-reference/`__all__` drift test passes; no new dependency in the build.
