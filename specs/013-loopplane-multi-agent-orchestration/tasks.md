---
description: "Task list for Multi-Agent Orchestration (013)"
---

# Tasks: Multi-Agent Orchestration

**Input**: Design documents from `/specs/013-loopplane-multi-agent-orchestration/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL
before implementation), then implements until green. All tests run **in-process** over scripted loop
definitions — no real model, no network.

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases IA–IF map below; the registry
+ the coordinator result types are Foundational. US1 (register + run a subagent) is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/orchestration/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Phase-3 loop surface (`loopplane.engineering`: `run_loop`,
`LoopDefinition`, `LoopOutcome`, `LoopEvent`, `LoopState`, `RunReference`, `ArtifactRef`) and stdlib. It
MUST NOT import a Phase-1/2 internal (`loopplane.host` / `controller` / `gateway` / `events`), or a
sibling layer; MUST **execute no tool** (Constitution V) and **re-emit no live bus** (Constitution VI —
it reads each captured `LoopOutcome.events`, passing no live sink); and MUST keep **aggregated views
metadata-only** (subagent / type / sequence / references). See
[contracts/orchestration-boundary.md](./contracts/orchestration-boundary.md). No Phase-1/2/3 source is
modified; no dependency is added.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `loopplane.orchestration` package skeleton: `src/loopplane/orchestration/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [X] T002 [P] Add orchestration test helpers in `tests/orchestration_helpers.py`: a `scripted_subagent_definition(name, *, text="done", fail=False)` building a public-safe single-iteration `LoopDefinition` over a scripted model (reusing the unit-003 `loop_helpers` pattern: `ManualTrigger` / `StaticInput` / `HostRuntimeProfile(selector)` / `ValidationPolicy(ScriptedValidator("pass"))` / `stop_on_pass()` / `ObservationPolicy(emit_loop_events=True)`). Verified runnable via `run_loop` → `loop_completed`, 5 events, 1 run_ref. `fail=True` makes the host selector raise (for the US5 fail-safe test). (Real scripted loops produce 0 artifacts, so US4 pairs an empty-real case with a constructed-artifact case.)

---

## Phase 2: Foundational (Blocking Prerequisites — registry + result types)

**Purpose**: The agent registry and the coordinator's child-reference / result value types every story
composes. **⚠️ Blocks US1–US5.**

- [X] T003 [P] Write unit tests in `tests/unit/test_orchestration_core.py`: `AgentRegistry.register` registers a named subagent and `names()` is registration-ordered; a duplicate name → `DuplicateSubagentError`; `get(unknown)` → `None`; `__contains__`; the `ChildRunReference` / `SubagentResult` value types carry only their declared metadata fields. (The `AggregatedEvent` / `AggregatedArtifact` metadata-only assertions land with US3/US4 + the boundary test, since those types are created then.)
- [X] T004 [P] Implement `src/loopplane/orchestration/registry.py`: `Subagent` (name + `LoopDefinition`), `AgentRegistry` (`register` / `get` / `names` / `__contains__`), and `DuplicateSubagentError` (FR-001-FR-003; [data-model.md](./data-model.md)).
- [X] T005 Implement `src/loopplane/orchestration/coordinator.py` value types: frozen `ChildRunReference` (subagent / loop_id / run_refs) and `SubagentResult` (subagent / reference / outcome / failure), plus a `Coordinator(registry)` skeleton (FR-002, FR-010).
- [X] T006 Finalize `src/loopplane/orchestration/__init__.py` exports (`AgentRegistry`, `Subagent`, `DuplicateSubagentError`, `Coordinator`, `ChildRunReference`, `SubagentResult`).
- [X] T007 Run `pytest tests/unit/test_orchestration_core.py --basetemp=".pytmp"` → green (gate for Foundational; 3 passed).

**Checkpoint**: The registry and the coordinator result types are ready.

---

## Phase 3: User Story 1 - Register and run a subagent (Priority: P1) 🎯 MVP

**Goal**: register a named subagent and run it; the coordinator drives one loop run via `run_loop` and
returns a child run reference + outcome.

**Independent Test**: register a subagent, `await coord.run(["a"])` → a `SubagentResult` with a
`ChildRunReference` + `LoopOutcome`; `run(["ghost"])` → a `failure="not found"` result.

