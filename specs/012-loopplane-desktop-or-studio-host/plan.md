# Implementation Plan: Desktop / Studio Host

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-loopplane-desktop-or-studio-host/spec.md`

## Summary

Build the **Desktop / Studio Host** layer (Phase-12): a **local, in-process developer experience** over
the public Host Application Interface (unit 002). A new additive sub-package, `loopplane.studio`, ships
a **developer-console core** (command → public-safe metadata-only view model), a **local session
manager** (open / list / select / close interactive sessions held over the embedded host), and a
**sidecar host contract** (a start/stop lifecycle with an in-process implementation). It embeds a
`LoopPlaneHost`, drives no runtime internals, executes no tool itself (Constitution V), and consumes
the normalized event stream as a host consumer without re-emitting the live bus (Constitution VI).
Unlike the web/API host (unit 011) it adds **no third-party dependency**, ships **no GUI / network /
OS-process spawning** (all reserved), and — being in-process — exercises the interactive approval
round-trip directly. Design detail lives in [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–11).

**Primary Dependencies**: the public Host Application Interface (`loopplane.host`: `LoopPlaneHost`,
`build_host`, `RunOutcome`, `Session`, `ApprovalDecision`, `RuntimeConfig`, …) and `anyio` (already a
core dependency, for the task group that holds interactive sessions open). **No new third-party
dependency** — the studio is pure in-process Python over the host.

**Storage**: None. The layer owns no store; it embeds a host and projects its outputs.

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. A public-safe scripted fake-model host is the deterministic instrument; the
interactive round-trip is exercised **in-process** (no network transport, so no buffering-client
limitation — see research D5). The repo's `pytest-timeout` net guards against any stuck test.

**Target Platform**: Cross-platform library embedded in a local developer process; offline.

**Project Type**: single library/host package (**no frontend** — the GUI / UI shell is unit-012
reserved, a real desktop app is future work).

**Performance Goals**: Not a throughput target; correctness, determinism of the command→view mapping
(SC-002), and fail-safe behavior (SC-004/006) are the goals.

**Constraints**: composes only the public `loopplane.host` surface (NFR-001); executes no tool
(Constitution V, NFR-002); consumes events as a host consumer, never re-emits the live bus
(Constitution VI, NFR-003); view models are **metadata-only** — never raw history blocks (FR-030,
NFR-006); deterministic command→view mapping (NFR-004, SC-002); fail-safe (NFR-005, SC-004/006);
offline — no network, no OS process spawn (FR-051, NFR-006); in-process testable (NFR-007).

**Scale/Scope**: One new package (~5 modules), one example, one doc, unit/integration/contract suites.
**No new dependency; no Phase-1/2/11 source is modified.**

## Dependency on Phase 2

This phase is **strictly additive** and consumes only the public host surface (NFR-001, NFR-002):

- **Phase-2 host (`loopplane.host`)**: `LoopPlaneHost` / `build_host` (assemble + `run` + `session` +
  `list_sessions` + `resume` + `history_snapshot` + `retrieve_artifact`), the `Session` round-trip
  (`submit` / `answer_approval` / `answer_question` / `cancel` / `outcome`), `RunOutcome`, and
  `ApprovalDecision` / `RuntimeConfig` for construction.

The layer adds **no** new public contract to Phase-2; it re-presents the host locally. It re-implements
no loop, no gateway, and no event bus (NFR-002, NFR-003). It needs **no** event serialization (it
projects `RunOutcome`, not the live stream), so it imports neither `loopplane.events` nor any internal.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.studio` depends on the public `loopplane.host` and
`anyio` + stdlib. The runtime, loop, host, and every sibling layer have **zero** knowledge of the
studio layer.

