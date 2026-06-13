---
description: "Task list for Observability & Debug-Console Layer (010)"
---

# Tasks: Observability & Debug-Console Layer

**Input**: Design documents from `/specs/010-loopplane-observability-debug-console/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL before
implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases IA–IF map below; the shared
`SequencedEvent` protocol is Foundational. US1 is loop diagnostics (the MVP).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/inspect/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Phase-3 Loop Event / Loop State (`loopplane.engineering`: `LoopEvent`,
`LoopEventType`, `reconstruct_state`, `LoopState`, `LoopOutcome`) and Phase-1 Runtime Event
(`loopplane.events`: `RuntimeEvent` + typed events, `TerminationReason`) surfaces. It MUST NOT import a
runtime control internal (`loopplane.controller`, `loopplane.host`, `loopplane.gateway`, `loopplane.context`)
or a sibling layer, MUST NOT drive a run or re-emit the live buses, and MUST read **only metadata** (`type`,
`sequence`, ids, terminal reasons) — never a content payload (Constitution VI). See
[contracts/inspect-boundary.md](./contracts/inspect-boundary.md). No Phase-1/2/3 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `loopplane.inspect` package skeleton: `src/loopplane/inspect/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [X] T002 [P] Add inspect test helpers in `tests/inspect_helpers.py`: a `loop_event(type, *, sequence, loop_id="L", loop_definition_id="defL", iteration_index=None, session_id=None, payload=None)` builder over the public `LoopEvent`; `runtime_event` builders over the public typed Runtime Events (e.g. `ToolCallStartedEvent`, `TurnCompletedEvent`, `DiagnosticEvent`, `RunTerminatedEvent`) with their minimal fields; and a `RecordingSink` that records each replayed event.

---

## Phase 2: Foundational (Blocking Prerequisites — the sequenced-event protocol)

**Purpose**: The shared structural protocol and count helper the timeline / replay / diagnostics use.
**⚠️ Blocks US1–US5.**

- [X] T003 [P] Write unit tests in `tests/unit/test_inspect_core.py` (MUST FAIL first): a `LoopEvent` and a `RuntimeEvent` both satisfy the `SequencedEvent` protocol (have `type` / `sequence`); `count_by_type(events, *types)` returns the count of events whose `type` is in the given set, tolerating an unknown type (FR-003, FR-062).
- [X] T004 [P] Implement `src/loopplane/inspect/base.py`: the `SequencedEvent` Protocol (`type: str`, `sequence: int`) and a `count_by_type(events, *types)` helper (FR-003).
- [X] T005 Populate `src/loopplane/inspect/__init__.py` exports for `SequencedEvent`.
- [X] T006 Run `pytest tests/unit/test_inspect_core.py --basetemp=".pytmp"` → green (gate for Foundational).

**Checkpoint**: The shared sequenced-event protocol and count helper are ready.

---

## Phase 3: User Story 1 - See what happened in a loop (Priority: P1) 🎯 MVP

**Goal**: `loop_diagnostics` summarizes a recorded Loop Event stream — iterations, runs, retries, repairs,
human-review, latest outcomes, terminal status — reusing the Phase-3 reconstruction.

**Independent Test**: Given a scripted Loop Event stream, assert the diagnostics report the counts + latest
outcomes + terminal status; an empty stream yields an empty report; it is identical on every run.

- [X] T007 [P] [US1] Write integration tests in `tests/integration/test_inspect_us1.py` (MUST FAIL first): `loop_diagnostics(events)` over a scripted stream reports iterations, runs, retries (`retry_scheduled`), repairs (`repair_requested`), human-reviews (`human_review_requested`), the latest validation/evaluation outcomes, and the terminal status (`loop_completed`/`loop_failed`); the latest-state fields match `reconstruct_state(events)`; an empty stream ⇒ an empty report; an unknown loop type is skipped; deterministic (US1 scenarios 1–3; SC-001/002/008).
- [X] T008 [US1] Implement `src/loopplane/inspect/diagnostics.py`: `LoopDiagnostics` and `loop_diagnostics(events)` counting by `type` and reusing `reconstruct_state` for runs + latest outcomes + terminal status (FR-010, FR-011, FR-062).
- [X] T009 [US1] Export `LoopDiagnostics`, `loop_diagnostics`; run `pytest tests/integration/test_inspect_us1.py --basetemp=".pytmp"` → green.

