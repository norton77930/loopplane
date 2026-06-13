# Implementation Plan: Human Review Workflows

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-loopplane-human-review-workflows/spec.md`

## Summary

Build the **Human Review Workflow** layer that turns the Phase-3 bare review hook
(`run_loop(review_resolver=...)`, the paused `LoopOutcome`, `LoopState.approval_status`) into reusable,
deterministic, public-safe human-review workflows. A host implements a **Reviewer**; the layer's
**review-gate builder** composes it (plus an optional **Review Memory** and a review-question channel)
into a Phase-3 `ReviewResolver` — the **human gate loop**. The layer adds a **Review Request** built from
the public Loop State, a richer **Review Decision** (approve / reject / request_changes) mapped down to
the Phase-3 decision, a **Review Context** for review-level questions, a distinct **Review Event** stream
(off by default), and the **pause / inspect / resume** path. The deliverable is one new additive
sub-package, `loopplane.review`, plus a public-safe example, a doc, and unit/integration/contract suites.
It composes only the Phase-3 public surface and reads only the public Loop State — it never reaches into
the Phase-1 Human Approval boundary or the in-run question machinery (those govern in-run *tool* approval
and are a distinct concern). Design detail lives in [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–5).

**Primary Dependencies**: The Phase-3 `loopplane.engineering` public surface (`run_loop`,
`ReviewResolver`, `ReviewDecision`, `LoopState`, `LoopOutcome`, `LoopDefinition`) and the stdlib. **No new
third-party dependency.**

**Storage**: None. Review Memory is in process and host-owned; the layer owns no runtime/loop state and no
storage format (FR-033, FR-062).

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted loops (Phase-3 helpers) + scripted reviewers + scripted answers are the
deterministic instruments (NFR-002, SC-007) — no credentials, no network.

**Target Platform**: Cross-platform library embedded in a host process; pure-composition layer with no
host, transport, or UI dependency (FR-063).

**Project Type**: Single library — one new sub-package (`loopplane.review`) added to the existing
src-layout package, keeping the one-package-per-component-boundary convention from Phases 1–5.

**Performance Goals**: Negligible — the gate is O(1) per review plus the host reviewer's own work.
Determinism preserved (NFR-002).

**Constraints**: `run_loop`-only invocation (FR-012, FR-040, SC-002); public-Loop-State-only reads
(FR-001, FR-040); determinism (NFR-002, SC-007); fail-safe on every failure mode (NFR-005, SC-009);
review observation off by default (FR-052, NFR-006, SC-008); distinct from Phase-1 in-run tool approval
(FR-061); public-safe (NFR-004, SC-010); minimal, reversible surface (NFR-007).

**Scale/Scope**: One new package (~6 modules), one example, one doc, unit/integration/contract suites.
**No Phase-1/2/3 source is modified.**

## Dependency on Phases 1–3

This phase is **strictly additive** and consumes only the Phase-3 review hook plus the public Loop State /
Loop Outcome value types — it composes them and re-derives none of them (NFR-001, FR-060). The exact
surface and the boundary are enumerated in
[contracts/gate-boundary.md](./contracts/gate-boundary.md) and
[research.md](./research.md#inherited-context-no-re-derivation--nfr-001).

**Non-duplication guarantee (FR-060/FR-061, SC-010)**: the layer contains *no* runtime, host, scheduler,
loop, or storage logic, and it does **not** re-implement the Phase-1 Human Approval boundary or the in-run
tool approval/question machinery. It adds only the loop-level review workflow above the public Phase-3
review hook.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.review` depends on `loopplane.engineering`; the loop,
scheduler, packs, host, and core have **zero** knowledge of the review layer.

```text
platform developer
     │ implements a Reviewer; builds a gate
     ▼
loopplane.review.build_review_resolver(reviewer, memory?, asker?, on_event?)
     │ produces a Phase-3 ReviewResolver
     ▼
run_loop(definition, review_resolver=gate)   ◄── Phase-3 (the ONLY path to drive a Loop Run)
     │ at needs_human_review, the loop calls the gate with LoopState
     ▼
gate: build Review Request (public state) → memory? → reviewer(request, context) → decide → map down
     │ returns engineering.ReviewDecision (approve/reject)
     ▼
Review Event stream (distinct; off by default)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/gate-boundary.md](./contracts/gate-boundary.md)):

- The layer drives Loop Runs **only** through `run_loop` (it supplies the resolver) (FR-012, FR-040).
- It reads **only** the public `LoopState` / `LoopOutcome` (FR-001).
- It does **not** import `loopplane.approval.*`, the `InteractionBroker`, or any loop-control internal
  (FR-060, FR-061).

## Project Structure

### Documentation (this feature)

```text
specs/006-loopplane-human-review-workflows/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── review.md            # Review Request, Decision, Reviewer, Context/questions, Memory
│   └── gate-boundary.md     # the gate builder, pause/resume, review events, the boundary
├── checklists/requirements.md
└── tasks.md                 # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/review/
├── __init__.py        # public exports
├── request.py         # ReviewRequest + ReviewCause + build_review_request (FR-001)
├── decision.py        # ReviewOutcome + ReviewDecision + Reviewer + to_phase3_decision (FR-002-FR-004)
├── questions.py       # ReviewQuestion + QuestionAsker + ReviewContext + ReviewError (FR-041-FR-043)
├── memory.py          # RememberMode + ReviewMemory + default_review_key (FR-030-FR-033)
├── events.py          # ReviewEvent vocabulary + REVIEW_SCHEMA_VERSION + sink (FR-050-FR-052)
└── gate.py            # build_review_resolver + inspect_paused + resume_review (FR-010-FR-022)

