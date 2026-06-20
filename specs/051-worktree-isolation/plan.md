# Implementation Plan: Worktree Isolation

**Branch**: `051-worktree-isolation` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/051-worktree-isolation/spec.md`

**Boundary review (FR-003 / FR-009)**: **ADDITIVE — no new ADR, no contract break, no maintainer
consult needed.** Worktrees live under a managed subdirectory of the working scope, so the 001/002
working-scope confinement is **preserved, not changed**. Unlike 048/049/050, worktree operations
are **synchronous git/filesystem ops — no concurrency task group is needed**; the per-run manager
is a plain registry + an injectable git runner. Threading reuses the 048/049/050 neutral-context-
Protocol pattern so the controller/loop never import the tools layer.

## Summary

Add agent-facing worktree tools (`worktree_create` / `worktree_list` / `worktree_remove`). A
per-run `WorktreeManager` (new, `loopplane.tools.worktree`) holds a registry (`worktree_id →
path + branch`), the per-run cap, the working scope, and an **injectable git runner** (production:
the existing shell-execution path running `git -C <scope> worktree …`; tests: a throwaway git repo
fixture / a fake runner). `worktree_create` runs `git worktree add` under a managed area of the
working scope (`<scope>/.loopplane-worktrees/<id>`), returns the id + path; `worktree_list`
enumerates the registry; `worktree_remove` runs `git worktree remove` + prunes. Gated by
`RuntimeConfig.max_worktrees` (default `0` = off, byte-identical). Bounded (count cap), contained
(non-git / git failure / bad input → normalized public-safe error, never a raise),
working-scope-confined (a path escaping the scope is rejected), lifecycle-bound (managed worktrees
removed at the run/session scope exit). Threaded as `RunContext.worktrees` via a neutral
`WorktreeManager` Protocol in `loopplane.context` (controller stays tool-agnostic). No
event-schema / content-model change; no new dependency.

## Technical Context

**Language/Version**: Python 3.11+; the existing shell-execution path (`anyio` subprocess) for git.

**Primary Dependencies**: none new — reuses the `run_command`-style shell executor, the
working-scope confinement, and the 048/049/050 per-run-manager + neutral-Protocol threading.

**Storage**: in-memory per-run registry; the worktrees themselves are on-disk git checkouts under
the managed area, removed at scope exit (no persistence beyond the run).

**Testing**: pytest, offline — a throwaway `git init` repo fixture (or an injected fake runner);
assert isolation (main tree unchanged), list/remove, caps, confinement rejection, containment,
lifecycle cleanup, and default-off byte-identity.

**Target Platform**: cross-platform library (git required at runtime only when the feature is on).

**Constraints**: additive / reuse-first; default-off byte-identical; Gateway-only tools (V);
**working-scope confinement preserved** (001/002 — worktrees under a managed area of the scope);
no event-schema/content-model change (VI); no new dependency; no new ADR.

**Scale/Scope**: a new manager module + 3 tools + an additive `RunContext.worktrees` field + the
048/049/050-style controller/dispatcher/host/assembly wiring (manager build + cleanup at scope
exit) + a `RuntimeConfig.max_worktrees` gate + tests. Simpler than 048-050 (no task group).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-009. ✅
- **III. Agent Harness Before Loop Automation**: A bounded, opt-in, model-invoked autonomy
  primitive (default-off); not the reserved outer loop-automation layer. ✅
- **IV. Runtime Boundary Clarity**: The manager is threaded via a neutral context Protocol (no
  tools import); worktrees stay within the working scope (the 001/002 confinement is preserved). ✅
- **V. Tool Gateway Ownership**: The three tools dispatch only through the Gateway; git runs via
  the existing shell-execution seam within the working scope. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change. ✅
- **X. Testable Evolution**: Additive; default-off (`max_worktrees = 0`) byte-identical;
  reversible; offline-tested (a throwaway git repo / a fake runner). ✅

**Result**: PASS — additive; the working-scope confinement is preserved (worktrees under a managed
area of the scope), so **no boundary crossing, no new ADR**, no breaking 001/002 contract change.
Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/051-worktree-isolation/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/worktree-tools.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── worktree.py          # NEW: WorktreeManager (registry + injectable git runner + cleanup) +
                         #      the 3 tools (a WorktreeToolsAdapter); make_worktree_manager[_factory]

src/loopplane/context.py            # MODIFIED: additive RunContext.worktrees + a neutral
                                    #   WorktreeManager Protocol (controller imports this)
src/loopplane/controller/{controller,dispatcher}.py   # MODIFIED: thread the manager (opaque
                                    #   factory; no loopplane.tools import); cleanup at scope exit
src/loopplane/host/{host,assembly,config}.py   # MODIFIED: build/inject the factory + the
                                    #   RuntimeConfig.max_worktrees gate; cleanup() at scope exit
src/loopplane/tools/__init__.py + docs/api-reference.md   # MODIFIED: export + document

tests/unit/test_worktree_isolation.py  # NEW: offline coverage (throwaway git repo / fake runner)
```

**Structure Decision**: Mirror unit 048/049/050's additive wiring (neutral Protocol in
`loopplane.context`; opaque manager factory built in `host/assembly`; threaded via `drive` →
`RunContext`; default-off gate; cleanup at scope exit) — but **without a task group** (worktree ops
are synchronous). The 051-specific bits are the **managed-area path confinement** (worktrees under
`<scope>/.loopplane-worktrees/`) and the **injectable git runner** (deterministic offline tests).

## Complexity Tracking

> No Constitution violations — section intentionally empty. Additive; the working-scope confinement
> is preserved; no task group, no event-bus change, no new ADR.
