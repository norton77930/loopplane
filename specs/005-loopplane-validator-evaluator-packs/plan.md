# Implementation Plan: Validator & Evaluator Packs

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-loopplane-validator-evaluator-packs/spec.md`

## Summary

Ship a library of reusable, deterministic, public-safe **packs** — concrete implementations of the
Phase-3 Validator and Evaluator Protocol contracts that a Loop Definition plugs straight into its
`validation_policy` and `evaluation_policy`. A pack is a **pure callable** that reads only the public
`RunOutcome`/`LoopState` surface (through a shared outcome reader) and returns a Phase-3
`ValidationResult` or `EvaluationResult`; it never starts/drives runs and never reaches into Phase-1/2/3
internals (FR-040, FR-041). The deliverable is one new additive sub-package, `loopplane.packs`,
providing: an outcome reader; rule-based / text-regex / JSON-schema / artifact-presence **validators**;
scoring / label / length **evaluators**; all-of / any-of **combinators** and a **threshold gate** (the
single evaluation-to-gating conversion) — plus public-safe examples, a doc, and unit/integration/contract
suites. Every pack is deterministic and fails safe. Design detail lives in [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–3).

**Primary Dependencies**: The Phase-3 `loopplane.engineering` public contracts and value types
(`Validator`, `Evaluator`, `ValidationResult`, `ValidationStatus`, `EvaluationResult`, `RunOutcome`,
`LoopState`); the stdlib (`re`, `json`); and the existing core `jsonschema` dependency for the
JSON-schema validator. **No new third-party dependency.**

**Storage**: None. Packs are stateless pure functions; they hold no run, loop, or scheduler state.

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted `RunOutcome`/`LoopState` fixtures (built directly or via the Phase-3 host
helpers) are the deterministic instruments (NFR-002, SC-007) — no credentials, no network.

**Target Platform**: Cross-platform library embedded in a host process; pure-function packs add no host,
transport, scheduler, or storage dependency.

**Project Type**: Single library — one new sub-package (`loopplane.packs`) added to the existing
src-layout package, keeping the one-package-per-component-boundary convention from Phases 1–3.

**Performance Goals**: Negligible — each pack is O(output size) string/JSON work. Determinism preserved
(NFR-002).

**Constraints**: Public-surface-only reads (FR-002, FR-040, SC-002); determinism (NFR-002, SC-007);
fail-safe on malformed input (FR-014, NFR-005, SC-008); evaluation non-gating except the threshold gate
(FR-023, FR-032); public-safe with no secrets/domain data (FR-004, NFR-004, SC-010); minimal, reversible
surface (NFR-006).

**Scale/Scope**: One new package (~5 modules), one example, one doc, unit/integration/contract suites.
**No Phase-1/2/3 source is modified.**

## Dependency on Phases 1–3

This phase is **strictly additive** and consumes only the Phase-3 public contracts and value types — it
*implements* the Validator/Evaluator Protocols and reads `RunOutcome`/`LoopState`, and re-derives none of
them (NFR-001, FR-040). The exact surface and the boundary are enumerated in
[contracts/combinators-boundary.md](./contracts/combinators-boundary.md) and
[research.md](./research.md#inherited-context-no-re-derivation--nfr-001).

**Non-duplication guarantee (FR-040, SC-010)**: the packs contain *no* runtime, host, scheduler, loop, or
storage logic; they add only the domain-agnostic validation/evaluation building blocks Phase 3 left as a
policy boundary, above the public contract.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.packs` depends on `loopplane.engineering` (contracts
+ value types); the loop, scheduler, host, and core have **zero** knowledge of the packs.

```text
loop engineer
     │  composes a ValidationPolicy / EvaluationPolicy from packs
     ▼
loopplane.packs  ──implements──►  Phase-3 Validator / Evaluator Protocol
     │  reads (only)
     ▼
read_outcome(RunOutcome, LoopState) -> OutcomeView   (public surface only)
     │  returns
     ▼
ValidationResult / EvaluationResult  ──►  consumed by run_loop (Phase-3)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/combinators-boundary.md](./contracts/combinators-boundary.md)):

- A pack implements the Phase-3 contract and reads the public `RunOutcome`/`LoopState` **only** through
  the outcome reader (FR-002, FR-040).
- A pack starts/drives/schedules/observes **no** runs (FR-041).
- Only the **threshold gate** converts an evaluation score into a gating decision (FR-032).

## Project Structure

### Documentation (this feature)

```text
specs/005-loopplane-validator-evaluator-packs/
├── spec.md                 # Feature specification (complete)
├── plan.md                 # This file (/speckit.plan output)
├── research.md             # Phase 0: design decisions
├── data-model.md           # Phase 1: pack-layer entities
├── quickstart.md           # Phase 1: validation/run guide
├── contracts/              # Phase 1: interface contracts
│   ├── packs.md                 # Outcome reader + validators + evaluators
│   └── combinators-boundary.md  # Combinators + threshold gate + the public-surface boundary
├── checklists/
│   └── requirements.md     # Spec quality checklist (complete)
└── tasks.md                # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/packs/
├── __init__.py        # public exports (read_outcome, OutcomeView, validators, evaluators, combinators, PackConfigError)
├── reader.py          # OutcomeView + read_outcome over the public surface (FR-002)
├── validators.py      # rule / text / json_schema / artifact_presence validators + PackConfigError (FR-010-FR-014)
├── evaluators.py      # scoring / label / length evaluators (non-gating) (FR-020-FR-023)
└── combinators.py     # all_of / any_of + threshold_gate (FR-030-FR-034)

