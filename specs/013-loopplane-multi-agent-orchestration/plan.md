# Implementation Plan: Multi-Agent Orchestration

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-loopplane-multi-agent-orchestration/spec.md`

## Summary

Build the **Multi-Agent Orchestration** layer (Phase-13): run several agent loops as **subagents** and
combine their results. A new additive sub-package, `loopplane.orchestration`, ships an **agent
registry** (named subagents = loop definitions), **subagent execution** + a **coordinator** that runs a
selected set through the public Phase-3 entry point (`run_loop`), **child run references**, and
**aggregated event / artifact views** — all **deterministic by registration order** and metadata-safe.
Each subagent run returns a `LoopOutcome` that already carries its recorded loop-event stream and its
run/artifact references, so the layer aggregates from **captured outcomes** (a recorded-event consumer,
exactly as Constitution VI prescribes — it never re-emits a live bus) and **executes no tool**
(Constitution V — tools run inside the subagents' loops). Execution is **sequential** (deterministic,
no shared-host concurrency); concurrent fan-out is reserved. Design detail lives in
[research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts), and
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–12).

**Primary Dependencies**: the public Phase-3 loop surface (`loopplane.engineering`: `run_loop`,
`LoopDefinition`, `LoopOutcome`, `LoopEvent`, `LoopState`, `RunReference`, `ArtifactRef`). Plus the
stdlib. **No new third-party dependency** — not even `anyio`: the coordinator awaits `run_loop`
sequentially.

**Storage**: None. The layer owns no store; it runs subagent loops and aggregates their captured
outcomes into in-memory value structures.

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted `LoopDefinition`s over a scripted model are the deterministic instruments;
no real model, no network. The repo's `pytest-timeout` net guards against any stuck test.

**Target Platform**: Cross-platform library embedded in a host process; offline.

**Project Type**: single library package (no frontend, no transport).

**Performance Goals**: Not a throughput target; correctness, determinism of ordering/aggregation
(SC-002), and fail-safe behavior (SC-004) are the goals.

**Constraints**: composes only the public Phase-3 loop surface (NFR-001); executes no tool
(Constitution V, NFR-002); consumes each subagent's captured loop events, never re-emits the live bus
(Constitution VI, NFR-003); aggregation is **metadata-only** — subagent name / event type / sequence /
references, never conversation content (FR-021/FR-031, NFR-006); deterministic by registration order
(NFR-004, SC-002); fail-safe — a failing subagent / raising policy / unknown name / empty selection is
contained (NFR-005, SC-004); offline, in-process testable (NFR-006/NFR-007).

**Scale/Scope**: One new package (~4 modules), one example, one doc, unit/integration/contract suites.
**No new dependency; no Phase-1/2/3 source is modified.**

## Dependency on Phase 3

This phase is **strictly additive** and consumes only the public Phase-3 loop surface (NFR-001):

- **Phase-3 (`loopplane.engineering`)**: `run_loop(definition, *, on_loop_event=None, ...)` (the manual
  loop-run entry point — drives one subagent's loop run), `LoopDefinition` (a subagent), `LoopOutcome`
  (`loop_id` / `terminal_event` / `stop_reason` / `state` / `events` / `diagnostics`), `LoopEvent`
  (`type` / `sequence` / `loop_id` / `session_id`), and `LoopState` (`run_refs: RunReference[]` /
  `artifacts: ArtifactRef[]`). `RunReference` (`session_id` / `termination_reason`) and `ArtifactRef`
  (`session_id` / `reference`) are the public-safe references aggregated.

The layer adds **no** new public contract to Phase-3; it composes the loop entry point and the captured
outcome. It re-implements no loop, no gateway, and no event bus (NFR-002, NFR-003); it needs no live
sink (the `LoopOutcome` already carries the recorded, ordered event stream).

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.orchestration` depends on the public
`loopplane.engineering` surface + stdlib. The runtime, loop, host, and every sibling layer have **zero**
knowledge of the orchestration layer.

