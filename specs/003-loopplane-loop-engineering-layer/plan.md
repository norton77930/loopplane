# Implementation Plan: Loop Engineering Layer

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-loopplane-loop-engineering-layer/spec.md`

## Summary

Build the **outer loop-engineering layer** on top of the merged Phase-1 runtime foundation
(`001-loopplane-runtime-foundation`) and Phase-2 Host Interface (`002-loopplane-host-interface`). The
layer wraps agent runs in an outer control loop: it defines a loop, triggers it (manually), starts each
Agent Run **through the Phase-2 `LoopPlaneHost`**, validates the outcome, optionally evaluates it, and
decides whether to stop, retry, repair, or request human review — repeating under a hard iteration bound
until a single terminal outcome. It adds **no runtime internals**: every run is started and observed
through the host, and the layer never reaches into Phase-1 components (FR-080–FR-083, FR-090, NFR-003).

The deliverable is one new additive sub-package, `loopplane.engineering`, providing: **Loop Definition**
and its policies, a **Loop Controller** (`run_loop`), the **manual trigger** plus **interval/condition
trigger contracts**, a **Validator** contract with fail-safe handling, an optional **Evaluator**
contract, distinct **retry** and **repair** paths, bounded **stop conditions**, in-process
reconstructable **Loop State**, and a versioned **Loop Event** stream — plus a public-safe example, an
embedding doc, and unit/integration/contract test suites. Design detail lives in
[research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts), and
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–2).

**Primary Dependencies**: The Phase-2 `loopplane.host` public surface (`LoopPlaneHost`, `RuntimeConfig`,
`RunOutcome`, `ApprovalDecision`) and Phase-1 value types re-exposed through it (`RuntimeEvent`,
`TerminationReason`, `ContentBlock`/`TextBlock`). No new third-party runtime dependency — the layer is
pure outer-loop control over `anyio` / `pydantic` v2 already present in the core.

**Storage**: None of its own. Loop State is **in process** and reconstructable from the Loop Event stream
(FR-062); checkpoints and artifacts stay in the Phase-1 stores, referenced only by id through the host
(FR-053, FR-061). No database, no durable loop persistence this phase (FR-064, FR-092).

**Testing**: pytest + the anyio plugin (Phase-1 toolchain). New suites under `tests/unit/`,
`tests/integration/`, and `tests/contract/`. `ScriptedModel` plus scripted validators/evaluators are the
deterministic instruments (NFR-002, SC-003).

**Target Platform**: Cross-platform library (Windows/Linux/macOS) embedded in a plain host process; no
web/desktop/CLI/transport dependency (FR-017, FR-092).

**Project Type**: Single library — one new sub-package (`loopplane.engineering`) added to the existing
src-layout package, keeping the "one package per component boundary" convention from Phases 1–2.

**Performance Goals**: Negligible overhead over the bare host; one host assembly per Loop Run, a thin
event/decision path per iteration. Determinism preserved (NFR-002).

**Constraints**: Host-interface-only run invocation (FR-080–FR-083, SC-002); observation defaults off
with zero behavior change (NFR-005, SC-009); every Loop Run bounded and terminal (FR-013, FR-074,
SC-007); public-safe with no secrets/paths/private names (NFR-004, SC-010); minimal, reversible surface
(NFR-006).

**Scale/Scope**: Single in-process Loop Run at a time (FR-091); one new package (~10 modules), one
example, one doc, and unit/integration/contract suites. **No Phase-1/2 source is modified.**

## Dependency on Phases 1 & 2

This phase is **strictly additive** and consumes only the Phase-2 public surface plus the value types it
re-exposes — it composes them and does not modify or re-implement them (NFR-001, FR-090). The exact
surface and the inner/outer boundary are enumerated in
[contracts/host-integration.md](./contracts/host-integration.md) and
[research.md](./research.md#inherited-context-no-re-derivation--nfr-001).

**Non-duplication guarantee (FR-090, SC-010)**: the layer contains *no* Agent Loop, Runtime Controller
mechanics, Dispatcher, Tool Gateway pipeline, Runtime Event vocabulary, or store internals. Any
capability it needs that Phases 1–2 lack (the Loop Definition, Loop Controller, Loop Events, Loop State,
validator/evaluator handling) is added *above* the host boundary, never by editing Phase-1/2 modules.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.engineering` depends on `loopplane.host`; the host
and core have **zero** knowledge of the loop layer.

