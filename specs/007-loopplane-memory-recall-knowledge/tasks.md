---
description: "Task list for Memory Recall & Knowledge Layer (007)"
---

# Tasks: Memory Recall & Knowledge Layer

**Input**: Design documents from `/specs/007-loopplane-memory-recall-knowledge/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL before
implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases KA–KF map below; the injection seam
(entry + budget + injection) is **Foundational** because every user story injects through it, so US1 (the
MVP) can recall *and* inject. US4 adds the cross-source de-duplication the composition story needs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/recall/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Phase-1 (`loopplane.memory`: `MemoryEntry`, `select_entries`;
`loopplane.artifacts`: `ArtifactMeta`) and Phase-3 (`loopplane.engineering`: `LoopState`, `RunReference`,
`ArtifactRef`, `InputSource`, `Prompt`, `StaticInput`) surfaces. It MUST NOT import `loopplane.host`,
`loopplane.model`, any Phase-1 runtime internal (`loopplane.controller`, `loopplane.gateway`,
`loopplane.context`, `loopplane.approval`, …), or a sibling layer (`scheduling`, `packs`, `review`). It
starts no Loop Run and mutates no store or `LoopState`. See
[contracts/injection-boundary.md](./contracts/injection-boundary.md). No Phase-1/2/3 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create the `loopplane.recall` package skeleton: `src/loopplane/recall/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [ ] T002 [P] Add recall test helpers in `tests/recall_helpers.py`: a `scripted_state(*, loop_id="L", run_refs=(), artifacts=())` builder over the public `LoopState`/`RunReference`/`ArtifactRef`; a `ScriptedArtifactReader` (a dict of `(session_id, reference) -> ArtifactMeta`, with a `raising` flag); a `memory_entries(*specs)` builder of `MemoryEntry`; and a `ScriptedKnowledgeIndex` (seeded entries + a `raising` flag).

---

## Phase 2: Foundational (Blocking Prerequisites — entry, budget, injection seam)

**Purpose**: The recall vocabulary and the injection seam every source plugs into. **⚠️ Blocks US1–US5.**

- [ ] T003 [P] Write unit tests in `tests/unit/test_recall_core.py` (MUST FAIL first): `RecalledEntry` shape; `apply_budget` keeps entries in order until `max_entries`/`max_chars` then truncates with an explicit `dropped` count, and treats `None` bounds as unbounded; `assemble_recall` concatenates sources in order and applies the budget, and a raising source contributes nothing while its label lands in `skipped`; `build_recall_input` prepends the preamble to a string base, returns the base unchanged on empty recall, and passes a `ContentBlock`-sequence base through unchanged; recall mutates neither the `LoopState` nor a bound store (FR-001, FR-052–FR-055, NFR-005, NFR-006).
- [ ] T004 [P] Implement `src/loopplane/recall/entry.py`: `RecalledEntry`, the `RecallSource` and `QueryFn` aliases, and `default_query` (deterministic, public-safe query from loop id + latest validation reason) (FR-001, FR-002).
- [ ] T005 [P] Implement `src/loopplane/recall/budget.py`: `RetrievalBudget`, `BudgetResult`, and `apply_budget` (order-stable truncation with an explicit dropped count) (FR-052, FR-053).
- [ ] T006 Implement `src/loopplane/recall/injection.py`: `RecallAssembly`, `assemble_recall` (source-order concat + `apply_budget`; a raising source is swallowed and recorded in `skipped`), and `build_recall_input` returning a Phase-3 `InputSource` (string-base preamble / empty passthrough / `ContentBlock`-base passthrough; never mutating base/state/store) (depends on T004, T005) (FR-050, FR-054, FR-055, NFR-005, NFR-006).
- [ ] T007 Populate `src/loopplane/recall/__init__.py` exports for the foundational types (`RecalledEntry`, `RecallSource`, `default_query`, `RetrievalBudget`, `apply_budget`, `RecallAssembly`, `assemble_recall`, `build_recall_input`).
- [ ] T008 Run `pytest tests/unit/test_recall_core.py --basetemp=".pytmp"` → green (gate for Foundational).

**Checkpoint**: The recall vocabulary, budget, and injection seam are ready.

---

## Phase 3: User Story 1 - Begin each run with the loop's prior conversation (Priority: P1) 🎯 MVP

**Goal**: A conversation-recall source reads the loop's prior-run trail and the injection seam prepends it
to the loop's first prompt, bounded and deterministic.

**Independent Test**: Build `build_recall_input(StaticInput("X"), [conversation_recall()], budget,
state=<2 run_refs>)`; assert `initial()` contains both runs most-recent-first; an empty-run state ⇒ `"X"`
unchanged; recalling twice is byte-identical.

