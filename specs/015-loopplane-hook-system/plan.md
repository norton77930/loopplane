# Implementation Plan: LoopPlane Lifecycle Hook System

**Branch**: `015-loopplane-hook-system` (main-only) | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-loopplane-hook-system/spec.md`

## Summary

Add an in-process **lifecycle hook system** (`loopplane.hooks`) — a hook registry
plus eleven well-defined lifecycle points — that lets host and plugin code observe
the run and, at the before-tool and prompt-submit points, gate or modify it,
without forking the runtime. The mechanism is purely additive: each existing
runtime component (Tool Gateway, Agent Loop, Runtime Controller, and the
orchestration layer for subagent points) gains one **optional `hooks` seam that
defaults to absent**, so with no hooks registered the runtime is byte-for-byte
unchanged (FR-011, SC-003). Tool-boundary hooks fire **inside** the Gateway
(Constitution V); the hook system stays **distinct** from the Runtime Event Bus,
and hook failures surface only through the existing metadata-only `diagnostic`
event (Constitution VI). The package ships present-but-inert; hosts and the future
plugin system (unit 016) opt in by registering.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: standard library + `anyio` (already a core dependency); no new third-party dependency

**Storage**: N/A (in-process; hooks are not persisted)

**Testing**: pytest (unit + integration + import-boundary + public-safety), matching the existing suite

**Target Platform**: any platform the runtime already targets (in-process library)

**Project Type**: single library (`src/loopplane/`)

**Performance Goals**: zero added latency when no hooks are registered (FR-011); hook dispatch is O(registered hooks) per point

**Constraints**: additive only — no change to any existing public contract's required surface; no new runtime dependency; metadata-only, public-safe payloads

**Scale/Scope**: one new subpackage (~5 modules) + four additive wiring seams (gateway, loop, controller, orchestration) + tests/example/docs

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1 design. Result: **PASS** (no violations; Complexity Tracking empty).*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Work traces to `spec.md` (FR/SC referenced by every task). | PASS |
| II — Greenfield | All code written fresh; no copy from `openspec/` or legacy. | PASS |
| III — Harness before loop automation | Hooks are exactly the "explicit extension point" the foundation reserved; they attach to existing seams, adding no new automation engine. | PASS |
| IV — Runtime Boundary Clarity | New component with one responsibility (lifecycle interception); it interacts only through declared seams passed into Gateway/Loop/Controller — never reach-through internal access. | PASS |
| V — Tool Gateway Ownership | before/after-tool hooks fire **inside** `ToolGateway._run_one`; hooks never resolve, authorize, or execute tools; a hook deny routes through the Gateway's existing `_failure` / `POLICY_DENIAL` path. | PASS (FR-009, FR-012) |
| VI — Event Bus Ownership | Hooks are a distinct synchronous seam; event emission does not depend on hooks, and hooks neither re-emit nor mutate the bus. Hook failures surface via the existing `diagnostic` event only. | PASS (FR-010) |
| VII — Public-Safe | Payloads and reasons are metadata-only and public-safe; a public-safety test covers them. | PASS (FR-015, SC-005) |
| VIII — No SDK Replacement | No framework introduced; runtime core unchanged. | PASS |
| IX — Reference, not clone | The hook concept is re-derived for LoopPlane; divergences recorded in research.md (strict event/hook separation; abstain-to-baseline gating fail-safe). | PASS |
| X — Testable Evolution | Tests + rollback documented (rollback = drop the optional seams / remove the package; default-inert means revert is behavior-free). | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/015-loopplane-hook-system/
├── plan.md              # This file
├── research.md          # Phase 0 — seam analysis + decisions
├── data-model.md        # Phase 1 — points, payloads, decisions, registry, dispatcher
├── quickstart.md        # Phase 1 — runnable usage walkthrough
├── contracts/
│   ├── hooks.md                 # public hook API (registry + dispatcher + decisions)
│   └── integration-boundary.md  # how hooks wire into existing components (V/VI rules)
└── tasks.md             # Phase 2 — created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/hooks/            # NEW subpackage
├── __init__.py                 # public surface (__all__): points, decisions, registry, dispatcher
├── points.py                   # LifecyclePoint + per-point metadata-only payload dataclasses
├── decisions.py                # ToolGateDecision / PromptDecision (allow / deny|block / modify|annotate)
├── registry.py                 # HookRegistry: register / unregister / clear
└── dispatcher.py               # HookDispatcher: fire (isolation), gating resolution, sync+async

# Additive wiring seams (optional `hooks=None`; no required-surface change):
src/loopplane/gateway/gateway.py        # before/after-tool + file-changed firing inside _run_one
src/loopplane/loop/loop.py              # user-prompt-submit, session-start, model-stop firing
src/loopplane/controller/controller.py  # owns the dispatcher; setup (once) + session-end; passes seam down
src/loopplane/orchestration/coordinator.py  # subagent-start / subagent-stop firing

examples/hooks_quickstart.py    # credential-free, scripted-model walkthrough
docs/hooks.md                   # guide

tests/unit/test_hooks_registry.py        # registry + dispatcher isolation + resolution
tests/integration/test_hooks_us1.py..us5 # the five user stories end-to-end
tests/integration/test_hooks_boundary.py # import/no-bypass/no-reemit + metadata-only + public-safety
```

**Structure Decision**: Single library. One new subpackage `loopplane.hooks` owns
the registry, points, decisions, and dispatcher. Each existing component gains a
single optional `hooks` parameter (default `None`), mirroring how the Gateway
already accepts optional `decide` / `artifact_handoff` seams — so the change is
additive and the un-hooked path is unchanged.

## Phases

- **Phase 0 — Research** (`research.md`): map the real seams in `gateway._run_one`,
  `loop.run`, `controller` lifecycle, and `orchestration.coordinator`; decide the
  decision types, the failure-surfacing channel, and the FileChanged signal source.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the
  eleven points, the metadata-only payloads, the two gating-decision families, the
  registry/dispatcher contracts, the integration-boundary rules, and a usage walkthrough.
- **Phase 2 — Tasks** (`/speckit.tasks` → `tasks.md`): dependency-ordered, TDD —
  foundational unit tests first, then per-user-story integration, then boundary +
  public-safety, then the additive wiring, then example + docs.

## Complexity Tracking

*No Constitution Check violations — this table is intentionally empty.*