```text
operator registers named subagents (loop definitions)
     │
     ▼
loopplane.orchestration.Coordinator  ──run each subagent──▶  loopplane.engineering.run_loop
     │  captures each LoopOutcome (events + run/artifact refs)
     ▼
aggregate_events / aggregate_artifacts  →  deterministic, metadata-only views (by registration order)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/orchestration-boundary.md](./contracts/orchestration-boundary.md)):

- The coordinator **drives subagent runs only through** the public `run_loop`; it **executes no tool**
  and re-implements no loop (Constitution V; NFR-002).
- It **consumes** each subagent's captured `LoopOutcome.events` (recorded) and re-emits **no** live bus
  event (Constitution VI; NFR-003).
- **Aggregated views are metadata-only**: subagent name / event type / sequence / run + artifact
  references — never conversation content, a payload value, tool I/O, or a secret (FR-021/FR-031;
  NFR-006).
- It imports only `loopplane.engineering` and stdlib; it does **not** import a Phase-1/2 internal, the
  host, the gateway, or a sibling layer (NFR-001).

## Project Structure

### Documentation (this feature)

```text
specs/013-loopplane-multi-agent-orchestration/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── orchestration-api.md      # registry, coordinator, child references, aggregated views
│   └── orchestration-boundary.md # the engineering-only / no-tool / metadata-only boundary + audit
├── checklists/requirements.md
└── tasks.md                      # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/orchestration/
├── __init__.py        # public exports: registry + coordinator + aggregation
├── registry.py        # Subagent + AgentRegistry + DuplicateSubagentError (FR-001-FR-003)
├── coordinator.py     # ChildRunReference + SubagentResult + DelegationPolicy + Coordinator (FR-002-FR-041)
└── aggregate.py       # AggregatedEvent/Artifact + aggregate_events / aggregate_artifacts (FR-020-FR-031)

examples/
└── orchestration_quickstart.py   # runnable: register subagents -> coordinate -> aggregate (public-safe, in-process)

docs/
└── multi-agent-orchestration.md  # public-safe guide: registry, coordinator, delegation, aggregation

tests/
├── unit/
│   └── test_orchestration_core.py    # registry register/duplicate/not-found; aggregation ordering/metadata-only
├── integration/
│   ├── test_orchestration_us1.py     # US1: register + run a subagent -> child reference + outcome
│   ├── test_orchestration_us2.py     # US2: coordinate a set, registration-order, deterministic
│   ├── test_orchestration_us3.py     # US3: aggregated event view (grouped, ordered, metadata-only)
│   ├── test_orchestration_us4.py     # US4: aggregated artifact view (grouped, metadata-only)
│   └── test_orchestration_us5.py     # US5: delegation policy; failing subagent / raising policy / empty -> safe
└── contract/
    └── test_orchestration_boundary.py  # import-boundary (engineering only), no-tool / no-reemit, metadata-only