**Checkpoint**: MVP — a developer gets a deterministic loop summary from a recorded stream.

---

## Phase 4: User Story 2 - See what happened in an agent run (Priority: P2)

**Goal**: `run_diagnostics` summarizes a recorded Runtime Event stream — tool-call / turn / error counts +
termination reason — metadata only.

**Independent Test**: Given a scripted Runtime Event stream, assert the diagnostics report the counts +
termination reason; an unknown event type is skipped.

- [X] T010 [P] [US2] Write integration tests in `tests/integration/test_inspect_us2.py` (MUST FAIL first): `run_diagnostics(events)` over a scripted stream reports the tool-call count (`tool-call-started`), turn count (`turn-completed`), error count (`diagnostic`), and the `run-terminated` reason; an empty stream ⇒ zero / `None`; an unknown type is skipped; the result carries no content or arguments (US2 scenarios 1–2; SC-003/004).
- [X] T011 [US2] Extend `src/loopplane/inspect/diagnostics.py`: `RunDiagnostics` and `run_diagnostics(events)` counting by `type` and reading the termination reason (metadata only) (FR-020, FR-021).
- [X] T012 [US2] Export `RunDiagnostics`, `run_diagnostics`; run `pytest tests/integration/test_inspect_us2.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1 + US2 — loop- and run-level diagnostics.

---

## Phase 5: User Story 3 - Build a trace of a loop and its runs (Priority: P2)

**Goal**: `build_trace` nests loop → iteration → run → tool/turn spans, metadata only.

**Independent Test**: Given correlated Loop and Runtime streams, assert the nesting + ids/types/counts only;
a session with no run stream ⇒ a childless run span.

- [X] T013 [P] [US3] Write integration tests in `tests/integration/test_inspect_us3.py` (MUST FAIL first): `build_trace(loop_events, run_events_by_session)` nests loop → iteration (by `iteration_index`) → run (by `session_id`) → tool_call / turn; each span carries only kind / id / `sequence` / children (no content or arguments); a `session_id` with no correlated stream ⇒ a childless run span; an empty loop stream ⇒ `Trace(root=None)` (US3 scenarios 1–2; SC-003, FR-030–FR-032).
- [X] T014 [US3] Implement `src/loopplane/inspect/trace.py`: `SpanKind`, `TraceSpan`, `Trace`, and `build_trace(loop_events, run_events_by_session)` (FR-030–FR-032).
- [X] T015 [US3] Export the trace types; run `pytest tests/integration/test_inspect_us3.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US3 — diagnostics + a structured trace.

---

## Phase 6: User Story 4 - Read a debug timeline (Priority: P2)

**Goal**: `build_timeline` orders entries by monotonic sequence and pairs started/completed spans.

**Independent Test**: Given a stream with start/complete pairs, assert sequence ordering, pairing, and an
explicit open span for an unpaired start.

