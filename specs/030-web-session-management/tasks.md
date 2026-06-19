# Tasks: Web Session Management

**Feature**: `specs/030-web-session-management` | **Input**: plan.md, spec.md, research.md, data-model.md, contracts/

Full-stack, additive, no ADR. **TDD**: write the failing test before the implementation in each
story. Stories are ordered P1 → P3 (US1 read-side titles/grouping; US2 rename; US3 delete).

## Phase 1: Setup

- [ ] T001 Establish a clean baseline: run `uv run pytest -q` and `npm --prefix apps/web test` and confirm green before changes.

## Phase 2: Foundational (blocking — the extended session summary contract)

- [ ] T002 Extend `SessionSummaryView` and its `_SummaryLike` Protocol to `{session_id, label, last_active_at, created_at}` and update `from_summary` in `src/loopplane/webapi/models.py` (source `SessionSummary` already carries the timestamps).
- [ ] T003 Update the two contract-pinned field-set assertions from `{session_id, label}` to the new set in `tests/contract/test_webapi_boundary.py` and `tests/integration/test_webapi_us4.py`; confirm the webapi import-boundary test stays green.
- [ ] T004 [P] Update the frontend `SessionSummary` type to `{session_id, label, last_active_at, created_at}` in `apps/web/src/api/types.ts`.

## Phase 3: User Story 1 — Recognize sessions by title and recency (P1)

**Goal**: sidebar shows titles (not raw ids) grouped Today / Yesterday / Earlier.
**Independent test**: with sessions of differing ages, titles + groups render; selecting one opens it.

- [ ] T005 [P] [US1] Write `apps/web/src/__tests__/sessionGroups.test.ts` (FAIL first): buckets sessions into Today / Yesterday / Earlier by local day from `last_active_at`.
- [ ] T006 [US1] Create `apps/web/src/lib/sessionGroups.ts` — a pure date-bucket helper — to pass T005.
- [ ] T007 [P] [US1] Extend `apps/web/src/__tests__/Sidebar.test.tsx` (FAIL first): renders `label ?? session_id` as the title (raw id not shown when a label exists) and renders the date-group headers.
- [ ] T008 [US1] Update `apps/web/src/components/Sidebar.tsx`: render the title (`label ?? <short id fallback>`) and group rows via `sessionGroups`; keep the existing empty state.

## Phase 4: User Story 2 — Rename a session (P2)

**Goal**: rename persists server-side (reload + restart + other device).
**Independent test**: rename → shows immediately; reload + backend restart → still shown.

- [ ] T009 [P] [US2] Write checkpoint `set_title` tests for BOTH backends in `tests/unit/` (FAIL first): the latest title wins in `list_sessions()` and after `rebuild_session`/resume.
- [ ] T010 [P] [US2] Write host/controller `set_session_title` unit tests in `tests/unit/` (FAIL first): delegates to the store; raises without a configured store.
- [ ] T011 [P] [US2] Write webapi PATCH tests in `tests/integration/test_webapi_session_mgmt.py` (FAIL first): rename shows in the listing; **non-owner → 404**; empty/whitespace title → 422; unknown id → 404.
- [ ] T012 [US2] Add `set_title(session_id, title)` to the `CheckpointStore` Protocol in `src/loopplane/checkpoint/base.py`.
- [ ] T013 [US2] Implement `FileCheckpointStore.set_title` (append a fresh session-meta) and change `_read_meta` to return the **last** session-meta in `src/loopplane/checkpoint/file.py`.
- [ ] T014 [US2] Implement `SqliteCheckpointStore.set_title` (insert a fresh meta row) and change the meta-pick to the **last** in `list_sessions` in `src/loopplane/checkpoint/sqlite.py`.
- [ ] T015 [US2] Add `RuntimeController.set_session_title` (delegate to the store; raise without a store; update a loaded `_Session.label`) in `src/loopplane/controller/controller.py`.
- [ ] T016 [US2] Add `LoopPlaneHost.set_session_title` (re-expose) in `src/loopplane/host/host.py`.
- [ ] T017 [US2] Add `RenameRequest{title}` (`min_length=1`) and `PATCH /v1/sessions/{id}` (owner-gated via `_owned_or_404`) in `src/loopplane/webapi/models.py` + `src/loopplane/webapi/app.py`.
- [ ] T018 [P] [US2] Add `ApiClient.renameSession(id, title)` (PATCH) in `apps/web/src/api/client.ts` (+ a client unit test).
- [ ] T019 [US2] Add the Sidebar rename affordance (per-session overflow menu → inline rename) wired to `renameSession` + `refreshSessions` in `apps/web/src/components/Sidebar.tsx` (+ `App.tsx`); extend `Sidebar.test.tsx`.

