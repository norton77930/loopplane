---
description: "Task list for Human Review Workflows (006)"
---

# Tasks: Human Review Workflows

**Input**: Design documents from `/specs/006-loopplane-human-review-workflows/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each user-story phase writes its tests first (they must
FAIL before implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5). Phases RA–RF in
[plan.md](./plan.md#implementation-phases) map below (Foundational = RA, US1 = RB, US2 = RC, US3 = RD,
US4 = RE, US5 = RF).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/review/`.

## Boundary reminder (every implementation task)

The layer composes only the Phase-3 public surface (`run_loop`, `ReviewResolver`, `ReviewDecision`,
`LoopState`, `LoopOutcome`, `LoopDefinition`) and reads only the public Loop State. It MUST NOT import or
reference any Phase-1 approval/interaction symbol (`loopplane.approval.*`, `InteractionBroker`), any
Phase-2 host internal, or the Phase-3 `LoopController` mechanics. See
[contracts/gate-boundary.md](./contracts/gate-boundary.md). No Phase-1/2/3 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create the `loopplane.review` package skeleton: `src/loopplane/review/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [ ] T002 [P] Add review test helpers in `tests/review_helpers.py`: a `needs_review_definition(...)` builder (a Phase-3 loop whose validator returns `needs_human_review`, reusing `tests/loop_helpers.py`), `scripted_reviewer(outcome, *, reason=None, asks=None)`, `scripted_asker(*answers)`, and a `ReviewEventRecorder` sink.

---

## Phase 2: Foundational (Blocking Prerequisites — RA: request, decision, events, context)

**Purpose**: The value types and the Phase-3 mapping every later phase composes. **⚠️ Blocks US1–US5.**

- [ ] T003 [P] Write unit tests in `tests/unit/test_review_core.py` (MUST FAIL first): `build_review_request` extracts loop id / definition id / iteration / session ref / cause (validator_status vs fail_safe) / validation status+reason / artifact refs from a scripted `LoopState`; `to_phase3_decision` maps approve→approve=True and reject/request_changes→approve=False (never a silent approve); `default_review_key` returns the loop id.
- [ ] T004 [P] Implement `src/loopplane/review/request.py`: `ReviewRequest`, `ReviewCause`, `build_review_request(state, *, options=...)` reading only the public Loop State (FR-001).
- [ ] T005 [P] Implement `src/loopplane/review/decision.py`: `ReviewOutcome`, `ReviewDecision`, the `Reviewer` Protocol, and `to_phase3_decision` (FR-002–FR-004).
- [ ] T006 [P] Implement `src/loopplane/review/events.py`: `REVIEW_SCHEMA_VERSION`, `ReviewEventType` (the five types), frozen `ReviewEvent`, and `ReviewEventSink` (FR-050–FR-051).
- [ ] T007 [P] Implement `src/loopplane/review/questions.py`: `ReviewQuestion`, `QuestionAsker`, `ReviewContext` (with `ask`), and `ReviewError` (the class + no-asker fail-safe; the full ask/emit flow is wired in US4) (FR-041, FR-043).
- [ ] T008 Populate `src/loopplane/review/__init__.py` exports for the foundational types + `default_review_key`.
- [ ] T009 Run `pytest tests/unit/test_review_core.py` → green (gate for RA).

**Checkpoint**: The review vocabulary and the Phase-3 mapping are ready.

---

## Phase 3: User Story 1 - Gate a loop on a human reviewer (Priority: P1) 🎯 MVP

**Goal**: A review gate built from a reviewer drives a loop at `needs_human_review` — approve →
`loop_completed`, reject/request_changes → `loop_failed` — reading only the public Loop State.

**Independent Test**: Build a gate from a scripted approving reviewer, run a needs-review loop, assert it
completes; reject → assert it fails; assert the Review Request carried the loop id / iteration / run ref /
reason.

- [ ] T010 [P] [US1] Write integration tests in `tests/integration/test_review_us1.py` (MUST FAIL first): an approving gate ⇒ `loop_completed`; a rejecting gate ⇒ `loop_failed` with the reason; `request_changes` ⇒ non-approval (`loop_failed`); a raising/unrecognized reviewer fails safe to a non-approval with a diagnostic (never a silent approve); the Review Request carries loop id / iteration / session ref / validation reason; the run is driven only through `run_loop`; a gated review run twice is identical (US1 scenarios 1–4; SC-001/002/003/007).
- [ ] T011 [US1] Implement `src/loopplane/review/gate.py`: `build_review_resolver(reviewer, *, memory=None, asker=None, on_event=None, options=...)` returning an async Phase-3 `ReviewResolver` that builds the Review Request, emits `review_requested`, invokes the reviewer with a `ReviewContext`, fails safe on a raised/unknown outcome, emits `review_decided`, and returns `to_phase3_decision(...)` (depends on Phase 2) (FR-010–FR-013).
- [ ] T012 [US1] Export `build_review_resolver` from `src/loopplane/review/__init__.py`; run `pytest tests/integration/test_review_us1.py` → green (boundary audit + determinism).

**Checkpoint**: MVP — the human gate loop drives a loop through the Phase-3 hook.

---

## Phase 4: User Story 2 - Pause, inspect, and resume a review (Priority: P2)

**Goal**: A no-resolver run pauses; `inspect_paused` returns the Review Request; `resume_review` drives
the loop with a supplied decision — in process.

**Independent Test**: Run with no gate, assert it pauses, `inspect_paused` returns the request; resume
with approve ⇒ completes, reject ⇒ fails.

- [ ] T013 [P] [US2] Write integration tests in `tests/integration/test_review_us2.py` (MUST FAIL first): a no-resolver run pauses and `inspect_paused` returns a Review Request matching the paused state; `inspect_paused` on a terminal outcome returns `None`; `resume_review` with approve ⇒ `loop_completed`, reject ⇒ `loop_failed`; resume drives only through `run_loop` and writes nothing to disk (US2 scenarios 1–4; SC-004).
- [ ] T014 [US2] Implement `inspect_paused(outcome)` and `resume_review(definition, decision, *, on_event=None, on_approval=None)` in `gate.py` (in-process re-drive via `run_loop` with a one-shot mapped resolver; durable resume reserved) (depends on T011) (FR-020–FR-022).
- [ ] T015 [US2] Export `inspect_paused`, `resume_review`; run `pytest tests/integration/test_review_us2.py` → green (SC-004).

**Checkpoint**: Out-of-band pause/inspect/resume works in process.

---

## Phase 5: User Story 3 - Remember review decisions (Priority: P3)

**Goal**: Review Memory remembers decisions by key so a repeated review auto-resolves; configurable
remember modes; keys isolated.

**Independent Test**: Two reviews with the same key through a gate with memory ⇒ reviewer invoked once;
approvals-only mode ⇒ a rejection re-invokes next time; a memory hit emits `review_resolved_from_memory`.

- [ ] T016 [P] [US3] Write integration tests in `tests/integration/test_review_us3.py` (MUST FAIL first): same key twice ⇒ reviewer invoked once, second resolves from memory to the same decision; `remember="approvals"` ⇒ a rejection is not remembered (reviewer re-invoked); a memory hit emits `review_resolved_from_memory`; two different keys never resolve each other (US3 scenarios 1–4; SC-005).
- [ ] T017 [US3] Implement `src/loopplane/review/memory.py`: `RememberMode`, `default_review_key`, `ReviewMemory` (`recall` / `remember_decision`), and wire memory into `build_review_resolver` (recall before the reviewer; remember after; emit `review_resolved_from_memory` on a hit) (depends on T011) (FR-030–FR-033).
- [ ] T018 [US3] Export the memory symbols; run `pytest tests/integration/test_review_us3.py` → green (SC-005).

**Checkpoint**: Loop-level review memory works, decoupled from Phase-1 tool-approval memory.

---

## Phase 6: User Story 4 - Ask the human review questions (Priority: P4)

**Goal**: A reviewer asks review questions via the Review Context; answers come from a host asker;
question events are emitted; missing/raising asker fails safe.

**Independent Test**: A reviewer asks a question and decides on the scripted answer; assert the answer
reached the reviewer and `review_question_asked`/`review_question_answered` were emitted; no asker ⇒
fail-safe.

- [ ] T019 [P] [US4] Write integration tests in `tests/integration/test_review_us4.py` (MUST FAIL first): a reviewer that asks one question gets the scripted answer and decides on it; `review_question_asked` then `review_question_answered` emitted in order; with no asker, `ask` raises `ReviewError` (no hang); an asker that raises ⇒ diagnostic + empty answer, review proceeds, no crash (US4 scenarios 1–4; SC-006, SC-009).
- [ ] T020 [US4] Complete `ReviewContext.ask` in `questions.py` (emit `review_question_asked`, delegate to the host `QuestionAsker` sync/async, emit `review_question_answered`, return answers; no asker ⇒ `ReviewError`; raising asker ⇒ diagnostic + `[]`) and wire the asker + event sink into `build_review_resolver`'s context (depends on T007, T011) (FR-041–FR-043).
- [ ] T021 [US4] Run `pytest tests/integration/test_review_us4.py` → green (SC-006, SC-009).

**Checkpoint**: Review questions work with events and fail safe.

---

## Phase 7: User Story 5 - Observe review events and keep edges honest (Priority: P5)

**Goal**: The review event stream is ordered and off by default; observation adds zero behavior change;
example + docs.

**Independent Test**: Observation on ⇒ ordered review events; observation off ⇒ identical decision/outcome
with no events.

- [ ] T022 [P] [US5] Write integration tests in `tests/integration/test_review_us5.py` (MUST FAIL first): with an `on_event` sink, a gated review (with a question and a decision) emits `review_requested → review_question_asked → review_question_answered → review_decided` in order; with no sink, the decision and loop outcome are identical and no event is recorded (US5 scenarios 1–4; SC-007, SC-008).
- [ ] T023 [US5] Confirm/adjust observation gating in `gate.py` and `questions.py`: events are emitted to `on_event` only when a sink is present; decisions and outcomes are identical when absent (depends on T011, T020) (FR-052, NFR-006).
- [ ] T024 [P] [US5] Create `examples/review_quickstart.py`: a runnable gated review over a scripted needs-review loop (approving reviewer + a review event printer), public-safe.
- [ ] T025 [P] [US5] Write `docs/human-review.md`: a public-safe guide (reviewer → gate → memory → questions → pause/resume) that points at the Phase-3 review hook and the no-Phase-1-approval boundary.
- [ ] T026 [US5] Run `pytest tests/integration/test_review_us5.py` → green (SC-007, SC-008).

**Checkpoint**: Review observation parity and the honest edges close the phase scope.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T027 [P] Write `tests/contract/test_review_boundary.py`: an import-boundary audit asserting `loopplane.review` imports only `loopplane.engineering` (+ stdlib) and references no `loopplane.approval` / `InteractionBroker` / `LoopController` / `run_loop`-bypass symbol; a `run_loop`-only drive assertion (SC-002); a determinism check (a gated review twice ⇒ identical decision/events/outcome, SC-007); and an unknown-future-Review-Event tolerance check (FR-051) (NFR-003).
- [ ] T028 Extend `tests/contract/test_public_safety.py` to include all committed Phase-6 files (`src/loopplane/review/`, `examples/review_quickstart.py`, `docs/human-review.md`, `specs/006-*`) so the scan finds zero private references (SC-010, NFR-004).
- [ ] T029 [P] Execute the [quickstart.md](./quickstart.md) scenarios end-to-end as a smoke check and reconcile any drift.
- [ ] T030 Final validation: full `pytest` green, `ruff format --check` + `ruff check` clean, `mypy` clean, `git diff --check` clean (board §10).
- [ ] T031 Update `docs/loopplane-agent-board.md`: advance unit 006 status (→ Verified) and its Next Action; set the active feature to 007.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational RA (Phase 2)** blocks all stories → **US1–US5** (US1 creates
  `gate.py`; US2 adds pause/resume to it; US3 adds memory + wiring; US4 completes the question flow; US5
  adds observation parity + example/docs) → **Polish**.
- US3, US4, US5 each extend the gate built in US1; they otherwise compose independently on the RA types.

### Parallel opportunities

- Foundational type modules T004–T007 are [P]; T003 (unit test) is [P] and written first.
- Each story's test task (T010, T013, T016, T019, T022) is [P] and written first (must fail).
- US5 example/docs (T024, T025) are [P]; Polish T027 ∥ T029.

---

## Implementation Strategy

### MVP first (US1)

Setup → Foundational RA (blocks all) → US1 (gate) → **STOP & VALIDATE**: the human gate loop drives a loop
through the Phase-3 hook (SC-001/002/003).

### Incremental delivery

RA → US1 (MVP) → US2 (pause/resume) → US3 (memory) → US4 (questions) → US5 (events/parity) → Polish. Each
story is an independently testable increment; commit after each green checkpoint and push (board §10–11).

---

## Notes

- [P] = different files. `gate.py` is shared by US1–US5; sequence those edits.
- Tests are written first per story and must FAIL before implementation (Constitution X).
- The layer composes only the Phase-3 public surface; no I/O, no network, deterministic, fail-safe.
