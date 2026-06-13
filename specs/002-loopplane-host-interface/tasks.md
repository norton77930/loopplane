# Tasks: Host Integration Interface

**Input**: Design documents from `/specs/002-loopplane-host-interface/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories).
`research.md`, `data-model.md`, and `contracts/` were intentionally **not** generated for this feature —
the configuration model, API shape, and event model are folded into [plan.md](./plan.md).

**Tests**: Test tasks are REQUIRED. End-to-end smoke tests are a first-class deliverable of this
feature (spec User Story 4, FR-040–FR-043) and Constitution Principle X (Testable Evolution) mandates
tests per phase.

**Organization**: Tasks are grouped by user story (spec priorities P1–P5) so each story can be
implemented and tested independently. This phase is **strictly additive** over the merged Phase-1
runtime (`001-loopplane-runtime-foundation`); no Phase-1 source file is modified.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 (user-story phases only; Setup/Foundational/Polish carry no story label)
- Exact repo-relative file paths are included in every task

## Path Conventions

Single library project (src-layout), matching Phase 1: source under `src/loopplane/`, tests under
`tests/`, examples under `examples/`, docs under `docs/`. The host layer is one new sub-package:
`src/loopplane/host/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new package and shared test fixtures; nothing story-specific yet.

- [x] T001 Create the `loopplane.host` package scaffold: `src/loopplane/host/__init__.py` (module docstring + empty `__all__`) and empty module stubs `src/loopplane/host/config.py`, `src/loopplane/host/assembly.py`, `src/loopplane/host/host.py` (docstrings only)
- [x] T002 [P] Add host test scenario helpers by extending `tests/integration/conftest.py`: reuse the existing scripted-model/echo fixtures to provide a text-only scenario, a tool-call scenario, and a temporary `storage_root` helper for the host suites
- [x] T003 [P] Add a Phase-1 public-surface import guard in `tests/contract/test_host_imports.py` asserting the host layer's Phase-1 dependencies import (controller, gateway, model, approval, checkpoint, artifacts, memory, skills, events, observability), and that `loopplane.host` imports no web/transport/UI framework — NFR-001, FR-008

**Checkpoint**: Package importable; shared fixtures available.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types every user story depends on. **No user-story work may begin until this phase is complete.**

- [x] T004 [P] Define the configuration types as frozen dataclasses in `src/loopplane/host/config.py`: `RuntimeConfig` (model, tools, tool_adapters, approval, storage, memory, skills, observability) plus `ToolSpec`, `ApprovalPolicy`, `StorageConfig`, `MemoryConfig`, `SkillsConfig` — **shape only**, validation and `from_mapping` deferred to US2 (FR-010)
- [x] T005 [P] Define `RunOutcome` (session_id, termination_reason, history) and the public-safe `ConfigError` exception in `src/loopplane/host/host.py` (skeleton)

**Checkpoint**: Shared types compile and are importable — user stories can begin.

---

## Phase 3: User Story 1 - Embed and start a run through one configured entry point (Priority: P1) 🎯 MVP

**Goal**: A host builds a minimal `RuntimeConfig` (scripted model + one echo tool), hands it to
`LoopPlaneHost`, submits a prompt, and gets an ordered event stream plus a `RunOutcome` — with zero
manual wiring of Phase-1 collaborators.

**Independent Test**: Drive a minimal config through `LoopPlaneHost.run` against the scripted model and
assert the ordered event sequence and the returned `RunOutcome`, for both a text-only and a tool-call
scenario.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [x] T006 [P] [US1] Integration test in `tests/integration/test_host_smoke.py`: minimal config (scripted model + echo tool) → `LoopPlaneHost.run` → ordered events + single terminal event + `RunOutcome`, covering the text-only and tool-call scenarios, plus one host driving two sequential runs with no state leak (SC-001, FR-006)

### Implementation for User Story 1

