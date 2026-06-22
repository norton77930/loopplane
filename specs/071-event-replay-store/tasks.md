# Tasks: Event Replay Store

**Feature**: 071-event-replay-store | **Spec**: [spec.md](spec.md) | **Plan**:
[plan.md](plan.md) | **ADR**: [0012](../../docs/adr/0012-event-replay-store.md)

**Scope**: additive durable replay storage for session SSE reconnect. Default stays the unit 058
in-memory / disabled behavior unless a host explicitly configures a replay store. No new runtime
event type, termination reason, content block, Tool Gateway change, or `SCHEMA_VERSION` bump.

**Tests**: required. Write/verify failing focused tests before implementation.

## Phase 1: Setup & fixtures

**Purpose**: Create reusable replay-store test fixtures and frame helpers used by all stories.

- [ ] T001 Create shared replay-store test helpers in `tests/replay_helpers.py` for synthetic SSE frames, `EventReplayRecord` builders, owner ids, and temp backend factories.
- [ ] T002 Add import/export expectations for the new replay API in `tests/contract/test_api_reference.py` and `docs/api-reference.md` only for public names that will be exported.

---

## Phase 2: Foundational replay boundary

**Purpose**: Establish the protocol, record shape, validation, and first local backend contract.

- [ ] T003 Add failing contract tests in `tests/contract/test_event_replay_store.py` for `EventReplayRecord` validation: non-empty ids/frame, non-negative sequence, matching `id:` frame sequence, and public-safe construction.
- [ ] T004 Add failing contract tests in `tests/contract/test_event_replay_store.py` for shared `EventReplayStore` behavior: append, ordered `load_after`, owner filtering, unknown session empty result, retention, duplicate sequence handling, and delete.
- [ ] T005 Implement `EventReplayRecord`, `EventReplayStore`, public-safe problem messages, and `FileEventReplayStore` in `src/loopplane/webapi/replay.py`.
- [ ] T006 Export replay-store public names from `src/loopplane/webapi/__init__.py` only if required by the API reference contract.
- [ ] T007 Run `uv run pytest -q tests/contract/test_event_replay_store.py tests/contract/test_api_reference.py` and confirm the foundational boundary tests pass.

**Checkpoint**: A file-backed replay store can persist and replay bounded, owner-scoped SSE frames.

---

## Phase 3: User Story 1 - Resume After Process Loss Or Worker Change (Priority: P1) MVP

**Goal**: Reconnect can replay durable frames after `Last-Event-ID`, deduplicate replay/live overlap,
and continue from store polling when no local live channel exists.

**Independent Test**: Record frames into a replay store, reconnect with a last-seen sequence from a
fresh stream consumer, and assert only later frames are emitted in order before live or store-polled
continuation.

### Tests for User Story 1

- [ ] T008 [US1] Add failing unit tests in `tests/unit/test_webapi_reconnect.py` for durable replay ordering, malformed `Last-Event-ID`, replay/live deduplication, and store-polled tailing without a local live channel.
- [ ] T009 [US1] Add failing integration tests in `tests/integration/test_webapi_replay_store.py` proving a session reconnect replays stored frames after `Last-Event-ID` and then continues with later events.

### Implementation for User Story 1

- [ ] T010 [US1] Update `src/loopplane/webapi/sessions.py` so `reconnect_stream` can merge durable replay records, the existing in-memory buffer, and live frames while deduplicating by sequence.
- [ ] T011 [US1] Update `src/loopplane/webapi/sessions.py` so `run_session` appends streamed `id:` frames to an optional `EventReplayStore` without breaking live delivery when the append fails.
- [ ] T012 [US1] Update `src/loopplane/webapi/app.py` to accept an optional replay store and retention/polling settings, wire them into session opening and event streaming, and preserve existing route ownership checks.
- [ ] T013 [US1] Run `uv run pytest -q tests/unit/test_webapi_reconnect.py tests/integration/test_webapi_replay_store.py tests/contract/test_event_replay_store.py` and confirm US1 tests pass.

**Checkpoint**: Durable replay works for the MVP with the file store and webapi session stream.

---

## Phase 4: User Story 2 - Preserve Default And In-Memory Behavior (Priority: P1)

**Goal**: Existing hosts with no durable replay store keep unit 058 behavior unchanged.

**Independent Test**: Existing webapi SSE reconnect tests and disabled-buffer assertions pass
without expected-output changes when no replay store is configured.

### Tests for User Story 2

- [ ] T014 [US2] Add failing/no-regression tests in `tests/integration/test_webapi_replay_store.py` for no-store default behavior, disabled-buffer byte identity, and in-memory ring replay staying unchanged.
- [ ] T015 [US2] Verify existing unit 058 tests in `tests/integration/test_webapi_us3.py` and `tests/integration/test_webapi_sse_reconnect.py` require no expected-output changes.

