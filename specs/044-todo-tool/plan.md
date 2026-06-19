# Implementation Plan: Agent Task List (`todo_write`)

**Branch**: `044-todo-tool` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/044-todo-tool/spec.md`

## Summary

Add a `todo_write` baseline tool to the Internal Tool Adapter so the agent can record
and update an ordered, per-run list of todo items (each a `content` string + a
`pending` / `in_progress` / `completed` status). Calls use set-the-whole-list (replace)
semantics; the list is held in the adapter instance keyed by `session_id` (mirroring the
existing `_reads` map), validated on write, and returned to the agent as a `TextBlock`
result. Entirely additive and confined to `src/loopplane/tools/internal.py` plus tests —
no change to `RunContext`, the controller, host assembly, the Tool Gateway pipeline, the
event schema, or the content model.

## Technical Context

**Language/Version**: Python 3.11+ (existing `loopplane` package)

**Primary Dependencies**: none new — standard library only (the tool is a pure in-memory
adapter handler; reuses `ToolDescriptor`, `AdapterOutput`/`TextBlock`/`ErrorOutput`,
`RunContext`, `ErrorCategory` already imported in `internal.py`)

**Storage**: in-memory per-run state in the adapter instance (`dict[str, list[TodoItem]]`
keyed by `session_id`); no persistence beyond the existing checkpoint mechanism

**Testing**: pytest (offline; new `tests/unit/test_todo_tool.py`)

**Target Platform**: cross-platform library (same as the runtime)

**Project Type**: single project (library + tests)

**Performance Goals**: negligible — O(n) over a bounded item list per call

**Constraints**: additive / reuse-first; no event-schema (`SCHEMA_VERSION`) or
content-model change; reachable only through the Tool Gateway; no new dependency; no ADR

**Scale/Scope**: one new descriptor + one handler + one per-session map; bounded list
(max 100 items)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Implementation traces to `spec.md` (FR-001…FR-011) and this plan. ✅
- **IV. Runtime Boundary Clarity**: The tool is a handler inside the existing Internal
  Tool Adapter; it owns only its per-session list. No new component, no boundary moved. ✅
- **V. Tool Gateway Ownership**: `todo_write` is reachable only via the Gateway like every
  other internal tool (registered through `describe()` / dispatched in `invoke()`); it
  performs no out-of-gateway dispatch. ✅
- **VI. Event Bus Ownership**: No event-schema or `SCHEMA_VERSION` change; the result is an
  ordinary `TextBlock` tool output on the existing stream; the metadata-only observability
  overlay (010) is unchanged. ✅
- **IX. Reference, Not Clone**: The concept (a TodoWrite-style task list) is borrowed from
  the reference harnesses but re-derived here; no implementation detail is copied. ✅
- **X. Testable Evolution**: Additive and reversible (delete the descriptor + handler +
  map to revert); fully covered by new offline unit tests; runs that never call it are
  byte-identical. ✅

**Result**: PASS — no violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/044-todo-tool/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── todo_write-tool.md   # Tool contract (input schema + result/error behavior)
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── internal.py          # MODIFIED: add `todo_write` descriptor + `_todo_write` handler
                         #           + `self._todos` per-session map + dispatch entry

tests/unit/
└── test_todo_tool.py    # NEW: offline coverage of the handler + descriptor

tests/                   # MODIFIED (only if needed): any existing test asserting the
                         #   exact internal descriptor set adds `todo_write`
```

**Structure Decision**: Single-project library change. The entire feature is local to the
Internal Tool Adapter (`src/loopplane/tools/internal.py`), reusing its established
per-session-state pattern (`self._reads`) and its `describe()` / `invoke()` contract. No
new module, package, wiring, or dependency.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
