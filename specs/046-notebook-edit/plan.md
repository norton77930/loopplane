# Implementation Plan: Notebook Editing (`notebook_edit`)

**Branch**: `046-notebook-edit` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/046-notebook-edit/spec.md`

## Summary

Add a `notebook_edit` baseline tool to the Internal Tool Adapter that replaces, inserts, or
deletes a single Jupyter `.ipynb` cell by index within the run's working scope. The notebook
is parsed and re-serialized as JSON with the standard library (no Jupyter dependency); all
non-targeted content (other cells, outputs, metadata, `nbformat`) is preserved by
round-tripping the parsed document. Edits reuse the existing path-scope confinement
(`_resolve`) and the `edit_file` stale-write guard (`self._reads`). Entirely additive and
confined to `src/loopplane/tools/internal.py` plus tests — mirroring unit 044.

## Technical Context

**Language/Version**: Python 3.11+ (`loopplane`)

**Primary Dependencies**: none new — standard-library `json` (added to `internal.py`); reuses
`_resolve`, the `_reads` stale-write guard, `ToolDescriptor`, `TextBlock`/`ErrorOutput`,
`ErrorCategory`

**Storage**: edits the `.ipynb` file in place within the working scope; no other persistence

**Testing**: pytest (offline; new `tests/unit/test_notebook_edit.py` with a small in-tmp `.ipynb`)

**Target Platform**: cross-platform library

**Project Type**: single project (library + tests)

**Constraints**: additive / reuse-first; reachable only via the Gateway; confined to the
working scope; stale-write guarded; no event-schema/content-model change; no ADR

**Scale/Scope**: one new descriptor + one handler + an `import json`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007. ✅
- **IV. Runtime Boundary Clarity**: A handler inside the existing Internal Tool Adapter; no
  new component. ✅
- **V. Tool Gateway Ownership**: `notebook_edit` is reachable only via the Gateway like every
  internal tool; registered in `describe()` / dispatched in `invoke()`. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change; the
  result is an ordinary `TextBlock`. ✅
- **IX. Reference, Not Clone**: The notebook-edit concept is re-derived; `.ipynb` JSON is the
  public Jupyter format, not copied harness code. ✅
- **X. Testable Evolution**: Additive and reversible (drop the descriptor + handler); the
  `edit_file` stale-write guard + working-scope confinement are reused unchanged; offline
  tests. ✅

**Result**: PASS — no violations; no ADR. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/046-notebook-edit/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/notebook_edit-tool.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── internal.py          # MODIFIED: add `import json`, the `notebook_edit` descriptor,
                         #           the `_notebook_edit` handler, and the dispatch entry

tests/unit/
└── test_notebook_edit.py   # NEW: offline coverage (replace/insert/delete, guards, scope)
```

**Structure Decision**: Single-project library change, local to the Internal Tool Adapter
(`src/loopplane/tools/internal.py`), reusing `_resolve` (scope confinement) and the
`self._reads` stale-write guard exactly as `edit_file` does. No new module, wiring, or
dependency.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