### Implementation for User Story 2

- [ ] T016 [US2] Ensure `src/loopplane/webapi/app.py` and `src/loopplane/webapi/sessions.py` take the durable replay path only when a store is configured and keep no-store behavior byte-identical.
- [ ] T017 [US2] Run `uv run pytest -q tests/integration/test_webapi_replay_store.py tests/integration/test_webapi_us3.py tests/integration/test_webapi_sse_reconnect.py` and confirm US2 tests pass.

**Checkpoint**: Durable replay remains opt-in and existing SSE behavior is stable.

---

## Phase 5: User Story 3 - Operate Safely Across Backends And Tenants (Priority: P2)

**Goal**: File, SQLite, and optional Postgres backends share one contract; replay remains bounded,
owner-scoped, import-guarded, and public-safe.

**Independent Test**: A shared backend contract suite covers local and optional networked stores,
and webapi tests prove non-owner reconnect attempts cannot replay another principal's events.

### Tests for User Story 3

- [ ] T018 [US3] Extend `tests/contract/test_event_replay_store.py` with shared backend contract coverage for `FileEventReplayStore`, `SqliteEventReplayStore`, and `PostgresEventReplayStore` import-guard behavior.
- [ ] T019 [US3] Add failing corruption, unavailable-store, and retention tests in `tests/contract/test_event_replay_store.py` for file and SQLite stores.
- [ ] T020 [US3] Add failing owner-scoping and delete-cleanup tests in `tests/integration/test_webapi_replay_store.py` for cross-principal reconnect attempts and session deletion.

### Implementation for User Story 3

- [ ] T021 [US3] Implement `SqliteEventReplayStore` in `src/loopplane/webapi/replay.py` using standard-library SQLite, ordered range reads, retention pruning, corruption tolerance, and owner filtering.
- [ ] T022 [US3] Implement `PostgresEventReplayStore` in `src/loopplane/webapi/replay.py` using the existing import-guarded `loopplane[postgres]` posture and sync thread-bridge style from ADR 0008.
- [ ] T023 [US3] Update `src/loopplane/webapi/app.py` so session deletion also removes replay records when a store is configured.
- [ ] T024 [US3] Run `uv run pytest -q tests/contract/test_event_replay_store.py tests/integration/test_webapi_replay_store.py` and confirm US3 tests pass.

**Checkpoint**: Replay storage is backend-agnostic, bounded, owner-scoped, and safe on failures.

---

## Phase 6: Polish & gates

- [ ] T025 Update `docs/api-reference.md` for any exported replay-store names and keep descriptions metadata-only.
- [ ] T026 Run focused validation from `specs/071-event-replay-store/quickstart.md`.
- [ ] T027 Run full gates: `uv run ruff check`, `uv run ruff format --check src tests`, `uv run mypy src`, and `uv run pytest -q`.
- [ ] T028 Run board audits: `git diff --check`, `openspec/` scan, public-safety scan, and local `sensitive-scan.txt` if present.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 fixtures and blocks all user stories.
- **US1 (Phase 3)**: Depends on Phase 2 replay boundary and is the MVP.
- **US2 (Phase 4)**: Depends on US1 wiring and validates the no-store/default behavior.
- **US3 (Phase 5)**: Depends on Phase 2 boundary and can use US1 webapi wiring; backend tests can
  start after T005.
- **Polish (Phase 6)**: Depends on all desired stories.

### User Story Dependencies

- **US1**: MVP. Establishes durable replay and stream integration with the file store.
- **US2**: Regression safety. Must pass before finalizing opt-in behavior.
- **US3**: Backend and tenant hardening. Extends the shared contract and webapi cleanup/scoping.

### Parallel Opportunities

- T008 and T009 touch separate test files after the shared helpers exist.
- T018 and T020 can be authored in parallel once the protocol shape is stable.
- T021 and T022 are backend implementations in the same module and should be kept serial in this
  workspace, but their tests can be prepared independently.
- T025 can run after public exports are finalized.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2 with `FileEventReplayStore`.
2. Complete US1 only.
3. Validate with `uv run pytest -q tests/unit/test_webapi_reconnect.py tests/integration/test_webapi_replay_store.py tests/contract/test_event_replay_store.py`.
4. Confirm durable replay emits only sequence-greater frames and does not duplicate live frames.

### Incremental Delivery

1. Build the replay-store record/protocol and file backend.
2. Wire durable replay into the session stream while preserving no-store behavior.
3. Prove default/in-memory behavior remains unchanged.
4. Add SQLite/Postgres backend parity and tenant/delete safeguards.
5. Run quickstart, full gates, and board audits.

## Cross-Artifact Analysis (gate)

Passed `/speckit-analyze`: no blocking cross-artifact inconsistencies; medium unavailable-store
coverage wording was corrected in T019 before implementation.
