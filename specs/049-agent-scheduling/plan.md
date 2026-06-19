# Implementation Plan: Agent Scheduling Tools

**Branch**: `049-agent-scheduling` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/049-agent-scheduling/spec.md`

**Boundary review (FR-009)**: **ADDITIVE — no new ADR, no contract break, no maintainer
consult needed.** Scheduling reuses the **unit-048** concurrency model (a per-run supervisor
owning an `anyio` task group; **ADR 0002**) + the **unit-004** interval/registry concepts. The
only new mechanism is a timer-driver task + an **injectable async sleeper** (so tests stay
deterministic without real sleeping) — both purely additive. The controller/loop stay
tool-agnostic via a neutral Protocol in `loopplane.context` (the 048 pattern). Unit 004's
`Clock` Protocol is **not** modified (it is `now()`-based; 049 adds its own injectable
`Sleeper`, leaving 004 untouched).

## Summary

Add agent-facing scheduling tools (`schedule_create` / `schedule_get` / `schedule_list` /
`schedule_cancel`) for delayed + recurring bounded child runs. A per-run
`ScheduleSupervisor` (new, `loopplane.tools.scheduling`) owns the schedule registry and, for
each schedule, starts a **timer task** in an injected `anyio` task group that waits via an
injectable `Sleeper` (real time in production; a controllable fake advanced by tests) and then
launches a bounded child run (reusing the 043/048 `run_child`), repeating for intervals. Gated
by `RuntimeConfig.max_schedules` (default `0` = off, byte-identical). Bounded (count + the 043
depth cap), contained (a failing occurrence → that occurrence's status, never a raise),
lifecycle-bound (timers cancelled at the supervisor scope exit). Threaded as
`RunContext.schedules` via a neutral `ScheduleSupervisor` Protocol in `loopplane.context`
(controller stays tool-agnostic, Constitution V). No event-schema / content-model change.

## Technical Context

**Language/Version**: Python 3.11+; `anyio` (existing) for the task group + the default sleeper.

**Primary Dependencies**: none new — reuses `anyio`, the 043/048 child-run, the unit-004
interval-cadence concepts (period math), and the 048 supervisor/scope pattern (ADR 0002).

**Storage**: in-memory per-run registry; no persistence (cross-session schedules out of scope).

**Testing**: pytest, offline — a fake `Sleeper` the test advances (deterministic, no real
sleep) drives interval firings; a scripted child model.

**Target Platform**: cross-platform library

**Project Type**: single project (library + tests)

**Constraints**: additive / reuse-first; default-off byte-identical; Gateway-only tools (V);
deterministic tests (injectable sleeper — no real sleeping); no 004 `Clock` contract change; no
event-schema/content-model change; no new ADR (reuses ADR 0002).

**Scale/Scope**: a new supervisor module + a `Sleeper` seam + 4 tools + an additive
`RunContext.schedules` field + the 048-style controller/dispatcher/host/assembly wiring + a
`RuntimeConfig.max_schedules` gate + tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-009. ✅
- **III. Agent Harness Before Loop Automation**: A bounded, opt-in, model-invoked autonomy
  primitive (default-off); not the reserved outer loop-automation layer. ✅
- **IV. Runtime Boundary Clarity**: Reuses the ADR-0002 concurrency model; the new timer/sleeper
  is additive; the controller/loop reference a neutral Protocol (no tools import). ✅
- **V. Tool Gateway Ownership**: The four tools dispatch only through the Gateway; child runs
  reuse the 043/048 seam. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change; child
  events captured, never on the parent bus. ✅
- **X. Testable Evolution**: Additive; default-off (`max_schedules = 0`) byte-identical;
  reversible; deterministic offline tests via the injectable sleeper. ✅

**Result**: PASS — additive; reuses ADR 0002 + unit-004; **no new ADR**, no breaking 001/002
contract change. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/049-agent-scheduling/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/scheduling-tools.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── scheduling.py        # NEW: ScheduleSupervisor + Sleeper seam + the 4 tools (a
                         #      SchedulingToolsAdapter), reusing the 043/048 run_child

src/loopplane/context.py            # MODIFIED: additive RunContext.schedules + a neutral
                                    #   ScheduleSupervisor Protocol (controller imports this)
src/loopplane/controller/{controller,dispatcher}.py   # MODIFIED: thread the schedule
                                    #   supervisor like 048's background supervisor (opaque
                                    #   factory; no loopplane.tools import)
src/loopplane/host/{host,assembly,config}.py   # MODIFIED: build/inject the factory + the
                                    #   RuntimeConfig.max_schedules gate (mirror 048)
src/loopplane/tools/__init__.py + docs/api-reference.md   # MODIFIED: export + document

tests/unit/test_agent_scheduling.py # NEW: offline coverage (fake sleeper; firings; caps;
                                     #   containment; lifecycle; default-off byte-identity)
```

**Structure Decision**: Mirror unit 048's additive wiring exactly (neutral Protocol in
`loopplane.context`; opaque supervisor factory built in `host/assembly`; threaded via `drive`
→ `RunContext`; default-off gate). The only 049-specific addition is the timer-driver + the
injectable `Sleeper` for deterministic interval firing. Unit 004's `Clock` is left unchanged.

## Complexity Tracking

> No Constitution violations — section intentionally empty. The single new mechanism (a
> timer-driver + injectable sleeper) is additive and reuses ADR 0002 + unit-004.
