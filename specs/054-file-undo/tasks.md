# Tasks: File-Edit Undo

**Feature**: 054-file-undo | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive, confined to `src/loopplane/tools/internal.py` + tests (the 044/046 pattern;
no new module). Gate = `InternalToolAdapter(max_file_snapshots: int = 0)` ctor param (the
`memory_store` injection shape); default 0 = off, byte-identical. No RunContext/Protocol/factory,
no loop/controller/assembly/config change, no event-schema/content-model change, no ADR.

**Tests**: requested (TDD-friendly; mirror `tests/unit/test_internal_file_tools.py` / `test_todo_tool.py`).

## Phase 1: Foundational

- [x] T001 Add the gate + state to `InternalToolAdapter.__init__` in
  `src/loopplane/tools/internal.py`: a `max_file_snapshots: int = 0` keyword param (the
  `memory_store` injection shape) stored as `self._max_file_snapshots`, and
  `self._snapshots: dict[tuple[str, str], list[bytes]] = {}` (per-(session_id, resolved_path)
  most-recent-first stack). A small `_snapshot(self, key, data: bytes)` helper that pushes +
  enforces the cap (oldest dropped when total exceeds `max_file_snapshots`).

## Phase 2: User Story 1 — Snapshot + undo (P1) 🎯 MVP

- [x] T002 [US1] In `write_file`, `edit_file`, and `notebook_edit`, BEFORE overwriting an
  **existing** file, add one guarded line: `if self._max_file_snapshots > 0` → read the file's
  prior **raw bytes** and `self._snapshot((session_id, resolved_path), prior)`. A brand-new file
  takes no snapshot. The off-path (cap 0) is byte-identical (no read, no snapshot).
- [x] T003 [US1] Add the `undo_file` ToolDescriptor (input `{path: string}`, required; `read_only`
  + `concurrency_safe` both False) to `_DESCRIPTORS` **gated**: `describe()` includes it only when
  `self._max_file_snapshots > 0`. Register `"undo_file": self._undo_file` in the `invoke` dispatch.
  Implement `_undo_file`: `_resolve` the path (working-scope confinement → normalized error on
  escape); pop the most-recent snapshot for `(session_id, resolved_path)`; if none → a clear
  "nothing to undo for <path>" TextBlock; else `write_bytes` the snapshot, **re-sync**
  `self._reads[(session_id, str(resolved))] = _digest(snapshot_bytes)`, and yield a TextBlock
  confirming the restore.

## Phase 3: User Story 2 + 3 — bounded / scoped / default-off (P2/P3)

- [x] T004 [US2] Write `tests/unit/test_file_undo.py` (mirror the file-tools harness): undo a
  write (restores prior content); multi-step walk-back (modify twice → undo twice → step-by-step;
  third undo → "nothing to undo"); stale-write-guard re-sync (after undo, a following `edit_file`
  is accepted, not rejected as stale); binary-faithful (snapshot + undo a non-UTF-8 file →
  byte-for-byte); the cap (exceed `max_file_snapshots` → oldest dropped, count bounded);
  out-of-scope (`..`/absolute) + unknown-path → normalized error.
- [x] T005 [US3] Add the default-off tests: a default `InternalToolAdapter()` (cap 0) → `describe()`
  has NO `undo_file`, and a write/edit takes no snapshot (byte-identical); an enabled adapter
  (`max_file_snapshots=N`) → `describe()` includes `undo_file`.

## Phase 4: Polish & Cross-Cutting

- [x] T006 Search `tests/` for any assertion of the exact baseline/internal descriptor name set;
  ensure it still holds for a DEFAULT adapter (cap 0 → no `undo_file`), and add an enabled-adapter
  case if appropriate. Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src,
  strict), `pytest` (full suite — additive proof + default-off byte-identity). ALSO confirm the
  structural audits stay green: `test_no_execution_path_outside_the_gateway` + `test_public_safety`.

## Dependencies

- T001 → T002, T003. T002/T003 → T004, T005. All → T006 (gates last).

## Implementation strategy

- Small + single-file (internal.py) — likely an inline implement (no fork needed). ULTRACODE: run
  the four gates + the two structural audits + a focused adversarial check (default-off
  byte-identity, working-scope confinement of `undo_file`, raw-bytes faithfulness, stale-guard
  re-sync, public-safe errors) before committing; GO/0 blocking.
- All additive; default-off (`max_file_snapshots = 0`) byte-identical; no ADR.

## Cross-Artifact Analysis (gate)

**Result: PASS** (analyze, 2026-06-20) — 0 critical, 0 high, 2 low (informational). 100%
requirement coverage (FR-001..FR-008 and SC-001..004 each map to ≥1 task); every task traces to a
requirement/design item; spec ↔ plan ↔ research ↔ data-model ↔ contract ↔ tasks agree (the
`max_file_snapshots` ctor gate; `self._snapshots` per-(session,path) raw-bytes history; the guarded
pre-write snapshot in the 3 mutating tools; the gated `undo_file` restore + stale-write-guard
re-sync; working-scope confinement; the cap). **Boundary review: additive** — no new
RunContext/Protocol/factory, no loop/controller/assembly/event/content change, no ADR; default-off
(`max_file_snapshots = 0`) byte-identical. No Constitution violation (III/IV/V/VI/X). Low notes are
informational: (1) the gate is a ctor param (not a RuntimeConfig field) — a deliberate, sound
refinement because `InternalToolAdapter` is caller-built/passed via `tool_adapters` (a RuntimeConfig
field would be a dead knob); documented in plan + research; (2) binary-faithfulness requires raw
`read_bytes`/`write_bytes` (not the lossy text round-trip the edit path uses) — captured in FR-006 +
the design. **Cleared for `/speckit-implement`.**
