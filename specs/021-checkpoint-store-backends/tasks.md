---
description: "Task list for unit 021 — Checkpoint Store Backends"
---

# Tasks: Checkpoint Store Backends

**Input**: Design documents from `specs/021-checkpoint-store-backends/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: REQUIRED (Constitution X). One **shared, parametrized** contract suite drives
both backends through the Protocol; the existing filesystem contract test is retargeted.
Write the shared suite FIRST and confirm it FAILS (SQLite missing) before implementing.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no new dependency**: `sqlite3` is stdlib, so `pyproject.toml`
  and the optional-extras set are unchanged; `tests/contract/test_packaging.py` must
  stay green **without edits** (verified in T017).

---

## Phase 2: Foundational (blocking — extracts the interface every story depends on)

- [ ] T002 Create `src/loopplane/checkpoint/base.py`: the `CheckpointStore` **Protocol**
  (`async append`, `load`, `list_sessions`) and **move `SessionSummary`** here from
  `store.py` (storage-agnostic). Signatures byte-for-byte match today's class.
- [ ] T003 Create `src/loopplane/checkpoint/file.py`: move the existing `CheckpointStore`
  class **verbatim** and rename it `FileCheckpointStore` (import `SessionSummary` from
  `.base`; logic unchanged). **Delete `src/loopplane/checkpoint/store.py`** (no shim).
- [ ] T004 Retype consumers to the Protocol (import source only; signatures unchanged):
  `src/loopplane/controller/controller.py` and `src/loopplane/checkpoint/recorder.py`
  import `CheckpointStore` / `SessionSummary` from `loopplane.checkpoint.base`.
- [ ] T005 Update `src/loopplane/checkpoint/__init__.py`: export `CheckpointStore` (now the
  Protocol), `FileCheckpointStore`, and `SessionSummary` from their new modules; keep all
  existing exports. (The `SqliteCheckpointStore` export is added in T008.)

**Checkpoint**: the package imports; `controller`/`recorder` bind to the Protocol; the
filesystem behavior is unchanged (existing tests still pass once retargeted in T010/T011).

---

## Phase 3: User Story 1 — choose a durable backend behind one interface (P1) 🎯 MVP

**Goal**: two interchangeable backends behind one `CheckpointStore`, selectable by config.

**Independent Test**: one parametrized suite asserts append/load ordering and listing
recency are equivalent across both backends.

- [ ] T006 [P] [US1] `tests/contract/test_checkpoint_sqlite.py` (FAIL first): a **shared,
  parametrized** contract suite over `FileCheckpointStore` and `SqliteCheckpointStore` —
  append→load order + value-equality, corrupt-record skip+report, missing store →
  `([], [])` / `[]`, multi-session recency ordering, and `created_at`/`label` surfaced.
- [ ] T007 [US1] Implement `src/loopplane/checkpoint/sqlite.py` `SqliteCheckpointStore`
  (`db_path: Path`): create the `records` table (per data-model.md); `append` =
  `INSERT serialize_record(record)` + `commit()` before return, per-session `anyio.Lock`;
  `load` = `SELECT ... ORDER BY sequence` → `deserialize_record` with the **same**
  corrupt-skip semantics; `list_sessions` = group by session, meta record for
  `created_at`/`label`, `last_active_at = max(recorded_at)`, most-recent-first.
- [ ] T008 [US1] Add `SqliteCheckpointStore` to `src/loopplane/checkpoint/__init__.py`
  `__all__` and imports (completes the public surface).
- [ ] T009 [US1] Selector wiring: add `checkpoint_backend: Literal["file","sqlite"] =
  "file"` to `StorageConfig` and read it in `_coerce_storage` (`src/loopplane/host/config.py`);
  in `src/loopplane/host/assembly.py` build `SqliteCheckpointStore(root /
  "checkpoints.sqlite3")` when `"sqlite"`, else `FileCheckpointStore(root)`.

**Checkpoint**: T006 passes for both backends; a host can select either via config.

---

## Phase 4: User Story 2 — existing deployments are unaffected (P2)

**Goal**: the default (filesystem) path is byte-identical; no new dependency.

**Independent Test**: default config builds the filesystem store; the existing checkpoint
behavior and the no-store path are unchanged.

- [ ] T010 [US2] Retarget `tests/contract/test_checkpoint.py` — the filesystem store's own
  contract test — to construct `FileCheckpointStore` (import + ~13 construction sites).
- [ ] T011 [P] [US2] Sweep the remaining `CheckpointStore(...)` construction sites to
  `FileCheckpointStore(...)`: `tests/contract/test_run_lifecycle.py`,
  `tests/integration/test_gating_matrix.py`, `tests/integration/test_review_regressions.py`,
  `tests/integration/test_us3_resume.py`, `tests/integration/test_us4_memory_skills.py`,
  and `docs/quickstart.md`.
- [ ] T012 [US2] Assert the default: a small test that the default `StorageConfig`
  assembles a `FileCheckpointStore` and the no-store path is unchanged (in the contract
  suite or an assembly test).

---

## Phase 5: User Story 3 — corrupt/missing data degrades safely in both backends (P3)

**Goal**: resilience parity — corrupt record skipped+reported; missing store → empty.

**Independent Test**: the parametrized corrupt/missing cases pass for both backends.

- [ ] T013 [US3] Confirm the shared suite (T006) exercises **corrupt-record skip** and
  **missing-store → empty** for **both** backends (parametrized) and that
  `SqliteCheckpointStore` matches the filesystem semantics; add cases if any gap.

---

## Phase 6: Polish — drift contracts, changelog, board, gates

- [ ] T014 [P] Update `docs/api-reference.md` checkpoint section to match `__all__`:
  `CheckpointStore` is now the Protocol; add `FileCheckpointStore` and
  `SqliteCheckpointStore` (api-reference drift contract).
- [ ] T015 [P] `CHANGELOG.md`: add a `021` entry under Added (Keep-a-Changelog structure).
- [ ] T016 [P] `docs/loopplane-agent-board.md`: add the **021** roadmap row + a status
  evidence note; refresh the stale §3 footer banner and §4 "Active Feature" so they
  reflect 020 + 021 (not "000–019 complete").
- [ ] T017 Run the gates: `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy`, `uv run pytest` — all green; `uv build` succeeds; confirm the packaging
  extras test is unchanged and the public-safety scan is clean.
- [ ] T018 Final review: confirm runtime core/contracts unchanged and `principal_id`/Postgres
  deferred; record unit 021 on the board; commit (`021 implement`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T005)** precede everything (the Protocol and the
  moved filesystem class are prerequisites).
- **US1 (T006–T009)** is the MVP. T006 (test) is written first and FAILS until T007/T008
  exist. T009 (selector) depends on T007/T008.
- **US2 (T010–T012)** depends on Foundational (the rename target `FileCheckpointStore`
  must exist). It is otherwise mechanical.
- **US3 (T013)** depends on T006/T007 (it asserts the parity already built there).
- **Polish (T014–T018)** depends on the public surface (T008) and the implemented backends.

### Parallel opportunities

- T001 is independent `[P]`.
- T011 (construction-site sweep) is `[P]` across disjoint test/doc files.
- T014/T015/T016 (api-reference / changelog / board) are independent `[P]` files.

## Notes

- The SQLite store reuses `records.py` (`serialize_record`/`deserialize_record`/
  `SessionMetaRecord`) — **one** record encoding and **one** corruption story across both
  backends. No second format.
- Runtime core, event bus, loop, and gateway are **unchanged**; only the checkpoint
  package layout, the consumers' import source, and the host storage config change.
- No new runtime dependency (`sqlite3` is stdlib); the packaging extras set is unchanged.
- Rollback = delete `sqlite.py` + the `checkpoint_backend` field, collapse `base.py` +
  `file.py` back into `store.py`, and revert the construction-site renames and the
  api-reference/changelog edits.
