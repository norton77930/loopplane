# Quickstart & Validation Guide: Validator & Evaluator Packs

**Feature**: `005-loopplane-validator-evaluator-packs` | **Spec**: [spec.md](./spec.md) |
**Plan**: [plan.md](./plan.md)

Runnable scenarios that prove each pack works against a scripted `RunOutcome` through the **public**
Phase-3 surface only. Every pack is deterministic and credential-free; no I/O, no network.

## Prerequisites

- Phases 1–3 merged (`loopplane.engineering` importable, incl. the Validator/Evaluator Protocols).
- Dev install: `pip install -e .[dev]` (pytest + anyio; `jsonschema` is a core dependency).
- The pack tests build scripted `RunOutcome`/`LoopState` fixtures (or reuse the Phase-3 host helpers).

## Run the validation suite

```powershell
pytest tests/unit/test_packs_core.py `
       tests/integration/test_packs_us1.py `
       tests/integration/test_packs_us2.py `
       tests/integration/test_packs_us3.py `
       tests/integration/test_packs_us4.py `
       tests/integration/test_packs_us5.py `
       tests/contract/test_packs_boundary.py
```

## Minimal example (design intent)

```python
from loopplane.engineering import ValidationPolicy
from loopplane.packs import text_validator, all_of, artifact_presence_validator

policy = ValidationPolicy(
    validator=all_of(
        text_validator(mode="contains", pattern="done"),
        artifact_presence_validator(require=False),
    )
)
# ... plug `policy` into a LoopDefinition's validation_policy and run_loop(...)
```

## Scenario → requirement map

| # | Scenario | Asserts | Maps to |
|---|---|---|---|
| 1 | Outcome reader | extracts terminal reason, final assistant text, artifact refs from a scripted outcome | US1, FR-002 |
| 2 | Rule-based validator | predicate true ⇒ pass; false ⇒ fail with reason | US1.1–2, SC-003 |
| 3 | Determinism | a pack applied twice to the same outcome returns equal results | US1.4, SC-007 |
| 4 | Boundary audit | the pack reads only the public surface; no Phase-1/2/3 internal called | US1, SC-002, NFR-003 |
| 5 | Text validator (contains / matches) | pattern present ⇒ pass; absent ⇒ fail | US2.1, SC-003 |
| 6 | Text validator (not_contains) | forbidden pattern present ⇒ fail | US2.2, FR-011 |
| 7 | Invalid regex | rejected at construction (`PackConfigError`) | US2, FR-011 |
| 8 | JSON-schema validator | valid JSON+schema ⇒ pass; schema-invalid ⇒ fail with reason | US2.3, SC-003 |
| 9 | Unparseable JSON | fail-safe fail with a reason (never silent pass) | US2.4, SC-008 |
| 10 | Scoring evaluator | returns the computed score; non-gating | US3.1, SC-004 |
| 11 | Label evaluator | returns the expected categorical label | US3.2, FR-021 |
| 12 | Length evaluator | normalized score in [0, 1] for short/long output | US3.3, SC-004 |
| 13 | Evaluator non-gating | no evaluator forces a validation decision | US3.4, FR-023 |
| 14 | Raising scoring function | non-fatal diagnostic, score=None | US3, SC-008 |
| 15 | all-of combinator | all pass ⇒ pass; any fail ⇒ most-cautious status | US4.1, SC-005 |
| 16 | any-of combinator | ≥1 pass ⇒ pass; all fail ⇒ most-cautious | US4.2, SC-005 |
| 17 | Combinator precedence | review/repair not downgraded; empty defaults | US4.3, FR-031/FR-034 |
| 18 | Threshold gate | score ≥ threshold ⇒ pass; below ⇒ configured fail/needs_repair | US4.4, SC-006 |
| 19 | Threshold gate, missing score | fail-safe fail with a reason | US4, FR-033, SC-008 |
| 20 | Artifact-presence validator | require=True ⇒ pass with artifact; require=False ⇒ pass without | US5.1–2, SC-003 |
| 21 | Fail-safe on degenerate outcome | every pack returns an explicit result, never a silent pass | US5.3, SC-008 |
| 22 | Example reproduces output | the example plugs packs into a policy and reproduces documented results | US5.4, SC-009 |
| 23 | Public-safety scan | committed Phase-5 files contain zero private references | SC-010, NFR-004 |

## Rollback

The `loopplane.packs` package is **purely additive** over Phases 1–3. Reverting the feature's commits
removes the package, example, docs, and tests and leaves the Phase-1/2/3 layers untouched (packs own no
runtime/loop/scheduler state and no storage). Packs are pure functions, so a partial revert can never
change loop or scheduler behavior.