```

**Structure Decision**: one new sub-package `loopplane.orchestration`, mirroring the Phase-1..12
one-package-per-boundary convention so the layer is a single, clearly-bounded, independently revertible
addition. It depends inward on the public Phase-3 loop surface only. No new dependency; no Phase-1/2/3
source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks
are deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| IA — Foundational + registry/run (US1) | package skeleton + `__init__`; `registry.py` (`Subagent`, `AgentRegistry`, `DuplicateSubagentError`); `coordinator.py` `ChildRunReference` + `SubagentResult` + a single-subagent run via `run_loop` — **blocks all stories** | `test_orchestration_core.py` + `test_orchestration_us1.py` green; child reference + outcome; duplicate → error; unknown → not-found (SC-001) | Revert package |
| IB — Coordinator (US2) | `coordinator.py` `Coordinator.run(selection)` over a set, registration-ordered | `test_orchestration_us2.py` green; each run once; deterministic order (SC-002/006) | Revert IB |
| IC — Aggregated events (US3) | `aggregate.py` `AggregatedEvent` + `aggregate_events` | `test_orchestration_us3.py` green; grouped by subagent + ordered by sequence; metadata-only (SC-003) | Revert IC |
| ID — Aggregated artifacts (US4) | `aggregate.py` `AggregatedArtifact` + `aggregate_artifacts` | `test_orchestration_us4.py` green; grouped; metadata-only (SC-003) | Revert ID |
| IE — Delegation & fail-safe (US5) | `coordinator.py` `DelegationPolicy` + `Coordinator.delegate(policy)` + fail-safe capture | `test_orchestration_us5.py` green; failing subagent / raising policy / empty → safe (SC-004) | Revert IE |
| IF — Example, docs, boundary | `examples/orchestration_quickstart.py`, `docs/multi-agent-orchestration.md`, `test_orchestration_boundary.py` + public-safety `PHASE13_TARGETS` | boundary + metadata-only + no-tool green; example runs; scan clean (SC-003/005) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Leaking conversation content in an aggregated view | Views are metadata-only — subagent name / event type / sequence / run + artifact references; a unit test asserts no payload value / content appears (FR-021, FR-031, NFR-006, SC-003) |
| Non-deterministic ordering | Ordering is by **registration order** (then event sequence within a subagent), never wall-clock / completion time; a determinism test builds the views twice (NFR-004, SC-002) |
| A failing subagent / raising policy crashing the coordinator | A subagent's `run_loop` failure is caught and captured per subagent; a raising delegation policy is contained; an empty selection → an empty result; fail-safe tests assert no crash (FR-041, NFR-005, SC-004) |
| Executing a tool / re-emitting the live bus (Constitution V/VI) | The layer only calls `run_loop` and reads the captured `LoopOutcome`; a contract test asserts no host/gateway import, no tool execution, and no live-bus emission (NFR-002/003, SC-005) |
| Reaching a runtime internal | Import-boundary audit: `loopplane.orchestration` imports only `loopplane.engineering` + stdlib; references no host / gateway / controller / sibling token (NFR-001) |
| Scope creep into distributed / dynamic orchestration | Out-of-scope list + reserved extension points; Constitution III gate; only the deterministic, in-process, sequential coordinator + metadata-only aggregation ship |

**Rollback posture**: `loopplane.orchestration` is purely **additive** over Phase 3 — small, task-scoped
commits, each phase (IA–IF) independently revertible. The layer owns no runtime state and drives nothing
of its own beyond `run_loop`, so reverting any or all leaves the runtime, loop, and every sibling
untouched. No dependency is added to remove.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.orchestration` written fresh; composes the public Phase-3 surface; no legacy code copied |
| III | Agent Harness Before Loop Automation | PASS | An additive orchestration over the existing loop entry point; ships **no** distributed/dynamic orchestration and names every reserved extension point |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (run + aggregate subagent loop runs); depends inward on the public loop surface; no run/gateway/bus logic of its own |
| V | Tool Gateway Ownership | PASS | The layer resolves/authorizes/executes **no** tool; tool execution remains the gateway's, reached only inside the subagents' loop runs (NFR-002; contract-tested) |
| VI | Runtime Event Bus Ownership | PASS | The layer **consumes** each subagent's captured (recorded) loop events and re-emits **no** live bus event; it needs no live sink (FR-020, NFR-003) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names/IPs in any artifact; aggregated views are metadata-only; scan extended with PHASE13 targets (NFR-006, SC-003/005) |
| VIII | No SDK Replacement | PASS | **No** framework introduced — pure stdlib over the public Phase-3 loop surface; the runtime core is untouched |
| IX | Reference, Not Clone | PASS | Registry / coordinator / aggregation shapes re-derived public-safe from the spec and the public loop surface; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (IA–IF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; determinism + metadata-only + fail-safe first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation, no
new dependency, and no Phase-1/2/3 modification. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify, and no new dependency to record — table intentionally empty.