```text
loop engineer / host driver
        │  builds + triggers (manual entry point)
        ▼
  LoopDefinition ──► run_loop()  [Loop Controller]
        │                  │ starts each Agent Run via the Host Interface (no bypass)
        │                  ▼
        │            LoopPlaneHost.run(prompt, on_event, on_approval)  ◄── Phase-2
        │                  │ returns RunOutcome (session_id, termination_reason)
        │                  ▼
        │   Validator ─► (Evaluator?) ─► next action: stop / retry / repair / human-review
        │                  │
        ▼                  ▼
  Loop State (refs only) ◄── records ──  Loop Event stream (distinct; off by default)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/host-integration.md](./contracts/host-integration.md)):

- The Loop Controller starts/observes Agent Runs **only** through `LoopPlaneHost.run` / `.session`
  (FR-080–FR-081).
- Validator/Evaluator are host-supplied policy callables; the layer hardcodes no domain logic (FR-033).
- Loop State holds **references** (`session_id`, artifact refs) — never copied Run State or bytes
  (FR-061).
- The Loop Event stream is separate from the Runtime Event Bus and never wraps/re-emits Runtime Events
  (FR-070).

## Project Structure

### Documentation (this feature)

```text
specs/003-loopplane-loop-engineering-layer/
├── spec.md                 # Feature specification (complete)
├── plan.md                 # This file (/speckit.plan output)
├── research.md             # Phase 0: design decisions
├── data-model.md           # Phase 1: outer-layer entities
├── quickstart.md           # Phase 1: validation/run guide
├── contracts/              # Phase 1: interface contracts
│   ├── loop-definition.md      # Loop Definition + policies + trigger contracts
│   ├── loop-controller.md      # Loop Controller lifecycle, decisions, retry/repair
│   ├── validator-evaluator.md  # Validator (gating) + Evaluator (non-gating)
│   ├── loop-events.md          # Loop Event vocabulary + Loop State reconstruction
│   └── host-integration.md     # Phase-2 boundary contract (the no-bypass rule)
├── checklists/
│   └── requirements.md     # Spec quality checklist (complete)
└── tasks.md                # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/engineering/
├── __init__.py        # public exports (Loop Definition, policies, controller, validator/evaluator,
│                      #   events, state, trigger contracts, reference constructors)
├── definition.py      # LoopDefinition + InputSource + HostRuntimeProfile + validate_definition (FR-001–FR-009)
├── policies.py        # Validation/Evaluation/Retry/Repair/Artifact/Approval/Observation policies (FR-004–FR-009)
├── triggers.py        # ManualTrigger (impl) + IntervalTrigger/ConditionTrigger contracts (FR-020–FR-023)
├── validation.py      # Validator Protocol, ValidationResult, ValidationStatus, fail-safe helpers (FR-030–FR-034)
├── evaluation.py      # Evaluator Protocol, EvaluationResult (optional, non-gating) (FR-040–FR-043)
├── stopping.py        # StopCondition + reference constructors + hard bound (FR-007, FR-013)
├── events.py          # LoopEvent vocabulary, LOOP_SCHEMA_VERSION, LoopEventSink (FR-070–FR-075)
├── state.py           # LoopState + RunReference/ArtifactRef + reconstruct_state (FR-060–FR-064)
└── controller.py      # run_loop / LoopController: lifecycle, decisions, retry, repair (FR-010–FR-016, FR-050–FR-056)

examples/
└── loop_quickstart.py # runnable single-iteration loop over a scripted host (public-safe)

docs/
└── loop-engineering.md # public-safe guide: definition → run_loop → events → retry/repair/review

tests/
├── unit/
│   └── test_engineering_core.py   # definition validation, status→decision map, stop bound, state reconstruction
├── integration/
│   ├── test_loop_us1.py           # US1: define + manual run, boundary audit, determinism (SC-001/002)
│   ├── test_loop_us2.py           # US2: four validation statuses + fail-safe (SC-003)
│   ├── test_loop_us3.py           # US3: retry exhaustion + repair input + artifact/checkpoint (SC-004/005)
│   ├── test_loop_us4.py           # US4: evaluator score-stop, non-gating, absent policy, error (FR-040–FR-043)
│   └── test_loop_us5.py           # US5: manual trigger, interval/condition driver, human-review pause (SC-008)
└── contract/
    └── test_engineering_boundary.py  # import-boundary audit + host-only run path + public-safety (SC-002/010, NFR-003)