- [X] T008 [P] [US1] Write integration tests in `tests/integration/test_orchestration_us1.py` (`pytest.mark.anyio`): register a scripted subagent; `await Coordinator(registry).run(["a"])` returns one `SubagentResult` with a `ChildRunReference(subagent="a", loop_id, run_refs)` and a `loop_completed` `LoopOutcome`; `run(["ghost"])` → a `SubagentResult(failure="not found", outcome=None, reference=None)`; no crash (US1 scenarios 1–3; SC-001, FR-002/FR-003).
- [X] T009 [US1] Implement `Coordinator.run(selection)` in `src/loopplane/orchestration/coordinator.py`: dedupe the selection; run the known subagents in **registration order** via `await run_loop(subagent.definition)`, building a `SubagentResult` with a `ChildRunReference` (loop_id + `state.run_refs`); append unknown names as not-found results (FR-002, FR-003, FR-010, FR-011).
- [X] T010 [US1] Run `pytest tests/integration/test_orchestration_us1.py --basetemp=".pytmp"` → green (2 passed; full suite 553).

**Checkpoint**: MVP — a registered subagent runs and returns a child reference + outcome.

---

## Phase 4: User Story 2 - Coordinate a set of subagents (Priority: P2)

**Goal**: the coordinator runs a selected set in deterministic (registration) order, each once.

**Independent Test**: register several subagents, `await coord.run([...])` → one result per selection in
registration order, each run once; repeat → identical.

- [X] T011 [P] [US2] Write integration tests in `tests/integration/test_orchestration_us2.py`: register several subagents; `await coord.run(selection)` returns one `SubagentResult` per selected name in **registration order** (independent of selection order), each run once (a duplicate is de-duped); the same selection run twice yields identical results; an unknown name yields a not-found result while the known subagents still run (US2 scenarios 1–3; SC-002/006, FR-010, FR-011).
- [X] T012 [US2] Confirmed: `Coordinator.run` (US1) already orders results by registration order independent of the selection argument order and de-dupes so each subagent runs exactly once — the US2 tests verify it; no code change needed (FR-011, NFR-004).
- [X] T013 [US2] Run `pytest tests/integration/test_orchestration_us2.py --basetemp=".pytmp"` → green (3 passed; full suite 556).

**Checkpoint**: US1 + US2 — run a single subagent and coordinate a set.

---

## Phase 5: User Story 3 - Aggregate child events (Priority: P3)

**Goal**: `aggregate_events` groups each subagent's loop events by subagent (registration order),
ordered by sequence — metadata-only.

**Independent Test**: coordinate subagents that emit scripted loop events; assert the aggregated view is
grouped by subagent and ordered by sequence, with metadata only.

- [X] T014 [P] [US3] Write integration tests in `tests/integration/test_orchestration_us3.py`: `aggregate_events(results)` returns `AggregatedEvent(subagent, type, sequence)` records grouped by subagent (registration order, contiguous groups) and ordered by `sequence` within; identical on repeat; **no** payload/content field (`vars(e) == {subagent, type, sequence}`); a result with no outcome contributes nothing (US3 scenarios 1–3; SC-002/003, FR-020, FR-021).
- [X] T015 [US3] Implement `src/loopplane/orchestration/aggregate.py`: the frozen `AggregatedEvent` and `aggregate_events(results)` projecting each `LoopOutcome.events` to `(subagent, type, sequence)` in result order (events already sequence-ordered) (FR-020, FR-021).
- [X] T016 [US3] Export the aggregation symbols; run `pytest tests/integration/test_orchestration_us3.py --basetemp=".pytmp"` → green (3 passed; full suite 559).

**Checkpoint**: US1–US3 — coordinate + aggregated event view.

---

## Phase 6: User Story 4 - Aggregate child artifacts (Priority: P4)

**Goal**: `aggregate_artifacts` groups each subagent's artifact references by subagent — metadata-only.

**Independent Test**: coordinate subagents that produce artifact references; assert the aggregated view
groups the references by subagent, with reference metadata only.

- [X] T017 [P] [US4] Write integration tests in `tests/integration/test_orchestration_us4.py`: `aggregate_artifacts(results)` returns `AggregatedArtifact(subagent, session_id, reference)` records grouped by subagent (registration order); a subagent with no artifacts contributes nothing; a real scripted run (no artifacts) → empty; **no** artifact content (`vars(x) == {subagent, session_id, reference}`). Populated case over constructed `SubagentResult`s, since scripted text loops produce no artifacts (US4 scenarios 1–3; SC-003, FR-030, FR-031).
- [X] T018 [US4] Implement in `src/loopplane/orchestration/aggregate.py`: the frozen `AggregatedArtifact` and `aggregate_artifacts(results)` projecting each `LoopOutcome.state.artifacts` to `(subagent, session_id, reference)` (FR-030, FR-031).
- [X] T019 [US4] Export the symbols; run `pytest tests/integration/test_orchestration_us4.py --basetemp=".pytmp"` → green (3 passed; full suite 562).

**Checkpoint**: US1–US4 — coordinate + aggregated events + artifacts.

---

## Phase 7: User Story 5 - Delegate and fail safe (Priority: P5)

