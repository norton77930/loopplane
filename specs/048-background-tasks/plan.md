# Implementation Plan: Background Task Tools

**Branch**: `048-background-tasks` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/048-background-tasks/spec.md`

**Boundary review**: settled by **[ADR 0002](../../docs/adr/0002-background-task-execution.md)**
(maintainer-approved). Background tasks are a new in-run concurrency pattern, implemented
**additively** (optional fields/params, default-off byte-identical).

## Summary

Add agent-facing background-task tools (`task_create` / `task_get` / `task_list` /
`task_stop` / `task_output`) for **non-blocking**, bounded agent sub-runs. Per ADR 0002, a
per-run `BackgroundTaskSupervisor` owns an `anyio` task group + a `{task_id → status,
result}` registry; `task_create` reuses the unit-043 one-shot child run (`run_loop`) via
`task_group.start_soon` and returns an id immediately. The supervisor is created by the
scope owner — the **Dispatcher** (interactive / web-API) from its existing session task
group, and the one-shot **`host.run`** from a task group it wraps around its single drive —
and threaded to the tools via an additive `RunContext.background_tasks` field (the 043
`subagent_depth` pattern). Gated by `RuntimeConfig.max_background_tasks` (default `0` = off,
no supervisor, no tools, byte-identical). Bounded (count cap + 043 depth cap), contained
(failures → `failed` status, never a raise), and lifecycle-bound (pending tasks cancelled
when the supervisor scope exits). No event-schema / `SCHEMA_VERSION` / content-model change.

## Technical Context

**Language/Version**: Python 3.11+ (`loopplane`); `anyio` (already a dependency) for the
task group.

**Primary Dependencies**: none new — reuses `anyio`, the unit-043 child-run helpers
(`run_loop` + the depth-incremented child host / `_restrict_config` factory), `RunContext`,
the Tool Gateway SPI.

**Storage**: in-memory per-run registry in the supervisor; no persistence (cross-session
background tasks are out of scope).

**Testing**: pytest, offline (a scripted child model; assert non-blocking create, status
transitions, caps, containment, cancellation, default-off byte-identity).

**Target Platform**: cross-platform library

**Project Type**: single project (library + tests)

**Constraints**: additive / reuse-first; default-off byte-identical; Gateway-only tools (V);
no event-schema/content-model change (VI); bounded + contained + lifecycle-bound; ADR 0002.

**Scale/Scope**: a new supervisor module + 5 tool descriptors/handlers + an additive
`RunContext` field + additive `drive`/`host.run`/Dispatcher wiring + a `RuntimeConfig` gate
+ tests. Larger than a Tier-1 unit (cross-cutting through controller/dispatcher/host).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-009 + ADR 0002. ✅
- **III. Agent Harness Before Loop Automation**: A bounded, opt-in, model-invoked autonomy
  primitive (default-off), not the reserved outer loop-automation layer; explicitly framed
  by ADR 0002. ✅
- **IV. Runtime Boundary Clarity**: The new concurrency pattern is recorded in ADR 0002; the
  supervisor is owned by the run/session scope owner and threaded additively. ✅
- **V. Tool Gateway Ownership**: The five tools dispatch only through the Gateway; the child
  runs reuse the 043 `run_loop` seam. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change;
  child events captured (no live sink), never re-emitted on the parent bus. ✅
- **X. Testable Evolution**: Additive; default-off (`max_background_tasks = 0`) byte-identical;
  reversible; offline-tested. ✅

**Result**: PASS — the one boundary crossing (a new in-run concurrency pattern) is approved
and recorded in ADR 0002; no breaking 001/002 contract change. Complexity Tracking not
required.

## Project Structure

### Documentation (this feature)

```text
specs/048-background-tasks/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/background-task-tools.md
└── checklists/requirements.md
docs/adr/0002-background-task-execution.md   # the approved boundary decision
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── background.py        # NEW: BackgroundTaskSupervisor + the 5 tool descriptors/handlers
                         #      (task_create/get/list/stop/output), reusing the 043 child run

src/loopplane/context.py            # MODIFIED: additive RunContext.background_tasks field
src/loopplane/controller/controller.py  # MODIFIED: drive(..., background_supervisor=None)
                                        #   stamps it onto RunContext; max_background_tasks gate
src/loopplane/controller/dispatcher.py  # MODIFIED: create a supervisor from the session task
                                        #   group and pass it to drive (when enabled)
src/loopplane/host/host.py          # MODIFIED: one-shot run wraps a task group + supervisor
src/loopplane/host/assembly.py      # MODIFIED: register the background tools + child-host
                                    #   factory when max_background_tasks > 0 (like 043)
src/loopplane/host/runtime_config (RuntimeConfig)  # MODIFIED: max_background_tasks: int = 0
src/loopplane/tools/__init__.py     # MODIFIED: export the supervisor/adapter (api-reference)
docs/api-reference.md               # MODIFIED: document the new exported name(s)

tests/unit/test_background_tasks.py # NEW: offline coverage
```

**Structure Decision**: A new `loopplane.tools.background` module holds the supervisor + the
five tools, reusing the 043 child-run factory. The supervisor is threaded exactly like 043's
`subagent_depth` (additive `RunContext` field + an optional `drive`/`host`/Dispatcher param),
gated by `RuntimeConfig.max_background_tasks` (default 0 = off). The 043 wiring in
`host/assembly.py` is the template for registration + the child-host factory.

## Complexity Tracking

> No unjustified complexity. The single boundary crossing (a new in-run concurrency pattern)
> is justified by ADR 0002 and gated default-off; not a Constitution violation.
