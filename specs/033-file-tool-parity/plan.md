# Implementation Plan: File-Tool Parity for the Baseline Tool Set

**Branch**: `033-file-tool-parity` (main-only autopilot; no dedicated branch) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/033-file-tool-parity/spec.md`

## Summary

Add three additive built-in tools to the **Internal Tool Adapter**
(`src/loopplane/tools/internal.py`) — `edit_file` (surgical unique-string
replacement), `glob_files` (filename pattern matching), and `grep` (regex
content search with `content`/`files_with_matches`/`count` output modes). All
three are reachable **only through the Tool Gateway** (Constitution V) and
**confined to the run working scope** via the adapter's existing `_resolve`
rule. `edit_file` reuses the existing `_write_file` stale-write machinery (the
`self._reads` digest map, `_digest`, the prior-read/unchanged check) unchanged.
The existing `search_files` tool is left intact for back-compat. The change is
purely additive: no gateway, event-bus, loop, or model-boundary change, and no
new dependency.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Standard library only (`pathlib`, `fnmatch`, `re`,
`hashlib`); no new runtime dependency. `anyio` is already used by the adapter.

**Storage**: N/A (in-memory session read-digest map already owned by the adapter)

**Testing**: pytest (offline, deterministic), mirroring
`tests/unit/test_rules_and_tools.py` and existing `InternalToolAdapter` tests

**Target Platform**: Cross-platform library runtime (Windows/macOS/Linux)

**Project Type**: Single project — embeddable Python library/runtime

**Performance Goals**: Interactive single-call latency; bounded result sets via a
documented match/result cap (mirrors the existing `_SEARCH_MATCH_LIMIT = 100`)

**Constraints**: Pure-Python (no external `ripgrep`/grep binary); every path
confined to the run working scope; no leakage of host paths outside the scope

**Scale/Scope**: Three new tool handlers + descriptors in one module, plus
deterministic unit tests; no other module changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I — Spec-First**: PASS. Plan traces to spec 033; tasks will trace to this plan.
- **II — Greenfield**: PASS. New handlers written fresh; no legacy code copied.
- **IV — Runtime Boundary Clarity**: PASS. All logic stays inside the Internal
  Tool Adapter; no reach-through into other components.
- **V — Tool Gateway Ownership**: PASS (key gate). The three tools are added as
  Internal Tool Adapter descriptors/handlers and are resolved, authorized, and
  executed **only** through the Gateway; no bypass path. Errors are returned as
  the gateway error model (`ErrorOutput` / `ErrorCategory.VALIDATION`), not raw
  exceptions.
- **VI — Event Bus**: PASS. No event schema change; tools emit existing
  `TextBlock`/`ErrorOutput` outputs only.
- **VII — Public-Safe**: PASS. No secrets, no internal paths; working-scope
  confinement prevents leaking host paths outside the scope.
- **VIII / IX — No SDK Replacement / Reference-not-clone**: PASS. No framework;
  edit/glob/grep semantics are re-derived in LoopPlane's own adapter.
- **X — Testable Evolution**: PASS. Deterministic unit tests per tool; rollback
  is deletion of the three handlers/descriptors (additive, reversible).

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/033-file-tool-parity/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── tools.md         # Tool input/output contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/loopplane/
├── tools/
│   └── internal.py          # MODIFY: +edit_file, +glob_files, +grep
│                            #   (descriptors + handlers); reuse _resolve,
│                            #   _digest, self._reads; search_files untouched
├── model/
│   └── boundary.py          # USE (unchanged): ToolDescriptor
├── gateway/
│   └── spi.py               # USE (unchanged): AdapterOutput, ErrorOutput
└── errors.py                # USE (unchanged): ErrorCategory.VALIDATION

tests/
└── unit/
    └── test_internal_file_tools.py   # NEW: deterministic offline tests
                                       #   (or extend test_rules_and_tools.py
                                       #    to match the repo's test layout)
```

**Structure Decision**: Single-project library layout. The entire feature is a
local extension of `InternalToolAdapter` in `src/loopplane/tools/internal.py`;
the only other touch is a new (or extended) unit-test module. No new packages,
no frontend, no configuration.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