**Goal**: a delegation policy selects subagents; a failing subagent / raising policy / empty selection
is contained.

**Independent Test**: a delegation policy where one subagent's loop fails and one name is unknown; the
coordinator completes, the failure is captured, and the healthy subagents still produce results.

- [X] T020 [P] [US5] Write integration tests in `tests/integration/test_orchestration_us5.py`: `await coord.delegate(policy)` runs exactly the policy-selected subagents in registration order; a subagent whose loop run **fails** (`run_loop` raises) → a `SubagentResult(failure="failed")` while the others still complete; a **raising** delegation policy → an empty result; an **empty** selection → an empty result tuple (US5 scenarios 1–3; SC-004, FR-040, FR-041).
- [X] T021 [US5] Implement `DelegationPolicy` + `Coordinator.delegate(policy)` and harden `Coordinator._run_subagent` in `coordinator.py`: wrap `run_loop` in `try/except Exception` capturing a failure into `SubagentResult(failure="failed")` (a fixed public-safe marker, never raw exception detail); a raising policy → an empty selection (FR-040, FR-041, NFR-005/006).
- [X] T022 [US5] Run `pytest tests/integration/test_orchestration_us5.py --basetemp=".pytmp"` → green (4 passed; full suite 566).

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Write contract tests in `tests/contract/test_orchestration_boundary.py`: an import-boundary audit (every `src/loopplane/orchestration/*.py` imports only `loopplane.engineering` / `loopplane.orchestration` + stdlib); a text scan finding no `loopplane.host` / `loopplane.gateway` / `loopplane.controller` / `loopplane.events` / `RuntimeController` / `serialize_event` / sibling-package token; a metadata-only aggregated-record assertion; an aggregation determinism check (NFR-001/002/003, SC-002/003/005).
- [ ] T024 [P] Extend `tests/contract/test_public_safety.py` with `PHASE13_TARGETS` (`src/loopplane/orchestration`, `examples/orchestration_quickstart.py`, `docs/multi-agent-orchestration.md`, `specs/013-loopplane-multi-agent-orchestration`) and a `test_phase13_orchestration_files_are_public_safe` scan.
- [ ] T025 [P] Create `examples/orchestration_quickstart.py`: a public-safe, in-process runnable that registers scripted subagents, coordinates them, and prints the aggregated event / artifact views (metadata only) (per [quickstart.md](./quickstart.md)).
- [ ] T026 [P] Create `docs/multi-agent-orchestration.md`: a public-safe guide — the registry, the coordinator, delegation, the aggregated views, and the reserved extension points (distributed / dynamic / inter-subagent).
- [ ] T027 Finalize `src/loopplane/orchestration/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [ ] T028 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/orchestration_quickstart.py`; confirm the public-safety scan is green (SC-003/005); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (registry + result types).
- **US1 (Phase 3)**: depends on Foundational. MVP (register + run a subagent).
- **US2 (Phase 4)**: depends on US1 (`Coordinator.run`); confirms the set / registration-order behavior.
- **US3 (Phase 5)**, **US4 (Phase 6)**: depend on US1/US2 (need results to aggregate); `aggregate.py` is independent of `coordinator.py` at the file level.
- **US5 (Phase 7)**: depends on US1 (`run`); adds the delegation policy + fail-safe capture.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- The registry/result types before the run/aggregation; each phase ends on its pytest gate; commit per
  stable phase.

## Parallel Opportunities

- T002 (helpers) runs alongside the Phase-2 test authoring.
- Foundational: `registry.py` (T004) is independent of `coordinator.py` (T005) at the file level (`[P]`).
- `aggregate.py` (US3/US4) is an independent file from `coordinator.py` — its `[P]` test authoring can
  proceed once results exist. US2/US5 serialize on `coordinator.py`.
- Polish: T023–T026 are independent files (`[P]`); T027/T028 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (registry + result types) → Phase 3 US1 (run a subagent).
2. **STOP and VALIDATE**: a registered subagent runs through `run_loop` and returns a deterministic
   child reference + outcome — in-process, offline.

### Incremental Delivery

Foundational → US1 (MVP) → US2 (coordinate a set) → US3 (aggregate events) → US4 (aggregate artifacts)
→ US5 (delegate + fail-safe) → Polish. Each phase is an independently testable, revertible increment;
no Phase-1/2/3 source is modified; no dependency is added.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- Every aggregated view is metadata-only (subagent / type / sequence / references); ordering is by
  registration order then event sequence; the layer executes no tool and re-emits no live bus.
- All tests run in-process over scripted loop definitions (NFR-006/NFR-007).
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: importing a Phase-1/2 internal / the host / the gateway / a sibling layer; executing a tool or
  re-emitting the live bus; leaking a `LoopEvent.payload`, content, internal name, path, or secret.