- [ ] T009 [P] [US1] Write integration tests in `tests/integration/test_recall_us1.py` (MUST FAIL first): `conversation_recall()` over a state with two `run_refs` yields both entries most-recent-first (`origin="conversation"`, `identifier=session_id`); `build_recall_input` injects them ahead of a `StaticInput`; an empty-`run_refs` state ⇒ the base prompt unchanged (FR-055); deterministic (twice identical); loop-scoped (only this state's runs); the `LoopState` is unmutated (US1 scenarios 1–3; SC-001/002/003).
- [ ] T010 [US1] Implement `src/loopplane/recall/conversation.py`: `conversation_recall(*, limit=10)` reading `LoopState.run_refs`, most-recent-first, emitting public-safe `session_id`+`termination_reason` entries (FR-010–FR-013).
- [ ] T011 [US1] Export `conversation_recall` from `__init__.py`; run `pytest tests/integration/test_recall_us1.py --basetemp=".pytmp"` → green.

**Checkpoint**: MVP — the loop begins each run with its bounded, loop-scoped prior-run context.

---

## Phase 4: User Story 2 - Recall the artifacts the loop produced (Priority: P2)

**Goal**: An artifact-recall source surfaces newest-first, public-safe references + metadata of the loop's
artifacts.

**Independent Test**: `artifact_recall(reader)` over scripted artifact metadata yields newest-first
reference+metadata entries; a reference with no metadata is skipped; a raising reader yields empty.

- [ ] T012 [P] [US2] Write integration tests in `tests/integration/test_recall_us2.py` (MUST FAIL first): `artifact_recall(reader)` over a `ScriptedArtifactReader` orders entries newest-first by `ArtifactMeta.created_at`, each carrying only a reference + declared metadata (no content, no filesystem path); an `ArtifactRef` with `metadata(...) is None` is skipped; a raising reader contributes nothing (fail-safe); the store and state are unmutated (US2 scenarios 1–3; SC-007, NFR-005/006).
- [ ] T013 [US2] Implement `src/loopplane/recall/artifacts.py`: the `ArtifactReader` Protocol (`metadata(session_id, reference) -> ArtifactMeta | None`) and `artifact_recall(reader, *, limit=10)` (FR-020–FR-022).
- [ ] T014 [US2] Export `artifact_recall` and `ArtifactReader`; run `pytest tests/integration/test_recall_us2.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Recall durable memory entries via the existing selection (Priority: P2)

**Goal**: A memory-entry-recall source reuses the Phase-1 deterministic `select_entries` and adapts results
into recalled context.

**Independent Test**: `memory_entry_recall(entries)` returns exactly the `select_entries(entries, query,
limit)` result, adapted into entries, deterministically.

- [ ] T015 [P] [US3] Write integration tests in `tests/integration/test_recall_us3.py` (MUST FAIL first): `memory_entry_recall(entries)` over a scripted `MemoryEntry` list returns entries corresponding exactly to `select_entries(entries, default_query(state), limit)`, in the same order, adapted (`origin="memory"`, `identifier=name`); identical inputs ⇒ identical result; no ranking of its own; the entry list and state are unmutated (US3 scenarios 1–2; SC-002, NFR-006).
- [ ] T016 [US3] Implement `src/loopplane/recall/memory.py`: `memory_entry_recall(entries, *, query=default_query, limit=5)` calling the Phase-1 `select_entries` and adapting each result (FR-030–FR-032).
- [ ] T017 [US3] Export `memory_entry_recall`; run `pytest tests/integration/test_recall_us3.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US3 each work independently.

---

## Phase 6: User Story 4 - Compose sources and inject within a retrieval budget (Priority: P2)

**Goal**: The injection policy composes multiple sources, de-duplicates by precedence, applies the budget,
and surfaces explicit truncation — proven across conversation + artifact + memory.

**Independent Test**: Two+ sources with overlapping identifiers and a budget smaller than their union ⇒ the
injected block is de-duplicated by precedence, within budget, with the dropped count surfaced.

- [ ] T018 [P] [US4] Write integration tests in `tests/integration/test_recall_us4.py` (MUST FAIL first): `assemble_recall` over `[conversation_recall(), artifact_recall(reader), memory_entry_recall(entries)]` with overlapping identifiers de-duplicates by source precedence (first occurrence kept; `identifier=None` always kept) and orders by source-then-within-source; a tight `RetrievalBudget` truncates order-stably with `RecallAssembly.dropped` surfaced; `build_recall_input`'s injected prompt is within budget; an empty union ⇒ base unchanged (US4 scenarios 1–3; SC-004, SC-009, FR-050–FR-053).
- [ ] T019 [US4] Extend `src/loopplane/recall/injection.py`: add de-duplication by `RecalledEntry.identifier` in `assemble_recall` (highest-precedence occurrence kept; `None` never collapsed) ahead of `apply_budget`, keeping the dropped count surfaced on `RecallAssembly` (FR-051, FR-053) (depends on T010, T013, T016).
- [ ] T020 [US4] Run `pytest tests/integration/test_recall_us4.py --basetemp=".pytmp"` → green (composition + budget).

**Checkpoint**: Multi-source composition under an explicit budget is proven.

---

## Phase 7: User Story 5 - A named knowledge-index contract with a public-safe reference (Priority: P3)

**Goal**: A `KnowledgeIndex` contract plus an in-memory reference, with a knowledge-recall source whose
query derives deterministically from the Loop State.

**Independent Test**: `knowledge_recall(InMemoryKnowledgeIndex([...]))` returns the matched entries within
the bound; a raising index ⇒ empty recall + diagnostic.

- [ ] T021 [P] [US5] Write integration tests in `tests/integration/test_recall_us5.py` (MUST FAIL first): `InMemoryKnowledgeIndex.lookup` returns a deterministic, `limit`-bounded match over seeded entries; `knowledge_recall(index)` derives the query from the state via `default_query` and adapts results (`origin="knowledge"`, `identifier`); a raising index ⇒ empty recall recorded in `skipped` (fail-safe); an empty/missing index ⇒ empty (US5 scenarios 1–2; SC-005, FR-040–FR-043, NFR-005).
- [ ] T022 [US5] Implement `src/loopplane/recall/knowledge.py`: `KnowledgeEntry`, the `KnowledgeIndex` Protocol, `InMemoryKnowledgeIndex` (deterministic match, empty by default, no domain data), and `knowledge_recall(index, *, query=default_query, limit=5)` (FR-040–FR-043).
- [ ] T023 [US5] Export the knowledge types; run `pytest tests/integration/test_recall_us5.py --basetemp=".pytmp"` → green.

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Write contract tests in `tests/contract/test_recall_boundary.py`: an import-boundary audit (every `src/loopplane/recall/*.py` imports only `loopplane.engineering` / `loopplane.memory` / `loopplane.artifacts` / `loopplane.recall` + stdlib, and references no `loopplane.host` / `loopplane.model` / `loopplane.controller` / `loopplane.gateway` / `loopplane.approval` / `scheduling` / `packs` / `review` token); the layer drives no run (no `run_loop` import/call); recall leaves a bound store and the `LoopState` unmutated; determinism (assemble twice ⇒ identical) (FR-060, FR-061, NFR-003, NFR-006, SC-002/003/008).
- [ ] T025 [P] Extend `tests/contract/test_public_safety.py` with `PHASE7_TARGETS` (`src/loopplane/recall`, `examples/recall_quickstart.py`, `docs/memory-recall.md`, `specs/007-loopplane-memory-recall-knowledge`) and a `test_phase7_recall_files_are_public_safe` scan.
- [ ] T026 [P] Create `examples/recall_quickstart.py`: a public-safe, credential-free runnable recall over a scripted `LoopState` + in-memory reader/index/entries, printing the `RecallAssembly` (preamble, kept entries, dropped count) and the injected prompt (per [quickstart.md](./quickstart.md)).
- [ ] T027 [P] Create `docs/memory-recall.md`: a public-safe guide — sources → budget → injection → `InputSource`, the knowledge index, and the reserved extension points (FR-090–FR-095).
- [ ] T028 Finalize `src/loopplane/recall/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [ ] T029 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/recall_quickstart.py`; confirm the public-safety scan is green (SC-006); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (the injection seam + vocabulary).
- **US1 (Phase 3)**: depends on Foundational. MVP.
- **US2 (Phase 4)**, **US3 (Phase 5)**: depend on Foundational; independent of each other and of US1.
- **US4 (Phase 6)**: depends on Foundational + the three sources (T010, T013, T016) for its composition test.
- **US5 (Phase 7)**: depends on Foundational; independent of US1–US4.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- Aliases/value types before sources; sources before the cross-source de-dup (US4).
- Each phase ends with its pytest gate green; commit per stable phase, push after each safe commit.

## Parallel Opportunities

- T002 (helpers) runs alongside the Phase-2 test authoring.
- Within Foundational: T004 (entry) and T005 (budget) are `[P]`; T006 (injection) depends on both.
- Across stories: US1/US2/US3/US5 source modules are independent files — their `[P]` test-authoring and
  implementation can proceed in parallel once Foundational is green (US4 waits on the three sources).
- Polish: T024–T027 are independent files (`[P]`); T028/T029 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (the injection seam) → Phase 3 US1.
2. **STOP and VALIDATE**: a loop begins each run with bounded, deterministic, loop-scoped conversation
   recall injected through a Phase-3 `InputSource`.

### Incremental Delivery

Foundational → US1 (MVP) → US2 → US3 → US4 (composition) → US5 (knowledge) → Polish. Each phase is an
independently testable, revertible increment; no Phase-1/2/3 source is modified.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- Every source is deterministic, fail-safe, and non-mutating; tests assert no crash, no fabricated content,
  and an unchanged store + `LoopState`.
- Commit after each stable phase (Section: board §11); push after each safe commit.
- Avoid: importing `loopplane.host`/`loopplane.model`/runtime internals; mutating a store or `LoopState`;
  surfacing artifact content or a filesystem path; any non-deterministic ordering.