```text
local developer (a UI shell / terminal renders the view models — reserved)
     │  console commands  →  public-safe metadata-only view models
     ▼
loopplane.studio  (StudioHost console + session manager + sidecar contract)
     │  composes ONLY the public host surface; projects RunOutcome -> views
     ▼
loopplane.host.LoopPlaneHost  ──drives──▶  Phase-1 runtime (gateway owns tools; bus owns events)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/studio-boundary.md](./contracts/studio-boundary.md)):

- The console **drives runs only through** `LoopPlaneHost.run` / `.session` and the `Session` handle;
  it **executes no tool** and re-implements no loop (Constitution V; NFR-002).
- It re-emits **no** live bus event — the only event path is an injected discard sink to satisfy
  `host.run`; it forwards nothing (Constitution VI; NFR-003).
- **View models are metadata-only**: history is projected to `{role, block_count}`; no `ContentBlock`
  text, tool I/O, or secret appears in any view (FR-030; NFR-006).
- It imports only `loopplane.host`, `anyio`, and stdlib; it does **not** import the controller, gateway,
  dispatcher, `loopplane.events`, or a sibling layer (NFR-001).

## Project Structure

### Documentation (this feature)

```text
specs/012-loopplane-desktop-or-studio-host/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── studio-api.md       # console commands, view models, the sidecar lifecycle
│   └── studio-boundary.md  # the host-only / no-tool / metadata-only boundary + audit
├── checklists/requirements.md
└── tasks.md                # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/studio/
├── __init__.py        # public exports: StudioHost + Sidecar contract + view models
├── views.py           # metadata-only view models + projections from RunOutcome (FR-030, NFR-006)
├── sessions.py        # the held-open interactive-session registry (SessionEntry + run_session) (FR-010-FR-022)
├── console.py         # StudioHost: the async-context-manager console core (run / open / submit / answer / cancel / list / history) (FR-001-FR-030)
└── sidecar.py         # the SidecarHost contract + an in-process implementation + lifecycle (FR-040-FR-041)

examples/
└── studio_quickstart.py   # runnable: build a host -> StudioHost -> drive a run + list/inspect (public-safe, in-process)

docs/
└── desktop-studio-host.md # public-safe guide: the console, the session manager, the sidecar, reserved UI shell

tests/
├── unit/
│   └── test_studio_core.py        # view projections (metadata-only), error/conflict views, deny-ish edges
├── integration/
│   ├── test_studio_us1.py         # US1: run from the console -> a metadata-only result view; concurrent -> conflict
│   ├── test_studio_us2.py         # US2: session manager open / list / select / close; unknown id -> not-found
│   ├── test_studio_us3.py         # US3: interactive submit + answer approval (in-process) + cancel never hangs
│   ├── test_studio_us4.py         # US4: outcome / history-metadata / sessions views; unknown -> not-found
│   └── test_studio_us5.py         # US5: in-process sidecar start/stop lifecycle (idempotent; stopped -> not-available)
└── contract/
    └── test_studio_boundary.py    # import-boundary (host/anyio/stdlib only), no-tool / no-reemit, metadata-only views
