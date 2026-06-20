# Implementation Plan: File-Edit Undo

**Branch**: `054-file-undo` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/054-file-undo/spec.md`

**Boundary review**: **ADDITIVE — no ADR, no contract change, no consult** (confirmed by the
Tier-3 design workflow as the lightest unit). Entirely contained in the Internal Tool Adapter +
tests, reusing the working-scope resolver + the stale-write guard. The single design refinement
vs the board's preliminary wording: the gate is an **`InternalToolAdapter` constructor param**
(`max_file_snapshots: int = 0`, the existing `memory_store` injection pattern), **not** a
`RuntimeConfig` field — because `InternalToolAdapter` is **caller-constructed and passed via
`RuntimeConfig.tool_adapters`** (assembly never builds it), so a `RuntimeConfig` flag would be a
dead, un-wired knob. The ctor param is the correct, minimal, default-off gate (Simplicity First +
Existing Patterns First).

## Summary

When enabled, the three mutating file tools (`write_file` / `edit_file` / `notebook_edit`)
**snapshot the file's prior raw bytes** before overwriting an existing file, into a bounded
per-run, per-resolved-path history on the adapter (`self._snapshots`, the unit-044 `self._todos`
/ unit-033 `self._reads` pattern). A new `undo_file` Gateway tool restores the most-recent
snapshot (most-recent-first), **re-syncs the stale-write guard** (`self._reads`) to the restored
content, and pops the snapshot. Bounded by `max_file_snapshots` (per-run cap, oldest dropped);
confined to the working scope (the existing `_resolve`); faithful for binary files (raw bytes).
Gated by `InternalToolAdapter(max_file_snapshots: int = 0)` (default 0 = off → no snapshot
side-effect, `undo_file` not in `describe()`, byte-identical). No new module, no `RunContext` /
Protocol / factory, no loop/controller/assembly/config change, no event-schema/content-model
change, no ADR.

## Technical Context

**Language/Version**: Python 3.11+ (`loopplane`); stdlib only.

**Primary Dependencies**: none new — reuses `InternalToolAdapter` internals (`_resolve`, the
`self._reads` stale-write guard, `_digest`), the Tool Gateway SPI, `TextBlock`/`ErrorOutput`.

**Storage**: in-memory per-run snapshot history on the adapter; no persistence (durable
artifact-backed undo is a deferred follow-up, out of scope).

**Testing**: pytest, offline — mirror `tests/unit/test_internal_file_tools.py` /
`test_todo_tool.py` (a `RunContext(session_id, working_scope=tmp_path)`, an async `_invoke`
collector); assert undo restores text + binary, the multi-step walk-back, the cap, the
stale-write-guard re-sync, default-off (no `undo_file` + no snapshot), and out-of-scope/unknown
errors.

**Target Platform**: cross-platform library.

**Constraints**: additive / reuse-first; default-off byte-identical; Gateway-only (V); working-
scope-confined; raw-bytes faithful; no event-schema/content-model change (VI); no new dependency;
no ADR.

**Scale/Scope**: changes confined to `src/loopplane/tools/internal.py` (the `_snapshots` dict +
the ctor param + a conditional snapshot in the 3 mutating handlers + the `undo_file` handler +
descriptor + `describe()` gating) + `docs/api-reference.md` (only if a new public name is
exported — none expected; `undo_file` is a descriptor, not a new export) + tests. Smallest unit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-008. ✅
- **III. Agent Harness Before Loop Automation**: A bounded, opt-in, model-invoked capability
  (default-off); not the loop-automation layer. ✅
- **IV. Runtime Boundary Clarity**: No boundary touched — adapter-internal per-session state only;
  no `RunContext`/Protocol/loop/controller change. ✅
- **V. Tool Gateway Ownership**: `undo_file` dispatches only through the Gateway; the snapshot is a
  side-effect inside the existing Gateway-owned file handlers. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change. ✅
- **X. Testable Evolution**: Additive; default-off (`max_file_snapshots = 0`) byte-identical;
  reversible; offline-tested. ✅

**Result**: PASS — purely additive, default-off, no boundary crossing, no ADR. Complexity Tracking
not required.

## Project Structure

### Documentation (this feature)

```text
specs/054-file-undo/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/undo-tool.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/tools/internal.py     # MODIFIED: + self._snapshots + max_file_snapshots ctor param
                                    #   + a conditional pre-write snapshot in write_file / edit_file
                                    #   / notebook_edit + the undo_file handler + descriptor +
                                    #   describe() gating. (No new file; the 044/046 pattern.)
tests/unit/test_file_undo.py        # NEW: offline coverage
```

**Structure Decision**: Mirror units 044 (`todo_write`, `self._todos`) and 046 (`notebook_edit`)
— add to `InternalToolAdapter` in place, no new module. The gate + state are ctor-injected like
`memory_store`. The mutating handlers gain a single guarded line (`if self._max_file_snapshots:
snapshot before write`), so the off-path is byte-identical. `undo_file` reuses `_resolve` +
re-syncs `self._reads`.

## Complexity Tracking

> No Constitution violations — section intentionally empty. The lightest additive class in the
> codebase (per-session adapter state); default-off; no ADR.