- [x] T007 [US1] Implement the Reference Runner core `assemble(config)` in `src/loopplane/host/assembly.py`: resolve the model, build a `ToolGateway`, `register` each `ToolSpec`, `register_adapter` each adapter, and construct a `RuntimeController` (minimal path; optional backends wired in US2) (FR-020, FR-022, FR-024)
- [x] T008 [US1] Implement `LoopPlaneHost.__init__` (calls `assemble`), `LoopPlaneHost.run(input, on_event)` → `RunOutcome` (create_session → drive → history_snapshot), and the `build_host(config)` factory alias in `src/loopplane/host/host.py` (FR-001, FR-003)
- [x] T009 [US1] Export the public surface from `src/loopplane/host/__init__.py` (`RuntimeConfig`, `ToolSpec`, `ApprovalPolicy`, `StorageConfig`, `MemoryConfig`, `SkillsConfig`, `LoopPlaneHost`, `build_host`, `RunOutcome`, `ConfigError`)

**Checkpoint**: US1 fully functional — the MVP runs end-to-end through the interface.

---

## Phase 4: User Story 2 - Configure the runtime's collaborators through a minimal contract (Priority: P2)

**Goal**: One declarative `RuntimeConfig` selects model, tools, memory/checkpoint/artifact backends, and
approval behavior; omitted optionals stay off (zero behavior change); invalid config is rejected before
any run.

**Independent Test**: Assemble runtimes from a range of configs (minimal, durable, approval-restricted,
invalid) and assert what gets wired, gating-equality, and fail-fast rejection.

### Tests for User Story 2 ⚠️ (write first, ensure they FAIL)

- [x] T010 [P] [US2] Contract test in `tests/contract/test_host_config.py`: `RuntimeConfig.from_mapping` round-trips a plain mapping to an equivalent config (FR-011); fail-fast `ConfigError` for missing model, duplicate tool names, and an unavailable optional capability (FR-005, SC-005); a checkpoint-only and an artifact-only config each assemble and wire consistently without manual handoff (edge case); and `RuntimeConfig` declares no credential/secret-bearing field (FR-013)
- [x] T011 [P] [US2] Integration test in `tests/integration/test_host_gating.py`: with all optional subsystems omitted, the event sequence is identical to a bare `RuntimeController` run (SC-003, FR-012, FR-043)

### Implementation for User Story 2

- [x] T012 [US2] Implement configuration validation in `src/loopplane/host/config.py`: model required, tool names unique across `tools`/`tool_adapters`, selected optional capabilities importable, approval names reference known tools — raising public-safe `ConfigError` (FR-005, FR-015)
- [x] T013 [US2] Implement `RuntimeConfig.from_mapping(data)` in `src/loopplane/host/config.py` (object-typed collaborators pass through; scalar/structured selections from the mapping) (FR-011)
- [x] T014 [US2] Extend `assemble()` in `src/loopplane/host/assembly.py` to wire optional backends from config: `StorageConfig` → `CheckpointStore` + `ArtifactStore` + `make_artifact_handoff`; `MemoryConfig` → `MemoryStore`; `SkillsConfig` → `load_skills` + `SkillToolAdapter`; `ApprovalPolicy` → `HumanApproval` (+ `skill_profiles` when skills present); record the observability flag for sink-wrap time (FR-002, FR-012, FR-014)
- [x] T015 [US2] Run fail-fast validation inside `LoopPlaneHost.__init__` before any session is created in `src/loopplane/host/host.py` (FR-005)

**Checkpoint**: US1 + US2 both work; the configuration contract is complete and validated.

---

## Phase 5: User Story 3 - Drive and observe a run as a host (Priority: P3)

**Goal**: The host consumes the ordered event stream through its own sink and drives the interactive
round-trip (submit, cancel, approval/question answers) without touching loop internals.

**Independent Test**: Attach a host sink and approval handler, drive a scripted run that asks for
approval and is then cancelled, and assert event order, the approval round-trip, the cancelled terminal
event, and consumer-failure isolation.

### Tests for User Story 3 ⚠️ (write first, ensure they FAIL)

