# Implementation Plan: Checkpoint Store Backends

**Branch**: `021-checkpoint-store-backends` (main-only) | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/021-checkpoint-store-backends/spec.md`

## Summary

Turn the checkpoint store from one concrete filesystem class into a **`CheckpointStore`
Protocol** with two interchangeable implementations: the existing filesystem store —
moved verbatim into `FileCheckpointStore` and kept as the **default** — and a new,
optional **`SqliteCheckpointStore`** that proves the seam is real. The Protocol carries
exactly today's public surface (`async append`, `load`, `list_sessions` + `SessionSummary`),
so the runtime consumers (`RuntimeController`, `SessionRecorder`, host assembly) depend
only on the interface and **no method signature changes**. The SQLite store uses only the
standard-library `sqlite3` (no new runtime dependency, fully offline), **reuses the
existing record encoding** (`serialize_record`/`deserialize_record`/`SessionMetaRecord`),
and preserves the same corrupt-record skipping and commit-before-return durability. A
backend is chosen by an **additive, defaulted** field on `StorageConfig`
(`checkpoint_backend="file"` by default), so every existing embedder is byte-identical.
`principal_id`/multi-user and any networked database (Postgres) are deferred to Phase C.
The naming mirrors unit 020 (`ModelBoundary` Protocol ↔ `AnthropicModel`/`OpenAIModel`).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: **none new** — the SQLite store uses the standard-library
`sqlite3`. The runtime core install stays `anyio + pydantic + jsonschema`; no optional
extra is introduced (unlike 020, SQLite needs none).

**Storage**: filesystem (default, unchanged) and a local SQLite database file under the
host-chosen storage root (`<root>/checkpoints.sqlite3`); both backends store the same
serialized record stream.

**Testing**: `pytest`. One **shared, parametrized contract suite** drives both backends
through the Protocol (append/load ordering, corrupt-record skipping, missing-store →
empty listing, recency-ordered listing). The existing filesystem contract test is
retargeted to `FileCheckpointStore`. All tests are offline.

**Target Platform**: a Python library (embeddable runtime)

**Project Type**: library — a refactor of `src/loopplane/checkpoint/` (one module split
into `base`/`file`/`sqlite`) plus a defaulted selector on the host storage config.

**Performance Goals**: append is durable (flushed/committed before return); writes are
serialized per session; latency is bound by local disk, unchanged from today.

**Constraints**: no runtime-core or public-contract change; Protocol method signatures
**unchanged**; no new runtime dependency; the interface is **single-tenant** (keyed by
`session_id`); default behavior is byte-identical when the selector is unset.

**Scale/Scope**: split one module into three; add one backend (~1 file); add one
`StorageConfig` field + `_coerce_storage` + assembly branch; retype ~20 construction
sites to `FileCheckpointStore`; add the shared parametrized contract test; edit the API
reference, the changelog, and the agent board.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–010). | PASS |
| II — Greenfield | The Protocol and the SQLite store are written fresh; the filesystem store is moved unchanged, not copied from legacy. | PASS |
| III — Harness before automation | Pure foundation infrastructure (durable checkpoint); adds **no** loop automation. | PASS |
| IV — Boundary Clarity | **Strengthens** the Checkpoint boundary: it becomes a declared interface with documented implementations; consumers reach only through it. | PASS (headline) |
| V — Tool Gateway Ownership | Untouched — no tool resolution/execution involved. | PASS |
| VI — Event Bus Ownership | Untouched — the recorder still records via the same append path; no event-bus change. | PASS |
| VII — Public-Safe | A local SQLite file holds public-safe session records (same content as today's files); no secret, path, or internal name is committed. | PASS (FR-009) |
| VIII — No SDK Replacement | `sqlite3` is the stdlib database module, not an agent framework; the runtime core is unchanged. | PASS (FR-008) |
| IX — Reference, not clone | N/A — internal refactor; no external reference cloned. | PASS |
| X — Testable Evolution | One shared contract suite covers both backends; rollback = restore the single `CheckpointStore` filesystem class and delete `sqlite.py`. | PASS (FR-006) |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/021-checkpoint-store-backends/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── checkpoint-store.md            # the Protocol: methods, semantics, parity obligations
│   └── backend-selection-boundary.md  # defaulted selector, no core change, api-reference/__all__ drift, no new dep
├── checklists/requirements.md
└── tasks.md                           # created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/checkpoint/
├── base.py        # NEW — CheckpointStore Protocol + SessionSummary (moved from store.py)
├── file.py        # NEW — FileCheckpointStore (the existing class, moved & renamed; logic unchanged)
├── sqlite.py      # NEW — SqliteCheckpointStore (stdlib sqlite3; reuses records.py encoding)
├── records.py     # unchanged — serialize_record / deserialize_record / *Record types
├── recorder.py    # EDIT — import CheckpointStore from .base (Protocol); signatures unchanged
├── rebuild.py     # unchanged
├── __init__.py    # EDIT — export CheckpointStore (Protocol), FileCheckpointStore, SqliteCheckpointStore
└── store.py       # REMOVED — split into base.py + file.py (no shim)

tests/
├── contract/
│   ├── test_checkpoint.py          # EDIT — retarget construction to FileCheckpointStore
│   └── test_checkpoint_sqlite.py   # NEW — shared parametrized contract over both backends
└── integration/                    # EDIT — retype CheckpointStore(...) → FileCheckpointStore(...)
```