```

**Structure Decision**: one new sub-package `loopplane.engineering`, mirroring the Phase-1/2
one-package-per-boundary convention so the loop layer is a single, clearly-bounded, independently
revertible addition. The package name maps to the feature ("loop-**engineering**-layer", paralleling
Phase-2's `host` from "host-interface") and is intentionally **distinct from the existing
`loopplane.loop`**, which is the Phase-1 *inner* Agent Loop — the inner/outer distinction is normative in
the spec. No Phase-1/2 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| EA — Contracts & state | `definition.py`, `policies.py`, `triggers.py`, `validation.py`, `evaluation.py`, `stopping.py`, `events.py`, `state.py` (types + validation + `reconstruct_state`) | `test_engineering_core.py` green; definitions validate; state reconstructs (SC-006) | Revert package; nothing depends on it yet |
| EB — Loop Controller (US1) | `controller.py`: `run_loop` single-iteration through `host.run`; Loop Events; in-process Loop State | `test_loop_us1.py` green incl. boundary audit + determinism (SC-001/002) | Revert to contracts-only |
| EC — Validation gating (US2) | status→decision mapping; `validation_completed`; fail-safe handling | `test_loop_us2.py` green: all four statuses + fault (SC-003) | Revert decision layer; US1 intact |
| ED — Retry & repair (US3) | retry count+backoff (no sleep); repair input injection; artifact/checkpoint reuse-by-reference | `test_loop_us3.py` green: exhaustion (SC-004), repair content (SC-005) | Revert retry/repair; gating intact |
| EE — Evaluator + stop (US4) | optional evaluator; `evaluation_completed`; score-threshold stop; non-gating + error handling | `test_loop_us4.py` green (FR-040–FR-043) | Revert evaluation; loop runs on validation alone |
| EF — Triggers, review, example, docs (US5) | interval/condition driver path; human-review pause/resume; `examples/loop_quickstart.py`; `docs/loop-engineering.md`; extend public-safety scan | `test_loop_us5.py` + `test_engineering_boundary.py` green; example reproduces output; scan clean (SC-008/010) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Loop layer reaches into Phase-1/2 internals | Import-boundary audit test asserts `loopplane.engineering` imports only the allowed host surface (FR-081, NFR-003, SC-002); host-only run path enforced by design |
| Retry/repair (or a never-satisfied stop) loops unbounded | Hard `max_iterations` checked before every iteration (FR-013, FR-056); dedicated termination test (SC-007) |
| Retry vs repair distinction blurs | Two separate code paths + tests asserting retry re-sends identical input while repair injects changed input (FR-050, SC-004/005) |
| A validator fault is treated as silent pass | Fail-safe routes to human review / `loop_failed` with a diagnostic; explicit test (FR-034, SC-003) |
| Evaluator error aborts the run | Evaluator wrapped; error becomes a non-fatal diagnostic; iteration proceeds on validation (FR-043) |
| Observation changes behavior | Off by default; parity test compares observed vs unobserved decisions/outcome (NFR-005, SC-009) |
| A secret/private path leaks via a Loop Definition | Definition carries no secrets by contract; host/model hold credentials; public-safety scan over committed files (NFR-004, SC-010) |
| Scope creeps into a scheduler/queue/UI | Interval/condition are contracts only; out-of-scope list forbidden by FR-091–FR-092; Constitution III review gate |

**Rollback posture**: `loopplane.engineering` is purely **additive** over Phases 1–2 — small,
task-scoped commits, each phase (EA–EF) independently revertible. Reverting any or all leaves the
Phase-1/2 runtime and on-disk records untouched (the loop layer owns no runtime state and no storage
format). Observation is default-off, so a partial revert can never change core-loop behavior.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.engineering` package written fresh; composes the Phase-2 public API only; no legacy code copied (FR-090) |
| III | Agent Harness Before Loop Automation | PASS | This *is* the deferred loop layer the constitution scoped for "a future layer"; it stays minimal, ships **no** production scheduler/watcher, and names every reserved extension point (FR-091, NFR-006) — manual trigger only, interval/condition are contracts |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (outer-loop control); depends inward on Phase 2; spec boundary table + [host-integration.md](./contracts/host-integration.md) assign ownership; no Phase-1/2 boundary blurred (FR-090) |
| V | Tool Gateway Ownership | PASS | The layer never resolves/authorizes/executes tools; all tool execution stays inside the Phase-1 gateway reached through the host (FR-082, FR-090) |
| VI | Runtime Event Bus Ownership | PASS | Consumes normalized Runtime Events through `host.run(on_event=...)`; emits a **distinct** Loop Event stream that never wraps/re-emits Runtime Events; versioned + unknown-type tolerant (FR-070, FR-075, FR-081) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; Loop Definition carries no secrets (FR-001, NFR-004); examples/docs public-safe; scan extended (SC-010); private reference stays untracked |
| VIII | No SDK Replacement | PASS | No agent framework introduced; pure outer-loop control over LoopPlane's own runtime via the host |
| IX | Reference, Not Clone | PASS | Loop concepts re-derived public-safe from the spec and the Phase-2 surface; no raw reference excerpts (spec Out-of-Scope) |
| X | Testable Evolution | PASS | Each phase (EA–EF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; observation default-off |

**Post-design re-check**: PASS — the entity model, contracts, and event model introduce no boundary
violation and no Phase-1/2 modification. The only mutable entity (`LoopState`) is controller-owned and
reference-only. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