- [x] T016 [P] [US3] Integration test in `tests/integration/test_host_session.py`: ordered event delivery + unknown-event-type tolerance (FR-004); cancel → `cancelled` terminal without raising, including cancellation issued before the first model response (edge case); an `ask`-policy approval round-trips to a host handler and resolves exactly one pending request (FR-014); a sink that raises is isolated as a diagnostic with ordering intact (FR-007)

### Implementation for User Story 3

- [x] T017 [US3] Implement the guarded sink wrapper plus the optional `observability.maybe_attach(sink)` wrap (only when `config.observability`) in `src/loopplane/host/host.py` (FR-004, FR-007, FR-012)
- [x] T018 [US3] Implement `LoopPlaneHost.session(on_event, on_approval)` as an async round-trip handle over the Phase-1 `Dispatcher` channels — `submit`, `cancel`, `answer_approval`, `answer_question` — in `src/loopplane/host/host.py` (US3; reuses FR-012/FR-013 machinery)
- [x] T019 [US3] Route the `ApprovalPolicy` `ask` set to the host-supplied approval handler at run/session time (deny when no handler is supplied) in `src/loopplane/host/host.py` (FR-014)

**Checkpoint**: US1–US3 independently functional; the interactive round-trip works.

---

## Phase 6: User Story 4 - Run the reference runner end-to-end as a deterministic smoke test (Priority: P4)

**Goal**: The reference runner (and the minimal example runner over it) drives the full path
deterministically, with verifiable checkpoint and artifact behavior.

**Independent Test**: Drive fixed scripted scenarios and assert the deterministic event/outcome
transcript, the recorded checkpoint, and the retrievable artifact; run the example runner and confirm a
deterministic transcript.

### Tests for User Story 4 ⚠️ (write first, ensure they FAIL)

- [x] T020 [P] [US4] Integration test in `tests/integration/test_host_durability.py`: determinism — the same scenario run twice yields identical event sequences and identical `RunOutcome` (SC-002); with a `StorageConfig`, durable checkpoint records are inspectable and an oversized test-tool result is offloaded and retrievable by reference (SC-004, FR-042); and the example runner reports a clear, public-safe message (not a traceback) on an unknown scenario argument (FR-033 edge case)

### Implementation for User Story 4

- [x] T021 [US4] Add an oversized-output test tool to `tests/integration/conftest.py` and assert in test that the facade and the example both reach execution through the single `assemble()` path (FR-024)
- [x] T022 [US4] Implement the minimal example / smoke runner `examples/host_quickstart.py`: builds a `RuntimeConfig`, constructs `LoopPlaneHost`, runs a selectable scenario (`text` | `tool` | `durable`), prints the ordered event stream and `RunOutcome`; credential-free and network-free; clear public-safe message on an unknown argument; explicitly **not** a product CLI (FR-030–FR-033, FR-051)

**Checkpoint**: US1–US4 functional; the deterministic end-to-end smoke path is proven.

---

## Phase 7: User Story 5 - Embed LoopPlane from public-safe documentation and examples (Priority: P5)

**Goal**: A new developer embeds the runtime from a public-safe guide and a runnable example, with the
scripted model and no credentials.

**Independent Test**: Run the documented example as-is and confirm it reproduces the documented output;
scan the example and docs for private references.

### Tests for User Story 5 ⚠️

- [x] T023 [P] [US5] Extend the public-safety scan in `tests/contract/test_public_safety.py` to cover `src/loopplane/host/`, `examples/host_quickstart.py`, and `docs/embedding-host.md` — zero private references and zero raw private-reference excerpts (SC-006, FR-052)

### Implementation for User Story 5

- [x] T024 [US5] Write `docs/embedding-host.md`: config → `LoopPlaneHost` → event consumption → durable + approval variants; state that Phase 2 is an integration layer over Phase 1 and point to the Phase-1 boundaries (`docs/quickstart.md`, the spec boundary table) without duplicating internals (FR-050, FR-053)
- [x] T025 [US5] Verify `examples/host_quickstart.py` reproduces the output documented in `docs/embedding-host.md` (cross-link the doc and the example) (SC-007)