- [X] T016 [P] [US4] Write integration tests in `tests/integration/test_inspect_us4.py` (MUST FAIL first): `build_timeline(events)` orders entries by `sequence` (stable), pairs a started event with its completion (e.g. `tool-call-started` ↔ `tool-call-completed`), marks an unpaired start `open=True`, sorts a duplicate/out-of-order sequence deterministically, and is identical on every run (US4 scenarios 1–2; SC-007, FR-040/FR-041).
- [X] T017 [US4] Implement `src/loopplane/inspect/timeline.py`: `TimelineEntry`, `Timeline`, and `build_timeline(events)` over `SequencedEvent`s (FR-040, FR-041).
- [X] T018 [US4] Export the timeline types; run `pytest tests/integration/test_inspect_us4.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US4 — diagnostics, trace, and a reproducible timeline.

---

## Phase 7: User Story 5 - Replay a recorded stream (Priority: P3)

**Goal**: `replay` feeds a recorded stream through a sink in recorded order, bracketed by start/complete,
starting no run.

**Independent Test**: Given a recorded stream and a recording sink, assert every event is delivered in
recorded order and no run is started.

- [X] T019 [P] [US5] Write integration tests in `tests/integration/test_inspect_us5.py` (MUST FAIL first): `replay(events, sink)` awaits the sink for every event in recorded order, returns `ReplaySummary(delivered=len, complete=True)`, and an empty stream ⇒ `ReplaySummary(0, True)`; the recording sink receives exactly the recorded events; no run is started (US5 scenarios 1–2; SC-009, FR-050/FR-051).
- [X] T020 [US5] Implement `src/loopplane/inspect/replay.py`: `ReplaySummary` and `async def replay(events, sink)` feeding the sink in recorded order (no run driven) (FR-050, FR-051).
- [X] T021 [US5] Export `ReplaySummary`, `replay`; run `pytest tests/integration/test_inspect_us5.py --basetemp=".pytmp"` → green.

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T022 [P] Write contract tests in `tests/contract/test_inspect_boundary.py`: an import-boundary audit (every `src/loopplane/inspect/*.py` imports only `loopplane.engineering` / `loopplane.events` / `loopplane.inspect` + stdlib, and references no `run_loop` / `LoopController` / `loopplane.controller` / `loopplane.host` / `loopplane.gateway` / `loopplane.context` / sibling-layer token); a **no-run** audit (no `.run(` reference); determinism (each transform twice ⇒ identical); a metadata-only assertion (FR-061/FR-062, NFR-003/NFR-006, SC-002/005).
- [X] T023 [P] Extend `tests/contract/test_public_safety.py` with `PHASE10_TARGETS` (`src/loopplane/inspect`, `examples/inspect_quickstart.py`, `docs/observability-debug.md`, `specs/010-loopplane-observability-debug-console`) and a `test_phase10_inspect_files_are_public_safe` scan.
- [X] T024 [P] Create `examples/inspect_quickstart.py`: a public-safe, credential-free runnable building scripted Loop + Runtime streams and printing `loop_diagnostics` / `run_diagnostics` / `build_trace` / `build_timeline` / `replay` results — metadata only, no run started (per [quickstart.md](./quickstart.md)).
- [X] T025 [P] Create `docs/observability-debug.md`: a public-safe guide — loop/run diagnostics → trace → timeline → replay, Constitution VI (consume recorded events, never re-emit), and the reserved extension points (FR-090–FR-094).
- [X] T026 Finalize `src/loopplane/inspect/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [X] T027 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/inspect_quickstart.py`; confirm the public-safety scan is green (SC-006); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (the sequenced-event protocol + helper).
- **US1 (Phase 3)**: depends on Foundational. MVP (loop diagnostics).
- **US2 (Phase 4)**: depends on Foundational; extends `diagnostics.py`.
- **US3 (Phase 5)**, **US4 (Phase 6)**, **US5 (Phase 7)**: depend on Foundational; independent of each other.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- The protocol/helper before the transforms; each phase ends on its pytest gate; commit per stable phase.

## Parallel Opportunities

- T002 (helpers) runs alongside the Phase-2 test authoring.
- Across stories: `trace.py`, `timeline.py`, `replay.py` are independent files — their `[P]` test-authoring
  and implementation can proceed in parallel once Foundational is green (US2 extends `diagnostics.py`, so it
  serializes with US1 on that file).
- Polish: T022–T025 are independent files (`[P]`); T026/T027 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (the sequenced-event protocol) → Phase 3 US1 (loop diagnostics).
2. **STOP and VALIDATE**: a developer gets a deterministic, metadata-only loop summary from a recorded
   stream, reusing the Phase-3 reconstruction.

### Incremental Delivery

Foundational → US1 (MVP) → US2 (run diagnostics) → US3 (trace) → US4 (timeline) → US5 (replay) → Polish.
Each phase is an independently testable, revertible increment; no Phase-1/2/3 source is modified.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- Every transform is deterministic (sequence-ordered, not wall-clock), metadata-only, and read-only; tests
  assert no content/arguments surfaced, no run driven, and a safe result on empty/unknown/unpaired streams.
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: importing a runtime control internal / sibling layer; driving a run or re-emitting the live bus;
  reading a content payload; any wall-clock-dependent ordering.
