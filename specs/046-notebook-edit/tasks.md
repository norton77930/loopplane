# Tasks: Notebook Editing (`notebook_edit`)

**Feature**: 046-notebook-edit | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive, confined to `src/loopplane/tools/internal.py` + `tests/unit/test_notebook_edit.py`.
No event-schema/content-model change, no new dependency (stdlib `json`), no ADR.

**Tests**: requested (TDD-friendly ordering).

## Phase 1: Foundational (blocking prerequisites)

- [x] T001 Add `import json` and the `notebook_edit` `ToolDescriptor` (input schema per [contracts/notebook_edit-tool.md](contracts/notebook_edit-tool.md): `path`, `mode` ∈ {replace,insert,delete}, `index`, optional `source`, optional `cell_type`; `read_only=False`) to `_DESCRIPTORS` in `src/loopplane/tools/internal.py`.
- [x] T002 Register `"notebook_edit": self._notebook_edit` in the `invoke` dispatch dict in `src/loopplane/tools/internal.py`.

## Phase 2: User Story 1 — Edit a notebook cell (P1) 🎯 MVP

**Goal**: replace / insert / delete a cell by index, preserving the rest of the notebook.

**Independent test**: read a 2-cell `.ipynb`, replace cell 0; only cell 0 changes; cell 1 + nbformat preserved; still a valid notebook.

- [x] T003 [US1] Write `tests/unit/test_notebook_edit.py` (mirror `tests/unit/test_internal_file_tools.py` harness): replace a cell's source (other cells/outputs/nbformat preserved); insert a markdown cell at an index (later cells shift); insert at `index == len(cells)` appends; delete a cell (order preserved). (Red until T004.)
- [x] T004 [US1] Implement the `_notebook_edit` async handler in `src/loopplane/tools/internal.py`: resolve `path` via `_resolve` (working scope); apply the `edit_file` stale-write guard via `self._reads` (must have been read this session + unchanged); parse the file as JSON and validate it is a notebook (a dict with a list `cells`); apply `mode` by `index` (replace sets `cells[index].source`; insert builds a minimal valid `code`/`markdown` cell and inserts at `index` allowing `== len`; delete removes `cells[index]`); validate the index range and required fields (`source` for replace/insert, `cell_type` for insert), yielding `ErrorOutput(VALIDATION)` WITHOUT writing on any failure; on success write the re-serialized JSON, refresh `self._reads` digest, and yield a `TextBlock` confirmation. Make T003 pass.

## Phase 3: User Story 2 — Safe, guarded edits (P2)

- [x] T005 [US2] Extend `tests/unit/test_notebook_edit.py`: no-prior-read rejected; changed-since-read rejected; out-of-range index rejected; malformed/non-notebook JSON rejected — each a `VALIDATION` error with the file unchanged.

## Phase 4: User Story 3 — Governed & scoped (P3)

- [x] T006 [US3] Extend `tests/unit/test_notebook_edit.py`: a path outside the working scope is rejected (nothing written); `InternalToolAdapter().describe()` includes `notebook_edit` with `read_only is False`.

## Phase 5: Polish & Cross-Cutting

- [x] T007 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict), `pytest` (full suite — additive proof). Fix any issue introduced by this unit.

## Dependencies

- T001, T002 → block Phase 2+.
- T003 → T004 (TDD). T004 → T005, T006. T007 last.

## Parallel opportunities

- Minimal: one source file + one test file. T005/T006 extend the same test file → sequential.

## Implementation strategy

- **MVP = Phase 1 + Phase 2 (US1)**: replace/insert/delete working with the core test set.
  US2/US3 are guard/scope verification over the same handler.
- All changes additive; confined to internal.py + the new test file.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 1 low (informational). 100%
requirement coverage (FR-001..FR-007 and SC-001..003 each map to ≥1 task); every task traces
to a requirement/design item; spec ↔ plan ↔ data-model ↔ contract ↔ tasks agree (notebook_edit;
replace/insert/delete by index; stdlib-json round-trip preserving non-targeted content; reuse
of `_resolve` + the `edit_file` stale-write guard). No Constitution violations (additive,
Gateway-only V, no event-schema/content-model change VI, reference-not-clone IX, testable X, no
ADR). The one low note is informational: cell selection is by index in v1 (selection by cell id
is a deferred refinement). **Cleared for `/speckit-implement`.**