**Checkpoint**: All five user stories independently functional and documented.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Traceability, quality gates, and the final public-safety / constitution check.

- [x] T026 [P] Append a Success-Criteria traceability map (SC-001–SC-008 → concrete test files) to the end of this `tasks.md` and to `docs/embedding-host.md`
- [x] T027 [P] Run ruff + mypy + pytest across `src/loopplane/host/`, `examples/host_quickstart.py`, and the new test suites; ensure green on Windows and Linux
- [x] T028 Final public-safety scan of all committed Phase-2 files (SC-006) and a constitution re-check confirming no Phase-1 source was modified and all tools still execute only through the Tool Gateway (SC-008, Constitution IV–VII)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **User Stories (Phase 3–7)**: all depend on Foundational. Recommended order is priority order
  (P1 → P5); they share `assembly.py`/`host.py`, so they integrate sequentially but each remains
  independently testable.
- **Polish (Phase 8)**: depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: needs Foundational only — the MVP.
- **US2 (P2)**: extends `config.py` + `assembly.py` from US1; independently testable (config contract + gating).
- **US3 (P3)**: extends `host.py` from US1; independently testable (events + round-trip).
- **US4 (P4)**: exercises the US1 `assemble()` path + US2 storage wiring; independently testable (determinism + durability + example runner).
- **US5 (P5)**: documents the surface built by US1–US4; independently testable (example reproduces docs; scan clean).

### Within Each User Story

- The test task is written first and must FAIL before implementation.
- In US1: types (Foundational) → `assemble` (T007) → facade (T008) → exports (T009).
- Same-file tasks run sequentially (e.g. US2 `config.py` T012 → T013; US3 `host.py` T017 → T018 → T019).

---

## Parallel Opportunities

- Setup: T002 and T003 run in parallel (after T001).
- Foundational: T004 and T005 run in parallel (different files).
- Each user story's test task is `[P]` (distinct file) and is authored before that story's implementation.
- Across stories: once Foundational is done, US2's tests (T010, T011) and US3's test (T016) can be drafted in parallel since they live in distinct files, even though implementation lands in priority order.

## Parallel Example: User Story 2

```text
# After Foundational, draft US2 tests together (distinct files):
Task: "Contract test for config validation + from_mapping in tests/contract/test_host_config.py"  (T010)
Task: "Gating-equality test in tests/integration/test_host_gating.py"                              (T011)
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP and validate**: a host can embed
   and run end-to-end through `LoopPlaneHost` with a minimal config. This alone is a demonstrable MVP.

### Incremental Delivery

US1 (embed & run) → US2 (full config contract + gating) → US3 (events + round-trip) → US4 (determinism +
durability + example runner) → US5 (docs). Each story adds value without breaking the previous ones; the
gating-equality test (T011) guards zero behavior change throughout.

### Notes

- `[P]` = different files, no dependency on an incomplete task.
- `[Story]` labels map tasks to spec user stories for traceability.
- Verify each story's test fails before implementing it.
- Commit after each task or logical group; each phase (and each story) is independently revertible —
  the whole `loopplane.host` package is additive over Phase 1 (plan.md → Risk & Rollback).
- Do **not** modify any Phase-1 source file; compose Phase 1 only through its public surface.

---

## Success-Criteria Traceability

| SC | Verified by |
|---|---|
| SC-001 (one-entry-point assembled run, no manual wiring) | T006 (`test_host_smoke.py`) |
| SC-002 (repeat-run determinism) | T020 (`test_host_durability.py`) |
| SC-003 (gating equality vs bare controller) | T011 (`test_host_gating.py`) |
| SC-004 (full smoke path + checkpoint + artifact via interface) | T006, T020 |
| SC-005 (invalid config fails fast) | T010 (`test_host_config.py`) |
| SC-006 (public-safety scan clean) | T023 (`test_public_safety.py`), T028 |
| SC-007 (embed from example + docs) | T025 |
| SC-008 (no Phase-1 internal re-implemented) | T003 (import guard), T028 (constitution re-check) |