```

**Structure Decision**: one new sub-package `loopplane.studio`, mirroring the Phase-1..11
one-package-per-boundary convention so the layer is a single, clearly-bounded, independently revertible
addition. It depends inward on the public `loopplane.host` surface only. No new dependency; no
Phase-1/2/11 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks
are deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| IA — Foundational + run (US1) | package skeleton + `__init__`; `views.py` (`RunResultView`, `HistoryEntryView`, `OutcomeView`, `SessionSummaryView`, `ErrorView`); `console.py` `StudioHost` async-CM skeleton + `run()` + conflict mapping — **blocks all stories** | `test_studio_core.py` + `test_studio_us1.py` green; metadata-only result view; concurrent → conflict view (SC-001) | Revert package |
| IB — Session manager (US2) | `sessions.py` (held-open registry) + `StudioHost` open / list / select / close | `test_studio_us2.py` green; unknown id → not-found; close frees the sequential host | Revert IB |
| IC — Interactive session (US3) | `StudioHost` submit / answer-approval / answer-question / cancel over the held session | `test_studio_us3.py` green; in-process approval round-trip; cancel never hangs | Revert IC |
| ID — Inspection (US4) | `StudioHost` outcome / history-metadata / sessions views | `test_studio_us4.py` green; metadata-only; unknown → not-found (SC-003) | Revert ID |
| IE — Sidecar (US5) | `sidecar.py` (`SidecarHost` contract + in-process impl + lifecycle) | `test_studio_us5.py` green; idempotent stop; stopped → not-available (SC-006) | Revert IE |
| IF — Example, docs, boundary | `examples/studio_quickstart.py`, `docs/desktop-studio-host.md`, `test_studio_boundary.py` + public-safety `PHASE12_TARGETS` | boundary + metadata-only + no-tool green; example runs; scan clean (SC-003/005) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Leaking conversation content in a view | View models are metadata-only projections (`{role, block_count}`, ids, reasons); a unit test asserts no `ContentBlock` text appears in any view (FR-030, NFR-006, SC-003) |
| Leaking internal detail in an error view | Every error/conflict/not-found is a fixed public-safe view; no stack trace, internal type, or path; a test drives malformed/unknown inputs (FR-050, SC-003) |
| A held-open interactive session hanging on cancel | `Session.cancel()` resolves anything parked; a test cancels a parked session and asserts no hang (FR-022, SC-006) |
| Executing a tool / re-emitting the live bus (Constitution V/VI) | The layer only calls `host.run` / `host.session` / the `Session` handle with a discard sink; a contract test asserts no gateway/controller/`events` import and no tool execution (NFR-002/003, SC-005) |
| Concurrent run on a sequential host | A second run/open while active maps the host's `RuntimeError` to an explicit conflict view; a test asserts no corruption (FR-003) |
| Sidecar lifecycle leaks (orphaned run / double-stop) | The in-process sidecar's stop is idempotent and joins the task group; a command to a stopped sidecar returns a not-available view; tests cover both (FR-041, SC-006) |
| Reaching a runtime internal | Import-boundary audit: `loopplane.studio` imports only `loopplane.host` / `anyio` / stdlib; references no controller / gateway / dispatcher / `events` / sibling token (NFR-001) |
| Scope creep into a real GUI / process spawn / network | Out-of-scope list + reserved extension points; Constitution III gate; only the in-process console core + sidecar contract ship |

**Rollback posture**: `loopplane.studio` is purely **additive** over Phase 2 — small, task-scoped
commits, each phase (IA–IF) independently revertible. The layer owns no runtime state beyond a
lifespan-scoped session registry and drives nothing of its own, so reverting any or all leaves the
runtime, host, and every sibling untouched. No dependency is added to remove.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.studio` written fresh; composes the public host surface; **no private/legacy UI copied** |
| III | Agent Harness Before Loop Automation | PASS | An additive local presentation over the existing host; ships **no** GUI, no scheduler/validator/loop automation, and names every reserved extension point |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (present the public host to a local developer); depends inward on public surfaces; no run/gateway/bus logic of its own |
| V | Tool Gateway Ownership | PASS | The layer resolves/authorizes/executes **no** tool; tool execution remains the gateway's, reached only through `LoopPlaneHost` (NFR-002; contract-tested) |
| VI | Runtime Event Bus Ownership | PASS | The layer re-emits **no** live bus event; its only event path is a discard sink for `host.run`; it projects `RunOutcome`, not the live stream (FR-002, NFR-003) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names/IPs in any artifact; view models are metadata-only; scan extended with PHASE12 targets (NFR-006, SC-003/005) |
| VIII | No SDK Replacement | PASS | **No** framework introduced at all — pure in-process Python over the public host + `anyio` (already core). The runtime core is untouched |
| IX | Reference, Not Clone | PASS | Console / session-manager / sidecar shapes re-derived public-safe from the spec and the public host; **no** private/legacy UI excerpt |
| X | Testable Evolution | PASS | Each phase (IA–IF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; determinism + metadata-only + fail-safe first-class; in-process tests avoid the buffering-client limitation that bit unit 011 |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation, no
new dependency, and no Phase-1/2/11 modification. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify, and no new dependency to record — table intentionally empty.