examples/
└── packs_quickstart.py # runnable example: compose packs into a policy over a scripted outcome (public-safe)

docs/
└── packs.md           # public-safe guide: outcome reader -> validators -> evaluators -> combinators -> gate

tests/
├── unit/
│   └── test_packs_core.py     # outcome reader, regex/JSON/length math, combinator precedence, fail-safe units
├── integration/
│   ├── test_packs_us1.py      # US1: outcome reader + rule validator + boundary audit + determinism (SC-001/002)
│   ├── test_packs_us2.py      # US2: text + JSON-schema validators incl. fail-safe (SC-003/008)
│   ├── test_packs_us3.py      # US3: scoring / label / length evaluators, non-gating (SC-004)
│   ├── test_packs_us4.py      # US4: all-of / any-of combinators + threshold gate (SC-005/006)
│   └── test_packs_us5.py      # US5: artifact validator + fail-safe edges + example (SC-008/009)
└── contract/
    └── test_packs_boundary.py # import-boundary audit + public-surface-only + determinism + public-safety (SC-002/010)
```

**Structure Decision**: one new sub-package `loopplane.packs`, mirroring the Phase-1/2/3
one-package-per-boundary convention so the pack library is a single, clearly-bounded, independently
revertible addition. The package name maps to the feature (validator/evaluator **packs**). It is distinct
from `loopplane.engineering` (whose contracts it implements) and depends inward on it only through the
public Validator/Evaluator Protocols and value types. No Phase-1/2/3 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| PA — Reader + rule (US1) | `reader.py` (OutcomeView + read_outcome) + `validators.rule_validator`; package skeleton | `test_packs_us1.py` + reader units green; boundary audit (SC-001/002) | Revert package; nothing depends on it |
| PB — Text + JSON-schema (US2) | `text_validator`, `json_schema_validator` + `PackConfigError`, with fail-safe | `test_packs_us2.py` green incl. fail-safe (SC-003/008) | Revert to reader+rule |
| PC — Evaluators (US3) | `evaluators.py`: scoring / label / length, non-gating | `test_packs_us3.py` green (SC-004) | Revert evaluators |
| PD — Combinators + gate (US4) | `combinators.py`: all_of / any_of precedence + threshold_gate | `test_packs_us4.py` green (SC-005/006) | Revert combinators |
| PE — Artifact + edges + example + docs (US5) | `artifact_presence_validator`; fail-safe edges; `examples/packs_quickstart.py`; `docs/packs.md`; extend public-safety scan | `test_packs_us5.py` + `test_packs_boundary.py` green; example runs; scan clean (SC-008/010) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| A pack reaches past the public outcome surface | Import-boundary audit asserts `loopplane.packs` imports only `loopplane.engineering` + stdlib + `jsonschema` (FR-040, NFR-003, SC-002); all reads go through the one outcome reader |
| A silent pass on malformed input | Every pack fails safe to an explicit `fail`/diagnostic with a reason; a dedicated fail-safe test per pack (NFR-005, SC-008) |
| Evaluation leaks into gating | Evaluators return only `EvaluationResult`; only the threshold gate converts (FR-032); a test asserts no evaluator gates (SC-004) |
| Combinators downgrade a cautious status | A documented, order-independent precedence (review > repair > fail > pass) with a precedence test (FR-031, SC-005) |
| Non-determinism creeps in | Packs do no I/O/network; deterministic stdlib (`re`, `json`, `jsonschema`); a determinism test applies each pack twice (NFR-002, SC-007) |
| A secret/domain datum leaks via a pack | Packs carry no domain data; config is host-supplied; examples use public-safe values; public-safety scan over committed files (NFR-004, SC-010) |
| Scope creeps into LLM-judge / ML / external calls | Out-of-scope list forbidden by FR-042–FR-043; Constitution III/VIII review gate |

**Rollback posture**: `loopplane.packs` is purely **additive** over Phases 1–3 — small, task-scoped
commits, each phase (PA–PE) independently revertible. Packs are pure functions owning no state, so
reverting any or all leaves the loop, scheduler, and runtime behavior untouched.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.packs` package written fresh; composes the Phase-3 public contracts only; no legacy code copied (FR-040) |
| III | Agent Harness Before Loop Automation | PASS | This is the reusable validator/evaluator library Phase 3 left as a policy boundary; it stays minimal, ships **no** LLM-judge/ML/external capability, and names every reserved extension point (FR-042, NFR-006) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (implement the Validator/Evaluator contracts); depends inward on Phase 3; boundary table assigns ownership; no lower-layer boundary blurred (FR-040) |
| V | Tool Gateway Ownership | PASS | Packs resolve/authorize/execute no tools; they read a `RunOutcome` and return a result — all tool execution stays in Phase 1, untouched (FR-041) |
| VI | Runtime Event Bus Ownership | PASS | Packs consume no events and emit none; they read the `RunOutcome`/`LoopState` value the loop already produced (FR-002, FR-041) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names/domain data in any artifact (FR-004, NFR-004); example/docs public-safe; scan extended (SC-010) |
| VIII | No SDK Replacement | PASS | No agent/eval framework introduced; pure stdlib + the existing `jsonschema` core dependency |
| IX | Reference, Not Clone | PASS | Validation/evaluation concepts re-derived public-safe from the spec and Phase-3 contracts; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (PA–PE) has required tests, a validation gate, and a rollback note; packs are additive, pure, and revertible; determinism + fail-safe are first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and no
Phase-1/2/3 modification. Packs are stateless pure functions. Complexity Tracking is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
