# Tasks: Web Parity Foundation

**Input**: Design documents from `specs/074-web-parity-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by Constitution Principle X. Write focused failing tests before implementation for each user story.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks.
- **[Story]**: User story label for story phases only.
- Every task includes an exact repository path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create shared contract/type and transport seams used by all stories.

- [x] T001 Create backend web contract type module in `src/loopplane/webapi/contract_types.py`
- [x] T002 [P] Create web transport interface scaffold in `apps/web/src/api/transport.ts`
- [x] T003 [P] Create REST/SSE transport wrapper scaffold in `apps/web/src/api/restTransport.ts`
- [x] T004 [P] Create generated web API/event type artifact scaffold in `apps/web/src/api/generated.ts`
- [x] T005 [P] Create backend live-channel test helper scaffold in `tests/integration/webapi_live_helpers.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add failing contract and boundary tests before implementing any user story.

**Critical**: No user story implementation starts until these tests exist and fail for the missing behavior.

- [x] T006 [P] Add live envelope and ticket contract tests in `tests/contract/test_web_live_contract.py`
- [x] T007 [P] Add session management contract tests in `tests/contract/test_web_session_management_contract.py`
- [x] T008 [P] Add type artifact drift contract tests in `tests/contract/test_web_type_artifacts.py`
- [x] T009 [P] Add web transport boundary tests in `apps/web/src/__tests__/transport.test.ts`
- [x] T010 [P] Add REST/SSE compatibility regression tests in `apps/web/src/__tests__/restTransport.test.ts`
- [x] T011 Add shared transport usage seam in `apps/web/src/api/client.ts`

**Checkpoint**: Contract tests and transport boundary tests are in place. User stories can now be implemented in priority order.

---

## Phase 3: User Story 1 - Resilient Live Chat Channel (Priority: P1)

**Goal**: A web user can send, abort, answer approvals/questions, and reconnect through an additive bidirectional live session channel without losing or duplicating visible session state.

**Independent Test**: Start a session over the live channel, submit a prompt, receive normalized events, answer one pending prompt, abort one in-flight turn, disconnect/reconnect with replay, and verify existing REST/SSE flows still pass.

### Tests for User Story 1

- [x] T012 [P] [US1] Add ticket issuance and owner-scope integration tests in `tests/integration/test_webapi_live_channel.py`
- [x] T013 [P] [US1] Add live submit, abort, approval, and question integration tests in `tests/integration/test_webapi_live_channel.py`
- [x] T014 [P] [US1] Add reconnect replay and dedupe integration tests in `tests/integration/test_webapi_live_channel.py`
- [x] T015 [P] [US1] Add live transport send/reconnect queue tests in `apps/web/src/__tests__/liveTransport.test.ts`
- [x] T016 [P] [US1] Add App live transport behavior tests in `apps/web/src/__tests__/App.live.test.tsx`

### Implementation for User Story 1

- [x] T017 [US1] Define `LiveSessionTicket`, `LiveClientMessage`, and `LiveServerMessage` models in `src/loopplane/webapi/models.py`
- [x] T018 [US1] Implement live ticket issuance and expiry checks in `src/loopplane/webapi/app.py`
- [x] T019 [US1] Add additive live session endpoint wiring in `src/loopplane/webapi/app.py`
- [x] T020 [US1] Implement live channel coordinator in `src/loopplane/webapi/live.py`
- [x] T021 [US1] Route submit, abort, approval decision, and question answer messages through existing host/session boundaries in `src/loopplane/webapi/app.py`
- [x] T022 [US1] Reuse existing replay/history semantics for reconnect recovery in `src/loopplane/webapi/live.py`
- [x] T023 [US1] Implement live transport adapter in `apps/web/src/api/liveTransport.ts`
- [x] T024 [US1] Refactor App chat flow to consume the transport boundary in `apps/web/src/App.tsx`
- [x] T025 [US1] Wire transport selection into `apps/web/src/App.tsx`
- [x] T026 [US1] Preserve existing REST/SSE behavior through `apps/web/src/api/restTransport.ts`

**Checkpoint**: User Story 1 is functional and independently testable. Existing REST/SSE web session tests and desktop tests still pass.

---

## Phase 4: User Story 2 - Agent-Style Session Management (Priority: P2)

**Goal**: A web user can manage draft chats, preferred model, starred sessions, forks, search, and bulk delete with deterministic owner-scoped behavior.

**Independent Test**: Create a draft, submit it with a preferred model, star/unstar, fork, search, bulk delete selected sessions, and verify active-session fallback without affecting non-owned sessions.

### Tests for User Story 2

- [ ] T027 [P] [US2] Add checkpoint metadata tests for starred and fork fields in `tests/unit/test_checkpoint_session_parity.py`
- [ ] T028 [P] [US2] Add web API integration tests for star, unstar, fork, search, and bulk delete in `tests/integration/test_webapi_session_parity.py`
- [ ] T029 [P] [US2] Add principal scoping regression tests for session parity actions in `tests/integration/test_webapi_session_parity.py`
- [ ] T030 [P] [US2] Add draft and preferred model tests in `apps/web/src/__tests__/draftSession.test.ts`
- [ ] T031 [P] [US2] Add sidebar star/search/bulk delete tests in `apps/web/src/__tests__/Sidebar.sessionParity.test.tsx`
- [ ] T032 [P] [US2] Add fork action UI tests in `apps/web/src/__tests__/MessageList.fork.test.tsx`

### Implementation for User Story 2

