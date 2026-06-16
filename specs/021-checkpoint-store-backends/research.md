# Research: Checkpoint Store Backends (unit 021)

Phase 0 decisions for extracting the checkpoint store into an interface and adding an
optional SQLite backend. Every decision is offline, additive, and reuses existing code.

## R1 — Interface shape: `Protocol`, not an abstract base class

- **Decision**: Define `CheckpointStore` as a `typing.Protocol` (structural), not an ABC.
- **Rationale**: The runtime already injects the store (`checkpoint_store: ... | None`);
  a structural Protocol lets each backend satisfy the seam without inheriting, exactly
  as unit 020's `ModelBoundary` does for model adapters. `mypy --strict` verifies
  conformance structurally. No `@runtime_checkable` is needed (no `isinstance` checks on
  the Protocol are required).
- **Alternatives**: ABC with `abstractmethod` — rejected: introduces an inheritance
  coupling the codebase deliberately avoids elsewhere (the model seam is a Protocol).

## R2 — Naming convention

- **Decision**: `CheckpointStore` names the **Protocol**; concrete backends are
  `FileCheckpointStore` and `SqliteCheckpointStore`.
- **Rationale**: Mirrors the established repo pattern (020: `ModelBoundary` Protocol with
  `AnthropicModel` / `OpenAIModel`). The clean conceptual name belongs to the boundary;
  implementations get descriptive names.
- **Cost**: the concrete class is renamed, so every `CheckpointStore(...)` construction
  site (~20, mostly tests + one production wiring + one doc) becomes
  `FileCheckpointStore(...)`. Mechanical; type annotations that meant "any store" now
  correctly mean the Protocol.

## R3 — Module layout

- **Decision**: Split `checkpoint/store.py` into `checkpoint/base.py` (Protocol +
  `SessionSummary`) and `checkpoint/file.py` (`FileCheckpointStore`); add
  `checkpoint/sqlite.py`; **remove `store.py`** (no back-compat shim). `records.py`
  (the shared encoding) and `recorder.py`/`rebuild.py` stay.
- **Rationale**: `base`/`file`/`sqlite` is symmetric and obvious; `SessionSummary` is
  storage-agnostic so it belongs with the Protocol. A shim would leave a dead import
  path (violates "clean up dead code").

## R4 — SQLite schema and encoding reuse

- **Decision**: One table, keyed by `(session_id, sequence)`, holding the **already
  serialized** record line:
  ```sql
  CREATE TABLE IF NOT EXISTS records (
      session_id   TEXT    NOT NULL,
      sequence     INTEGER NOT NULL,
      recorded_at  TEXT    NOT NULL,
      data         TEXT    NOT NULL,
      PRIMARY KEY (session_id, sequence)
  );
  ```
  `append` stores `serialize_record(record)` in `data` (plus `sequence`/`recorded_at`
  as columns for ordering and recency). `load` selects a session's rows `ORDER BY
  sequence`, runs `deserialize_record(data)` on each, and **reuses the same
  corrupt-record skipping** (a `None` result becomes a reported problem). `list_sessions`
  reads each session's meta record (the `SessionMetaRecord`) for `created_at`/`label`.
- **Rationale**: Reusing `serialize_record`/`deserialize_record` keeps **one** record
  format and one corruption story across both backends — the SQLite store never invents
  a second encoding. The columns are derived from the record so a row is
  self-describing for ordering and recency.
- **Alternatives**: a normalized column-per-field schema — rejected: it would fork the
  record encoding and the corruption semantics from the filesystem store.

## R5 — Durability and per-session serialization

- **Decision**: `append` performs the `INSERT` and `commit()` **before returning**
  (matching the filesystem store's flush-before-return), serialized per session by the
  same `anyio.Lock` map the filesystem store uses. The connection is opened against the
  db file with `check_same_thread=False`-safe usage confined to the lock; the sync
  `sqlite3` work runs inline inside the async method (the filesystem store likewise does
  inline I/O in its async `append`).
- **Rationale**: Preserves FR-006 durability and ordering parity with no new concurrency
  model. `anyio.to_thread.run_sync` is a possible later refinement but is **not** needed
  for parity and adds nothing the filesystem store has.

## R6 — `last_active_at` recency derivation

- **Decision**: `FileCheckpointStore` keeps deriving `last_active_at` from the records
  file mtime; `SqliteCheckpointStore` derives it from the session's **maximum
  `recorded_at`**. Both order listings most-recent-first.
- **Rationale**: SQLite has no per-session file mtime. The latest record's timestamp is
  the faithful "most recent activity" signal. This is a documented, intentional
  difference (spec Edge Cases + Assumptions); the shared contract test asserts **ordering
  by recency**, not timestamp equality between backends.

## R7 — Backend selection (additive, defaulted)

- **Decision**: Add `checkpoint_backend: Literal["file", "sqlite"] = "file"` to
  `StorageConfig` and read it in `_coerce_storage`'s dict branch
  (`value.get("checkpoint_backend", "file")`). `host/assembly.py` builds
  `FileCheckpointStore(root)` by default or `SqliteCheckpointStore(root /
  "checkpoints.sqlite3")` when `"sqlite"`. The artifact store still uses `root`.
- **Rationale**: Default `"file"` makes the change byte-identical for every existing
  embedder (FR-003/FR-004); the SQLite db sits beside the artifacts under the same
  host-chosen root ("both wired together").

## R8 — No data migration

- **Decision**: Backend choice applies to sessions created under that configuration;
  existing on-disk filesystem sessions are **not** migrated into SQLite.
- **Rationale**: Migration is out of scope (spec) and unnecessary for proving the seam;
  it would add risk with no Phase-B value.

## R9 — Drift / packaging obligations (unit 014)

- **Decision**: Update `checkpoint/__init__.py` `__all__` (`CheckpointStore` now the
  Protocol; add `FileCheckpointStore`, `SqliteCheckpointStore`) and the matching
  `docs/api-reference.md` checkpoint section so the `__all__` ↔ api-reference bijection
  test stays green; add a `021` `CHANGELOG.md` entry; no new dependency, so the packaging
  extras test is unchanged.
- **Rationale**: Unit 014's drift contracts fail CI if the public surface and the API
  reference diverge.

## R10 — Deferred to Phase C

- `principal_id` / per-principal scoping and any networked database (Postgres) are **not**
  in this unit; the Protocol stays single-tenant, keyed by `session_id`. Phase C adds a
  real `Authenticator` + per-principal sessions and can add a Postgres backend as another
  implementation of the same Protocol.