examples/
└── review_quickstart.py # runnable gated review over a scripted loop (public-safe)

docs/
└── human-review.md    # public-safe guide: reviewer -> gate -> memory -> questions -> pause/resume

tests/
├── unit/
│   └── test_review_core.py     # request building, phase-3 mapping, memory remember-modes, event order
├── integration/
│   ├── test_review_us1.py      # US1: gate approve/reject/request_changes + boundary audit (SC-001/002/003)
│   ├── test_review_us2.py      # US2: pause/inspect/resume (SC-004)
│   ├── test_review_us3.py      # US3: review memory remember-by-key + modes (SC-005)
│   ├── test_review_us4.py      # US4: review questions + fail-safe asker (SC-006/009)
│   └── test_review_us5.py      # US5: review events + observation parity (SC-007/008)
└── contract/
    └── test_review_boundary.py # import-boundary audit (no approval/interaction symbols) + public-safety (SC-002/010)
```

**Structure Decision**: one new sub-package `loopplane.review`, mirroring the Phase-1/2/3/4/5
one-package-per-boundary convention so the review layer is a single, clearly-bounded, independently
revertible addition. It depends inward on Phase 3 only through the public review hook and Loop State value
types. No Phase-1/2/3 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| RA — Request, decision, events | `request.py`, `decision.py`, `events.py` (+ `to_phase3_decision`) + package skeleton | `test_review_core.py` (request + mapping + event order) green | Revert package; nothing depends on it |
| RB — Gate (US1) | `gate.py`: `build_review_resolver` approve/reject/request_changes + fail-safe; Review Events | `test_review_us1.py` green incl. boundary audit (SC-001/002/003) | Revert to RA |
| RC — Pause/resume (US2) | `inspect_paused`, `resume_review` (in-process) | `test_review_us2.py` green (SC-004) | Revert pause/resume |
| RD — Memory (US3) | `memory.py`: remember-by-key + modes; gate memory wiring | `test_review_us3.py` green (SC-005) | Revert memory |
| RE — Questions (US4) | `questions.py`: `ReviewContext`/`ask`/`QuestionAsker` + fail-safe; gate question wiring | `test_review_us4.py` green (SC-006/009) | Revert questions |
| RF — Events parity, example, docs (US5) | observation parity; `examples/review_quickstart.py`; `docs/human-review.md`; boundary + public-safety tests | `test_review_us5.py` + `test_review_boundary.py` green; example runs; scan clean (SC-008/010) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Reaching into the Phase-1 approval/question machinery | Import-boundary audit asserts `loopplane.review` imports only `loopplane.engineering` + stdlib and references no `loopplane.approval` / `InteractionBroker` / `LoopController` symbol (FR-061, NFR-003, SC-002) |
| A silent approve on a faulted/ambiguous review | Every fail-safe maps to a non-approval decision with a diagnostic; dedicated fail-safe tests (FR-013, NFR-005, SC-009) |
| Review questions hanging with no asker | `ask` with no asker raises `ReviewError`; a raising asker → diagnostic + empty answer; tests assert no hang (FR-043) |
| Non-determinism creeps in | The layer does no I/O/network; memory/key derivation pure; a determinism test runs a gated review twice (NFR-002, SC-007) |
| Observation changes behavior | Off by default; parity test compares observed vs unobserved decision/outcome (NFR-006, SC-008) |
| Scope creeps into UI / external storage / multi-reviewer | Out-of-scope list forbidden by FR-062–FR-063; Constitution III review gate; durable resume reserved (FR-022) |
| A secret leaks via a request/decision | Requests/decisions carry no secrets; reviewers/askers/keys are host objects; public-safety scan over committed files (NFR-004, SC-010) |

**Rollback posture**: `loopplane.review` is purely **additive** over Phases 1–3 — small, task-scoped
commits, each phase (RA–RF) independently revertible. The layer owns no state and no storage, so reverting
any or all leaves the loop, scheduler, packs, and runtime behavior untouched. Observation defaults off.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.review` package written fresh; composes the Phase-3 public hook only; no legacy code copied (FR-060) |
| III | Agent Harness Before Loop Automation | PASS | This is the structured human-review workflow Phase 3 left as a bare hook; it stays minimal, ships **no** UI/external store/multi-reviewer, and names every reserved extension point (FR-062, NFR-007) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (compose a review workflow into a Phase-3 resolver); depends inward on Phase 3; boundary table assigns ownership; distinct from the Phase-1 approval boundary (FR-060, FR-061) |
| V | Tool Gateway Ownership | PASS | The layer resolves/authorizes/executes no tools; in-run tool approval stays the Phase-1 boundary, untouched (FR-061) |
| VI | Runtime Event Bus Ownership | PASS | Consumes no Runtime Events; emits a **distinct** Review Event stream that never wraps/re-emits Loop or Runtime Events; versioned + unknown-type tolerant (FR-050) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; requests/decisions carry no secrets (FR-004, NFR-004); example/docs public-safe; scan extended (SC-010) |
| VIII | No SDK Replacement | PASS | No agent/review framework introduced; pure stdlib composition over LoopPlane's own loop layer |
| IX | Reference, Not Clone | PASS | Review-workflow concepts re-derived public-safe from the spec and the Phase-3 hook; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (RA–RF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; observation default-off; determinism + fail-safe first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and no
Phase-1/2/3 modification. The only mutable entity (`ReviewMemory`) is host-owned and in-process.
Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