## Phase 5: User Story 3 — Delete a session (P3)

**Goal**: durable deletion, confirm-guarded; deleting the open session returns to empty state.
**Independent test**: delete (confirm) → gone; reload + restart → stays gone.

- [ ] T020 [P] [US3] Write checkpoint `delete_session` tests for BOTH backends in `tests/unit/` (FAIL first): removed from `list_sessions()`/`load()`; idempotent on an unknown id.
- [ ] T021 [P] [US3] Write host/controller `delete_session` unit tests in `tests/unit/` (FAIL first).
- [ ] T022 [P] [US3] Write webapi DELETE tests in `tests/integration/test_webapi_session_mgmt.py` (FAIL first): removed from the listing; **non-owner → 404**; unknown id → 404.
- [ ] T023 [US3] Add `delete_session(session_id)` to the `CheckpointStore` Protocol in `src/loopplane/checkpoint/base.py`.
- [ ] T024 [US3] Implement `FileCheckpointStore.delete_session` (remove the session dir, idempotent) in `src/loopplane/checkpoint/file.py`.
- [ ] T025 [US3] Implement `SqliteCheckpointStore.delete_session` (`DELETE FROM records WHERE session_id = ?`) in `src/loopplane/checkpoint/sqlite.py`.
- [ ] T026 [US3] Add `RuntimeController.delete_session` (pop a live `_Session` if present, then delegate) in `src/loopplane/controller/controller.py`.
- [ ] T027 [US3] Add `LoopPlaneHost.delete_session` (re-expose) in `src/loopplane/host/host.py`.
- [ ] T028 [US3] Add `DELETE /v1/sessions/{id}` (owner-gated; cancel a live entry first, then delete durable records) in `src/loopplane/webapi/app.py`.
- [ ] T029 [P] [US3] Add `ApiClient.deleteSession(id)` (DELETE) in `apps/web/src/api/client.ts` (+ a client unit test).
- [ ] T030 [US3] Add the Sidebar delete affordance (overflow menu → delete + confirm) wired to `deleteSession`; handle deleting the **open** session → empty/new state in `apps/web/src/components/Sidebar.tsx` + `App.tsx`; extend `Sidebar.test.tsx`.

## Phase 6: Polish & cross-cutting

- [ ] T031 Run the Python gate: `uv run pytest` + `uv run ruff check .` + `uv run mypy` (strict); confirm the **webapi import-boundary test is green**.
- [ ] T032 Run the web gate: `npm --prefix apps/web run typecheck` + `test` + `build`.
- [ ] T033 [P] Add a "Session management (unit 030)" section to `docs/web-frontend.md`.

## Dependencies

- **Phase 2 (T002–T004)** blocks the user stories (the extended summary is the shared contract).
- **US1 (T005–T008)** depends only on Phase 2 — it reads the existing `label` + new timestamps; it is the MVP.
- **US2 (T009–T019)** depends on Phase 2; the rename read-side change (last-meta-wins) lands here.
- **US3 (T020–T030)** depends on Phase 2; independent of US2 (different store methods/routes).
- **Polish (T031–T033)** last.
- TDD: within each story the `[P]` test tasks precede their implementation tasks.

## Parallel opportunities

- T004 ‖ T002/T003 (frontend type vs backend view, different files).
- Within US2/US3, the test tasks (T009/T010/T011 ‖ ; T020/T021/T022 ‖) are independent.
- Backend store impl (T013 ‖ T014; T024 ‖ T025) are different files.

## MVP scope

**US1** alone (titles + recency grouping over the existing data) is a shippable MVP — it removes the
raw-UUID wall immediately. US2 (rename) and US3 (delete) complete management.
