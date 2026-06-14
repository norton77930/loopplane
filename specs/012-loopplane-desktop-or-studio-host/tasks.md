---
description: "Task list for Desktop / Studio Host (012)"
---

# Tasks: Desktop / Studio Host

**Input**: Design documents from `/specs/012-loopplane-desktop-or-studio-host/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL
before implementation), then implements until green. All tests run **in-process** over a scripted
fake-model host — no GUI, no network, no OS process. The interactive approval round-trip is exercised
directly (no transport, so none of unit 011's buffering-client limitation applies).

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases IA–IF map below; the view
models + the `StudioHost` async-context-manager core are Foundational. US1 (run from the console) is
the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/studio/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Host Application Interface (`loopplane.host`: `LoopPlaneHost`,
`build_host`, `RunOutcome`, `Session`, `ApprovalDecision`, `RuntimeConfig`) plus `anyio` and stdlib. It
MUST NOT import `loopplane.events`, a runtime internal (`loopplane.controller` / `gateway` /
`dispatcher` / `loop`), or a sibling layer; MUST **execute no tool** (Constitution V) and **re-emit no
live bus** (Constitution VI — its only event path is a discard sink); MUST keep **view models
metadata-only** (history → `{role, block_count}`); and MUST spawn no OS process and open no socket. See
[contracts/studio-boundary.md](./contracts/studio-boundary.md). No Phase-1/2/11 source is modified; no
dependency is added.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `loopplane.studio` package skeleton: `src/loopplane/studio/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [X] T002 [P] Add studio test helpers in `tests/studio_helpers.py`: a public-safe deterministic fake model (`ScriptedModel` pattern — `text_model` / `multi_text_model` / `tool_then_text_model`), a `build_test_host(working_scope, *, model=None, tools=(ECHO_TOOL,), approval=None, storage=False)` returning a `LoopPlaneHost`, and an `auto_approve(payload: object) -> ApprovalDecision` handler (typed `object` so it is a valid `OnApproval` by contravariance, avoiding a `loopplane.events` import). No GUI/transport deps.

---

## Phase 2: Foundational (Blocking Prerequisites — view models + StudioHost core)

**Purpose**: The metadata-only view models and the `StudioHost` async-context-manager core every
command composes. **⚠️ Blocks US1–US5.**

- [X] T003 [P] Write unit tests in `tests/unit/test_studio_core.py`: `RunResultView.from_outcome` projects a `RunOutcome` and the block text never appears in the view (history is `{role, block_count}`, FR-030); `ErrorView` is `{kind, detail}` only; `StudioHost(host)` can be entered/exited as an async context manager (smoke).
- [X] T004 [P] Implement `src/loopplane/studio/views.py`: the frozen `HistoryEntryView`, `RunResultView` (+ `OutcomeView` alias), `SessionSummaryView`, and `ErrorView` dataclasses, plus the `RunOutcome` → view and `SessionSummary` → view projections (metadata-only; `SessionSummary` read via a structural `_SummaryLike` protocol) (FR-030, NFR-006; [data-model.md](./data-model.md)).
- [X] T005 Implement `src/loopplane/studio/console.py`: `StudioHost(host)` as an async context manager — `__aenter__` opens an `anyio` task group via an `AsyncExitStack`, `__aexit__` cancels/joins it; a module-level `_discard(event: object)` sink (names no event type, so no `loopplane.events` import).
- [X] T006 Finalize `src/loopplane/studio/__init__.py` exports (`StudioHost`, the view models).
- [X] T007 Run `pytest tests/unit/test_studio_core.py --basetemp=".pytmp"` → green (gate for Foundational; 3 passed).

**Checkpoint**: The view models and the `StudioHost` async-CM core are ready.

---

## Phase 3: User Story 1 - Run a prompt from the local console (Priority: P1) 🎯 MVP

**Goal**: `studio.run(prompt)` drives one run through the embedded host and returns a metadata-only
`RunResultView`.

**Independent Test**: `await studio.run(...)` → a `RunResultView` (metadata-only); a concurrent run →
`ErrorView(conflict)`; an empty prompt → `ErrorView(invalid)`.