- [ ] T033 [US2] Extend checkpoint session metadata contract in `src/loopplane/checkpoint/base.py`
- [ ] T034 [US2] Persist starred and fork metadata in `src/loopplane/checkpoint/file.py`
- [ ] T035 [US2] Persist starred and fork metadata in `src/loopplane/checkpoint/sqlite.py`
- [ ] T036 [US2] Add session parity host methods in `src/loopplane/host/host.py`
- [ ] T037 [US2] Add session parity request/response models in `src/loopplane/webapi/models.py`
- [ ] T038 [US2] Implement star, unstar, fork, search, and bulk-delete handlers in `src/loopplane/webapi/sessions.py`
- [ ] T039 [US2] Expose session parity routes in `src/loopplane/webapi/app.py`
- [ ] T040 [US2] Add client methods for session parity actions in `apps/web/src/api/client.ts`
- [ ] T041 [US2] Add draft chat and preferred model state in `apps/web/src/state/sessions.ts`
- [ ] T042 [US2] Render draft/new-chat and preferred model behavior in `apps/web/src/components/Composer.tsx`
- [ ] T043 [US2] Render star, search, and bulk delete controls in `apps/web/src/components/Sidebar.tsx`
- [ ] T044 [US2] Add fork-from-message action in `apps/web/src/components/MessageList.tsx`
- [ ] T045 [US2] Implement deterministic active-session fallback in `apps/web/src/App.tsx`

**Checkpoint**: User Story 2 is functional and independently testable. Session operations remain principal-scoped and older clients tolerate missing additive fields.

---

## Phase 5: User Story 3 - Contract-Safe Type Alignment (Priority: P3)

**Goal**: A maintainer can validate web-facing API and event types against backend-owned contracts while existing REST/SSE and desktop compatibility remain intact.

**Independent Test**: Run type-artifact validation, intentionally drift one representative API response and one representative event fixture in tests, and confirm validation fails clearly while existing REST/SSE and desktop gates pass.

### Tests for User Story 3

- [ ] T046 [P] [US3] Add API response drift failure coverage in `tests/contract/test_web_type_artifacts.py`
- [ ] T047 [P] [US3] Add session event drift failure coverage in `tests/contract/test_web_type_artifacts.py`
- [ ] T048 [P] [US3] Add generated type wrapper tests in `apps/web/src/__tests__/generatedTypes.test.ts`
- [ ] T049 [P] [US3] Add desktop compatibility regression test in `apps/desktop/src/__tests__/App.test.tsx`

### Implementation for User Story 3

- [ ] T050 [US3] Export backend-owned web contract fixtures from `src/loopplane/webapi/contract_types.py`
- [ ] T051 [US3] Add deterministic type artifact validation test support in `tests/contract/test_web_type_artifacts.py`
- [ ] T052 [US3] Align generated web API/event types in `apps/web/src/api/generated.ts`
- [ ] T053 [US3] Wrap generated types in existing web API types in `apps/web/src/api/types.ts`
- [ ] T054 [US3] Update web API client usage to rely on validated types in `apps/web/src/api/client.ts`
- [ ] T055 [US3] Keep desktop renderer compatible with shared web state in `apps/desktop/src/App.tsx`

**Checkpoint**: User Story 3 is functional and independently testable. Type validation catches representative drift and compatibility gates remain green.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Final cleanup, documentation, and delivery validation across all stories.

- [ ] T056 [P] Update 074 validation notes in `specs/074-web-parity-foundation/quickstart.md`
- [ ] T057 [P] Update roadmap status for 074 in `docs/loopplane-agent-board.md`
- [ ] T058 Run backend gates from `specs/074-web-parity-foundation/quickstart.md`
- [ ] T059 Run web gates from `specs/074-web-parity-foundation/quickstart.md`
- [ ] T060 Run desktop compatibility gates from `specs/074-web-parity-foundation/quickstart.md`
- [ ] T061 Run final public-safety gates from `specs/074-web-parity-foundation/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (P1)**: Depends on Foundational and is the MVP.
- **User Story 2 (P2)**: Depends on Foundational; may follow US1 sequentially to reduce shared-file conflicts.
- **User Story 3 (P3)**: Depends on Foundational; final compatibility validation depends on US1 and US2 artifacts.
- **Polish (Phase 6)**: Depends on all selected user stories.

### User Story Dependencies

- **US1**: No dependency on US2 or US3 after Foundational.
- **US2**: Can be implemented after Foundational, but sequential execution after US1 is recommended because both touch `apps/web/src/App.tsx`, `apps/web/src/api/client.ts`, and `src/loopplane/webapi/models.py`.
- **US3**: Can start after Foundational, but final type alignment should run after US1 and US2 define their public shapes.

### Parallel Opportunities

- T002-T005 can run in parallel after T001 is understood.
- T006-T010 can run in parallel because they create separate test files.
- T012-T016 can run in parallel before US1 implementation.
- T027-T032 can run in parallel before US2 implementation.
- T046-T049 can run in parallel before US3 implementation.
- T056-T057 can run in parallel after implementation is complete.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1.
3. Run backend tests covering live channel plus web typecheck/tests/build.
4. Confirm REST/SSE compatibility before continuing.

### Incremental Delivery

1. Add US1 live channel foundation and validate independently.
2. Add US2 session-management actions and validate independently.
3. Add US3 type-artifact drift checks and compatibility validation.
4. Run final quickstart gates and update board status.

### Notes

- Do not remove existing REST/SSE endpoints.
- Do not add browser provider-secret collection.
- Do not modify raw `openspec/`.
- Do not change runtime event semantics, content model, or Tool Gateway ownership.
- Keep commits scoped to completed phases or independently validated story increments.