Edited (additive / mechanical, traceable):

```text
src/loopplane/controller/controller.py   # import CheckpointStore/SessionSummary from .base (Protocol)
src/loopplane/host/config.py             # StorageConfig.checkpoint_backend: Literal["file","sqlite"]="file" + _coerce_storage
src/loopplane/host/assembly.py           # build FileCheckpointStore (default) or SqliteCheckpointStore per selector
docs/quickstart.md                       # CheckpointStore(...) → FileCheckpointStore(...)
docs/api-reference.md                    # checkpoint section: + FileCheckpointStore, SqliteCheckpointStore (CheckpointStore now the Protocol)
CHANGELOG.md                             # + a 021 Added entry
docs/loopplane-agent-board.md            # + the 021 row + audit; refresh stale "020/021" banners
tests/contract/test_run_lifecycle.py, tests/integration/test_gating_matrix.py,
tests/integration/test_review_regressions.py, tests/integration/test_us3_resume.py,
tests/integration/test_us4_memory_skills.py   # CheckpointStore(...) → FileCheckpointStore(...)
```

**Structure Decision**: Keep everything inside the existing `src/loopplane/checkpoint/`
package. `base.py` holds the Protocol plus the storage-agnostic `SessionSummary`;
`file.py` and `sqlite.py` are the two concrete backends; `records.py` (the shared
encoding) is reused by both. The runtime depends on `checkpoint.base.CheckpointStore`;
only `host/assembly.py` names a concrete class, selecting it from
`StorageConfig.checkpoint_backend` (default `"file"`). The SQLite database lives at
`<storage.root>/checkpoints.sqlite3`, beside the artifact store under the same root.

## Phases

- **Phase 0 — Research** (`research.md`): Protocol vs ABC for the seam; the naming
  convention (020 precedent); the SQLite schema (one `records` table holding the reused
  serialized record line, ordered by `(session_id, sequence)`); reusing the record
  encoding + corrupt-record skipping; commit-before-return durability and per-session
  serialization; the `last_active_at` recency-derivation difference; the defaulted
  `checkpoint_backend` selector; the no-migration decision; and the api-reference/`__all__`
  drift obligation (unit 014).
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the Protocol and
  the two backends; `SessionSummary`; the SQLite table shape; the `StorageConfig`
  selector; the interface contract and the integration boundary; and a quickstart that
  swaps backends behind the same Protocol.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — write the shared parametrized contract
  test first (FAIL), then extract `base.py` (Protocol) and move `file.py`
  (`FileCheckpointStore`), then implement `sqlite.py`, then retype the consumers and add
  the selector wiring, then sweep the ~20 construction sites, then the api-reference /
  changelog / board updates; run all gates.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