- [X] T008 [P] [US1] Write integration tests in `tests/integration/test_studio_us1.py` (`pytest.mark.anyio`): `async with StudioHost(host)`, `await studio.run("...")` returns a `RunResultView` (session_id, termination_reason, integer turns_taken, metadata `history` of `{role, block_count}` — asserts the run's own content does not leak into the view); an empty prompt → `ErrorView(kind="invalid")`; a `RuntimeError` from a stub host → `ErrorView(kind="conflict")` (US1 scenarios 1–3; SC-001, FR-001–FR-003).
- [X] T009 [US1] Implement `StudioHost.run(prompt)` in `src/loopplane/studio/console.py`: validate the prompt, drive `host.run(prompt, _discard)`, project `RunOutcome` → `RunResultView`, map a sequential-run `RuntimeError` → `ErrorView(conflict)` (FR-001–FR-003).
- [X] T010 [US1] Run `pytest tests/integration/test_studio_us1.py --basetemp=".pytmp"` → green (3 passed; full suite 536).

**Checkpoint**: MVP — a developer drives a run from the console and gets a metadata-only view.

---

## Phase 4: User Story 2 - Manage local sessions (Priority: P2)

**Goal**: open / list / select / close interactive sessions over the embedded host.

**Independent Test**: open a session (it appears in `list_sessions`), select it, close it; an unknown id
→ `ErrorView(not-found)`.

- [X] T011 [P] [US2] Write integration tests in `tests/integration/test_studio_us2.py`: `await studio.open_session()` → a `session_id` tracked by `studio.list_sessions()`; `studio.select(unknown)` → `ErrorView(not-found)`; `await studio.cancel(session_id)` closes it and frees the host; a second open while active → `ErrorView(conflict)` (US2 scenarios 1–3; FR-010/FR-011, FR-003).
- [X] T012 [US2] Implement `src/loopplane/studio/sessions.py` (`SessionEntry` + `run_session`: a task-group-held `async with host.session(sink, on_approval=...)` keyed by `session_id`, a `close` event, conflict signalled to the opener via `box['error']`; `OnApproval`/`Sink` typed over `object` to avoid a `loopplane.events` import) and the `StudioHost` open / list / select / cancel commands in `console.py` (FR-010, FR-011, FR-003).
- [X] T013 [US2] Run `pytest tests/integration/test_studio_us2.py --basetemp=".pytmp"` → green (2 passed; full suite 538).

**Checkpoint**: US1 + US2 — run and a local session manager.

---

## Phase 5: User Story 3 - Conduct an interactive session from the console (Priority: P3)

**Goal**: submit input, answer a pending approval/question (in-process), and cancel.

**Independent Test**: open a session with an injected `on_approval`, submit a prompt that triggers an
approval → it is answered and the run reaches its outcome; cancel never hangs; an unknown id → an
explicit negative result.

- [X] T014 [P] [US3] Write integration tests in `tests/integration/test_studio_us3.py`: open a session with `on_approval=auto_approve`; `await studio.submit(id, prompt)` over `tool_then_text_model` + `ApprovalPolicy(ask={"echo"})` reaches a `RunResultView(termination_reason="natural-completion")` (the approval answered **in-process** by the injected handler); `studio.answer_approval/answer_question(id, "ghost", ...)` → `False`; an unknown session → `ErrorView(not-found)` (submit + answer). "Cancel never hangs on a pending approval" is delegated to `Session.cancel()` (Phase-2 host suite) + US2's registry close (US3 scenarios 1–3; FR-020–FR-022).
- [X] T015 [US3] Implement `StudioHost` submit / answer_approval / answer_question in `console.py` over the held `Session`; `open_session(on_approval=...)` threads the handler into `host.session` (`cancel` was implemented in US2) (FR-020–FR-022).
- [X] T016 [US3] Run `pytest tests/integration/test_studio_us3.py --basetemp=".pytmp"` → green (2 passed; full suite 540).

**Checkpoint**: US1–US3 — run, session manager, and an in-process interactive session.

---

## Phase 6: User Story 4 - Inspect a session locally (Priority: P4)

**Goal**: metadata-only `history_view`, outcome view, and the sessions list.

**Independent Test**: after a run, request the history-metadata view (no content), the outcome view, and
the sessions list; an unknown id → `ErrorView(not-found)`.

- [ ] T017 [P] [US4] Write integration tests in `tests/integration/test_studio_us4.py` (MUST FAIL first): after a run on a storage-backed host, `studio.history_view(id)` → `HistoryEntryView`s with **no** block text; `studio.list_sessions()` → `SessionSummaryView`s; an unknown session → `ErrorView(not-found)` (US4 scenarios 1–3; SC-003, FR-030).
- [ ] T018 [US4] Implement `StudioHost.history_view(session_id)` and confirm `list_sessions` in `console.py`: project `host.history_snapshot` / `host.list_sessions` to metadata-only views, mapping `KeyError` → `ErrorView(not-found)` (FR-030).
- [ ] T019 [US4] Run `pytest tests/integration/test_studio_us4.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US4 — run, session manager, interactive, and inspection.

---

## Phase 7: User Story 5 - Embed the host as a local sidecar (Priority: P5)

**Goal**: a `SidecarHost` contract + an in-process implementation with a start/stop lifecycle.

**Independent Test**: start an in-process sidecar, drive a run through it, stop it (idempotent); a
command after stop → `ErrorView(not-available)`.

- [ ] T020 [P] [US5] Write integration tests in `tests/integration/test_studio_us5.py` (MUST FAIL first): `InProcessSidecar(host)`; `await sidecar.start()` then `await sidecar.studio.run("...")` works; `await sidecar.stop()` twice is idempotent and orphans no run; a command after stop → `ErrorView(kind="not-available")` (US5 scenarios 1–3; FR-040/FR-041, SC-006).
- [ ] T021 [US5] Implement `src/loopplane/studio/sidecar.py`: the `SidecarHost` Protocol (`studio` / `start` / `stop`) and `InProcessSidecar` wrapping a `LoopPlaneHost` + `StudioHost`; `start` opens the studio, `stop` is idempotent and joins the task group; a command after stop returns `ErrorView(not-available)` (FR-040, FR-041).
- [ ] T022 [US5] Run `pytest tests/integration/test_studio_us5.py --basetemp=".pytmp"` → green.

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Write contract tests in `tests/contract/test_studio_boundary.py`: an import-boundary audit (every `src/loopplane/studio/*.py` imports only `loopplane.host` / `anyio` / stdlib); a text scan finding no `loopplane.events` / `loopplane.controller` / `loopplane.gateway` / `loopplane.dispatcher` / `loopplane.loop` / `RuntimeController` / `EventEmitter` / `serialize_event` / `subprocess` / `socket` / sibling-package token; a metadata-only view assertion; a conflict/not-available fail-safe assertion (NFR-001/002/003, FR-051, SC-003/005).
- [ ] T024 [P] Extend `tests/contract/test_public_safety.py` with `PHASE12_TARGETS` (`src/loopplane/studio`, `examples/studio_quickstart.py`, `docs/desktop-studio-host.md`, `specs/012-loopplane-desktop-or-studio-host`) and a `test_phase12_studio_files_are_public_safe` scan.
- [ ] T025 [P] Create `examples/studio_quickstart.py`: a public-safe, in-process runnable that builds a host with the fake model, opens a `StudioHost`, drives a run + lists/inspects sessions, printing only public-safe view models (per [quickstart.md](./quickstart.md)).
- [ ] T026 [P] Create `docs/desktop-studio-host.md`: a public-safe guide — the console commands → view models, the local session manager, the in-process sidecar lifecycle, embedding via `StudioHost`, and the reserved extension points (GUI / process spawn / network).
- [ ] T027 Finalize `src/loopplane/studio/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [ ] T028 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/studio_quickstart.py`; confirm the public-safety scan is green (SC-003/005); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (view models + `StudioHost` core).
- **US1 (Phase 3)**: depends on Foundational. MVP (run).
- **US2 (Phase 4)**: depends on Foundational; adds `sessions.py` + the session-manager commands.
- **US3 (Phase 5)**: depends on US2 (the held session); adds submit / answer / cancel.
- **US4 (Phase 6)**: depends on Foundational; read-only views (best after US2 so sessions exist).
- **US5 (Phase 7)**: depends on Foundational (wraps `StudioHost`); the sidecar lifecycle.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- The views/core before the commands; each phase ends on its pytest gate; commit per stable phase.

## Parallel Opportunities

- T002 (helpers) runs alongside the Phase-2 test authoring.
- Foundational: `views.py` (T004) is independent of `console.py` (T005) at the file level (`[P]`).
- Across stories: `sidecar.py` (US5) is an independent file from the `console.py` command additions; its
  `[P]` test authoring can proceed once Foundational is green. US3/US4 serialize on `console.py`.
- Polish: T023–T026 are independent files (`[P]`); T027/T028 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (view models + `StudioHost` core) → Phase 3 US1 (`run`).
2. **STOP and VALIDATE**: a developer drives a run from the console and gets a deterministic,
   metadata-only view — in-process, offline.

### Incremental Delivery

Foundational → US1 (MVP) → US2 (session manager) → US3 (interactive) → US4 (inspection) → US5 (sidecar)
→ Polish. Each phase is an independently testable, revertible increment; no Phase-1/2/11 source is
modified; no dependency is added.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- Every view is metadata-only (no history blocks / tool I/O); the command → view mapping is
  deterministic; the layer executes no tool, re-emits no live bus, spawns no process, and opens no
  socket.
- All tests run in-process over a scripted fake-model host (FR-051, NFR-006/NFR-007).
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: importing `loopplane.events` / a runtime internal / a sibling layer; executing a tool or
  re-emitting the live bus; leaking a content block, stack trace, internal type, path, or secret.
