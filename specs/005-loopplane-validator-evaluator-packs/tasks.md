---
description: "Task list for Validator & Evaluator Packs (005)"
---

# Tasks: Validator & Evaluator Packs

**Input**: Design documents from `/specs/005-loopplane-validator-evaluator-packs/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each user-story phase writes its tests first (they must
FAIL before implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5). Phases PA–PE in
[plan.md](./plan.md#implementation-phases) map below (Foundational reader = part of PA; US1 = rest of PA,
US2 = PB, US3 = PC, US4 = PD, US5 = PE).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/packs/`.

## Boundary reminder (every implementation task)

A pack implements a Phase-3 Validator/Evaluator Protocol and reads **only** the public
`RunOutcome`/`LoopState` surface through the outcome reader. It MUST NOT import or call any Phase-1/2
internal or the Phase-3 `LoopController` mechanics — only `loopplane.engineering` public symbols, the
stdlib, and the existing `jsonschema` core dependency. See
[contracts/combinators-boundary.md](./contracts/combinators-boundary.md). No Phase-1/2/3 source is
modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create the `loopplane.packs` package skeleton: `src/loopplane/packs/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [ ] T002 [P] Add pack test helpers in `tests/packs_helpers.py`: a `scripted_outcome(*, text="", terminal="natural-completion", artifacts=())` builder returning a Phase-3 `RunOutcome` + `LoopState` pair for pure-pack tests (reusing Phase-3 value types).

---

## Phase 2: Foundational (Blocking Prerequisites — outcome reader)

**Purpose**: The outcome reader that every pack uses. **⚠️ Blocks US1–US5.**

- [ ] T003 [P] Write unit tests in `tests/unit/test_packs_core.py` (MUST FAIL first): `read_outcome` extracts the terminal reason, the last assistant entry's concatenated `TextBlock` text (empty when none), and the artifact references from `state.artifacts`; the combinator status-precedence helper; and the length/JSON math.
- [ ] T004 Implement `src/loopplane/packs/reader.py`: `OutcomeView` + `read_outcome(outcome, state)` reading only the public surface (FR-002).
- [ ] T005 Populate `src/loopplane/packs/__init__.py` exports for `OutcomeView` and `read_outcome`.
- [ ] T006 Run `pytest tests/unit/test_packs_core.py` → green (reader + helpers).

**Checkpoint**: The shared reader is ready — pack work can begin.

---

## Phase 3: User Story 1 - Read a run outcome and gate on a rule (Priority: P1) 🎯 MVP

**Goal**: A rule-based validator reads the outcome via the reader, applies a host predicate, and returns
`pass`/`fail` — reading only the public surface.

**Independent Test**: Build a scripted `RunOutcome`, apply a rule-based validator, and assert `pass` /
`fail` per the predicate, deterministically.

- [ ] T007 [P] [US1] Write integration tests in `tests/integration/test_packs_us1.py` (MUST FAIL first): `rule_validator` returns `pass` when the predicate holds and `fail` (with a reason) otherwise; a raising predicate fails safe to `fail`; the result plugs into a Phase-3 `ValidationPolicy`; applied twice it returns equal results (determinism); a boundary audit that only the public surface was read (US1 scenarios 1–4; SC-001, SC-002, SC-007).
- [ ] T008 [US1] Implement `src/loopplane/packs/validators.py` with `rule_validator(predicate, *, reason=...)` and `PackConfigError`, returning a Phase-3 `Validator` callable; fail-safe on a raising predicate (depends on T004) (FR-010, FR-014).
- [ ] T009 [US1] Export `rule_validator`, `PackConfigError` from `src/loopplane/packs/__init__.py`.
- [ ] T010 [US1] Run `pytest tests/integration/test_packs_us1.py` → green (boundary audit + determinism).

**Checkpoint**: MVP — a pack gates a loop on a rule through the public surface.

---

## Phase 4: User Story 2 - Validate text and structured output (Priority: P2)

**Goal**: Text/regex and JSON-schema validators return `pass`/`fail` with reasons and fail safe on
malformed input.

**Independent Test**: Apply the text validator to matching/non-matching outputs; apply the JSON-schema
validator to valid, schema-invalid, and non-JSON outputs and assert `pass`/`fail`/fail-safe-`fail`.

- [ ] T011 [P] [US2] Write integration tests in `tests/integration/test_packs_us2.py` (MUST FAIL first): `text_validator` `contains`/`matches`/`not_contains` modes (pass/fail); an invalid regex raises `PackConfigError` at construction; `json_schema_validator` ⇒ `pass` on valid JSON+schema, `fail` on a schema violation, and a **fail-safe** `fail` on unparseable JSON — never a silent pass (US2 scenarios 1–4; SC-003, SC-008).
- [ ] T012 [US2] Implement `text_validator(*, mode, pattern, reason=None)` in `validators.py`: compile the regex at construction (`PackConfigError` on an invalid pattern); apply `re.fullmatch`/`re.search` over `final_text` (depends on T008) (FR-011).
- [ ] T013 [US2] Implement `json_schema_validator(*, schema)` in `validators.py`: parse `final_text` with stdlib `json` and validate with `jsonschema`; `fail` with the reason on a violation, fail-safe `fail` on unparseable JSON (depends on T008) (FR-012, FR-014).
- [ ] T014 [US2] Run `pytest tests/integration/test_packs_us2.py` → green (SC-003, SC-008).

**Checkpoint**: Text and structured-output validation work and fail safe.

---

## Phase 5: User Story 3 - Score and label iterations (Priority: P3)

**Goal**: Scoring, label, and length/heuristic evaluators return `EvaluationResult`s and never gate.

**Independent Test**: Apply each evaluator to a scripted outcome and assert the score/label; confirm
non-gating and `[0, 1]` length scores.

- [ ] T015 [P] [US3] Write integration tests in `tests/integration/test_packs_us3.py` (MUST FAIL first): `scoring_evaluator` returns the computed score (and `None` with a reason when the scoring function raises); `label_evaluator` returns the expected categorical label; `length_evaluator` returns a normalized score in `[0, 1]`; no evaluator returns a `ValidationResult` or gates (US3 scenarios 1–4; SC-004, SC-008).
- [ ] T016 [US3] Implement `src/loopplane/packs/evaluators.py`: `scoring_evaluator(score_fn, *, label=None)`, `label_evaluator(rules, *, default)`, `length_evaluator(*, target_chars)` returning Phase-3 `Evaluator` callables; a raising `score_fn` ⇒ non-fatal diagnostic (`score=None`) (depends on T004) (FR-020–FR-023).
- [ ] T017 [US3] Export the evaluators from `__init__.py`; run `pytest tests/integration/test_packs_us3.py` → green (SC-004).

**Checkpoint**: Non-gating evaluators work.

---

## Phase 6: User Story 4 - Compose validators and gate on a score (Priority: P4)

**Goal**: all-of / any-of combinators with documented precedence, and a threshold gate (the single
evaluation-to-gating conversion).

**Independent Test**: Compose validators with all-of/any-of and assert the combined status per the
precedence; build a threshold gate and assert score-based gating + fail-safe on a missing score.

- [ ] T018 [P] [US4] Write integration tests in `tests/integration/test_packs_us4.py` (MUST FAIL first): `all_of` passes iff all pass and otherwise yields the most-cautious status; `any_of` passes iff ≥1 passes; a `needs_human_review`/`needs_repair` sub-result is never downgraded; empty `all_of` ⇒ `pass`, empty `any_of` ⇒ `fail`; `threshold_gate` ⇒ `pass` at/above threshold, configured `fail`/`needs_repair` below, and fail-safe `fail` on a missing score (US4 scenarios 1–4; SC-005, SC-006, SC-008).
- [ ] T019 [US4] Implement `src/loopplane/packs/combinators.py`: `all_of(*validators)` / `any_of(*validators)` with the documented status precedence (`needs_human_review` > `needs_repair` > `fail` > `pass`) and empty defaults (depends on T008) (FR-030, FR-031, FR-034).
- [ ] T020 [US4] Implement `threshold_gate(evaluator, *, threshold, below="fail")` in `combinators.py`: run the evaluator, gate on the score, fail-safe on a missing score — the only evaluation-to-gating pack (depends on T016) (FR-032, FR-033).
- [ ] T021 [US4] Export the combinators + gate from `__init__.py`; run `pytest tests/integration/test_packs_us4.py` → green (SC-005, SC-006).

**Checkpoint**: Composition and the single gating conversion work.

---

## Phase 7: User Story 5 - Validate artifacts and keep edges honest (Priority: P5)

**Goal**: artifact-presence validator; every pack's fail-safe on degenerate input; example + docs.

**Independent Test**: Apply the artifact validator to outcomes with/without artifacts; apply each pack to
an empty outcome and assert an explicit fail-safe result; run the example.

- [ ] T022 [P] [US5] Write integration tests in `tests/integration/test_packs_us5.py` (MUST FAIL first): `artifact_presence_validator(require=True/False)` ⇒ correct pass/fail on `artifact_references` presence/absence; every pack applied to an empty/degenerate outcome returns an explicit result (fail-safe), never a silent pass (US5 scenarios 1–4; SC-003, SC-008).
- [ ] T023 [US5] Implement `artifact_presence_validator(*, require=True)` in `validators.py` reading `OutcomeView.artifact_references` (depends on T008) (FR-013).
- [ ] T024 [P] [US5] Create `examples/packs_quickstart.py`: compose packs (text + artifact + threshold gate) into a `ValidationPolicy`/`EvaluationPolicy` and apply them to a scripted outcome, printing the results (public-safe).
- [ ] T025 [P] [US5] Write `docs/packs.md`: a public-safe guide (outcome reader → validators → evaluators → combinators → threshold gate) that points at the Phase-3 contract boundary.
- [ ] T026 [US5] Run `pytest tests/integration/test_packs_us5.py` → green (SC-003, SC-008).

**Checkpoint**: Artifact validation and fail-safe edges close the phase scope.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T027 [P] Write `tests/contract/test_packs_boundary.py`: an import-boundary audit asserting `loopplane.packs` imports only `loopplane.engineering` (+ stdlib + `jsonschema`) and no Phase-1/2 internal or `LoopController` mechanics; a public-surface-only assertion (no pack starts a run, SC-002); and a determinism check (each pack applied twice returns equal results, SC-007) (NFR-003).
- [ ] T028 Extend `tests/contract/test_public_safety.py` to include all committed Phase-5 files (`src/loopplane/packs/`, `examples/packs_quickstart.py`, `docs/packs.md`, `specs/005-*`) so the scan finds zero private references (SC-010, NFR-004).
- [ ] T029 [P] Execute the [quickstart.md](./quickstart.md) scenarios end-to-end as a smoke check and reconcile any drift.
- [ ] T030 Final validation: full `pytest` green, `ruff format --check` + `ruff check` clean, `mypy` clean, `git diff --check` clean (board §10).
- [ ] T031 Update `docs/loopplane-agent-board.md`: advance unit 005 status (→ Verified) and its Next Action; set the active feature to 006.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational reader (Phase 2)** blocks all stories → **US1–US5** (US1 creates
  `validators.py`; US2/US5 extend it; US3 adds `evaluators.py`; US4 adds `combinators.py`) → **Polish**.
- US4's threshold gate depends on the evaluators (US3); the other stories are otherwise independent given
  the reader.

### Parallel opportunities

- The reader unit test (T003) and helpers (T002) are [P].
- Each story's test task (T007, T011, T015, T018, T022) is [P] and written first (must fail).
- `evaluators.py` (US3) and `validators.py` extensions are different files — US3 ∥ US2 after US1.
- US5 docs/example (T024, T025) are [P]; Polish T027 ∥ T029.

---

## Implementation Strategy

### MVP first (US1)

Setup → Foundational reader → US1 (rule validator) → **STOP & VALIDATE**: a pack gates a loop on a rule
through the public surface (SC-001/002).

### Incremental delivery

Reader → US1 (MVP) → US2 (text/JSON) → US3 (evaluators) → US4 (combinators/gate) → US5 (artifact/edges)
→ Polish. Each story is an independently testable increment; commit after each green checkpoint and push
(board §10–11).

---

## Notes

- [P] = different files. `validators.py` is shared by US1/US2/US5; sequence those edits.
- Tests are written first per story and must FAIL before implementation (Constitution X).
- Every pack is a pure function reading only the public surface; no I/O, no network, deterministic.
