# Contract: Backend selection & integration boundary

How a backend is chosen and what this unit promises **not** to change. Enforces the
"supported, not required" intent (spec) and the unit-014 drift contracts.

## Selection (additive, defaulted)

- `StorageConfig` gains `checkpoint_backend: Literal["file", "sqlite"] = "file"`.
- `_coerce_storage` reads `value.get("checkpoint_backend", "file")` for mapping input.
- `host/assembly.py` builds the store from the selector:
  - `"file"` (default) → `FileCheckpointStore(storage.root)`
  - `"sqlite"` → `SqliteCheckpointStore(storage.root / "checkpoints.sqlite3")`
- The artifact store continues to use `storage.root`; durable backends remain "both or
  neither" as today.

## Invariants (what MUST NOT change)

1. **Default is byte-identical (FR-003/FR-004)**: with the selector unset, the assembled
   runtime builds `FileCheckpointStore` and behaves exactly as before. The **no-store**
   path (no `storage`) is unchanged.
2. **No runtime-core or contract change (FR-008)**: `RuntimeController`, `SessionRecorder`,
   and host assembly depend only on the `CheckpointStore` Protocol; **no method signature
   changes**; no event-bus, loop, or gateway change.
3. **No new runtime dependency (FR-005)**: the SQLite store imports only stdlib `sqlite3`.
   The core install stays `anyio + pydantic + jsonschema`; the packaging extras set is
   **unchanged** (no new optional extra).
4. **Public surface stays in sync (FR-009)**: `checkpoint/__init__.py` `__all__` exports
   `CheckpointStore` (now the Protocol), `FileCheckpointStore`, `SqliteCheckpointStore`,
   and `SessionSummary`; `docs/api-reference.md`'s checkpoint section matches `__all__`
   (the unit-014 drift test). `CHANGELOG.md` records unit 021.
5. **Offline (FR-005)**: the SQLite backend uses a local file only; no network, no
   service; it runs in CI like every existing gate.

## Rollback (Constitution X)

Delete `sqlite.py` and the `checkpoint_backend` field; collapse `base.py` + `file.py`
back into a single `store.py` `CheckpointStore` filesystem class; revert the
construction-site renames and the api-reference/changelog edits. The runtime core is
untouched, so rollback is local to the checkpoint package + host config + docs.
