# Tasks: Web Capability Management

**Input**: Design documents from `specs/075-web-capability-management/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by Constitution Principle X and FR-014. Write focused failing tests before implementation for each user story.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks.
- **[Story]**: User story label for story phases only.
- Every task includes an exact repository path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create shared capability-management seams and type scaffolds used by all stories.

- [x] T001 Create capability management host model scaffold in `src/loopplane/host/capabilities.py`
- [x] T002 [P] Add capability management web model scaffolds in `src/loopplane/webapi/models.py`
- [x] T003 [P] Add capability management API type scaffolds in `apps/web/src/api/types.ts`
- [x] T004 [P] Add capability management client method scaffolds in `apps/web/src/api/client.ts`
- [x] T005 [P] Add capability settings component scaffold in `apps/web/src/components/CapabilitySettings.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add failing contract and boundary tests before implementing any user story.

**Critical**: No user story implementation starts until these tests exist and fail for missing behavior.

- [x] T006 [P] Add memory/skills capability contract tests in `tests/contract/test_web_capability_management_contract.py`
- [x] T007 [P] Add MCP/project context contract tests in `tests/contract/test_web_context_management_contract.py`
- [x] T008 [P] Add schedules/model-defaults contract tests in `tests/contract/test_web_schedule_model_contract.py`
- [x] T009 [P] Add public-safe capability error tests in `tests/contract/test_web_capability_management_contract.py`
- [x] T010 [P] Add web capability client tests in `apps/web/src/__tests__/capabilityClient.test.ts`
- [x] T011 [P] Add web capability settings smoke tests in `apps/web/src/__tests__/CapabilitySettings.test.tsx`
- [x] T012 [P] Add 074 compatibility regression tests for settings routing in `apps/web/src/__tests__/App.capabilities.test.tsx`

**Checkpoint**: Contract tests and web boundary tests are in place. User stories can now be implemented in priority order.

---

## Phase 3: User Story 1 - Manage Memory And Skills (Priority: P1)

**Goal**: A web user can list, open, write/import, and delete owned memory entries and skills with public-safe status and errors.

**Independent Test**: Use the capability management surface to list memory and skills, open one owned item, save or import one item, delete one item, refresh, and verify read-only/invalid states remain safe.

### Tests for User Story 1

- [x] T013 [P] [US1] Add memory CRUD unit tests in `tests/unit/test_capability_management.py`
- [x] T014 [P] [US1] Add skill write/import/delete unit tests in `tests/unit/test_capability_management.py`
- [x] T015 [P] [US1] Add memory/skills web API integration tests in `tests/integration/test_webapi_capability_management.py`
- [x] T016 [P] [US1] Add memory/skills UI tests in `apps/web/src/__tests__/CapabilitySettings.test.tsx`

### Implementation for User Story 1

- [x] T017 [US1] Implement memory operation models in `src/loopplane/host/capabilities.py`
- [x] T018 [US1] Implement skill operation models in `src/loopplane/host/capabilities.py`
- [x] T019 [US1] Add host memory management methods in `src/loopplane/host/host.py`
- [x] T020 [US1] Add host skill management methods in `src/loopplane/host/host.py`
- [x] T021 [US1] Add memory/skills request and response views in `src/loopplane/webapi/models.py`
- [x] T022 [US1] Add memory/skills management routes in `src/loopplane/webapi/app.py`
- [x] T023 [US1] Add memory/skills API client methods in `apps/web/src/api/client.ts`
- [x] T024 [US1] Render memory management controls in `apps/web/src/components/CapabilitySettings.tsx`
- [x] T025 [US1] Render skill management controls in `apps/web/src/components/CapabilitySettings.tsx`
- [x] T026 [US1] Wire capability settings entry point from `apps/web/src/components/InspectionPanel.tsx`

**Checkpoint**: User Story 1 is functional and independently testable. Existing read-only inspection still works.

---

## Phase 4: User Story 2 - Manage MCP And Workspace Context (Priority: P2)

**Goal**: A web user can add/update/delete/reconnect MCP configurations and bind sessions to project/workspace contexts.

**Independent Test**: Add or update an MCP configuration, reconnect it, delete it, create/select a project/workspace context, bind it to a session, and verify owner scoping.

### Tests for User Story 2

- [x] T027 [P] [US2] Add MCP management unit tests in `tests/unit/test_capability_management.py`
- [x] T028 [P] [US2] Add project/workspace context unit tests in `tests/unit/test_capability_management.py`
- [x] T029 [P] [US2] Add MCP/context web API integration tests in `tests/integration/test_webapi_context_management.py`
- [x] T030 [P] [US2] Add MCP/context UI tests in `apps/web/src/__tests__/CapabilitySettings.test.tsx`
- [x] T031 [P] [US2] Add session context binding regression tests in `tests/integration/test_webapi_context_management.py`

### Implementation for User Story 2

- [x] T032 [US2] Implement MCP operation models in `src/loopplane/host/capabilities.py`
- [x] T033 [US2] Implement project/workspace context models in `src/loopplane/host/capabilities.py`
- [x] T034 [US2] Add host MCP management methods in `src/loopplane/host/host.py`
- [x] T035 [US2] Add host project/workspace context methods in `src/loopplane/host/host.py`
- [x] T036 [US2] Extend session metadata for context binding in `src/loopplane/checkpoint/base.py`
- [x] T037 [US2] Persist context binding metadata in `src/loopplane/checkpoint/file.py`
- [x] T038 [US2] Persist context binding metadata in `src/loopplane/checkpoint/sqlite.py`
- [x] T039 [US2] Add MCP/context request and response views in `src/loopplane/webapi/models.py`
- [x] T040 [US2] Add MCP/context management routes in `src/loopplane/webapi/app.py`
- [x] T041 [US2] Add MCP/context API client methods in `apps/web/src/api/client.ts`
- [x] T042 [US2] Render MCP management controls in `apps/web/src/components/CapabilitySettings.tsx`
- [x] T043 [US2] Render project/workspace context controls in `apps/web/src/components/CapabilitySettings.tsx`
- [x] T044 [US2] Show active session context in `apps/web/src/App.tsx`

**Checkpoint**: User Story 2 is functional and independently testable. Context binding remains owner-scoped and optional.

---

## Phase 5: User Story 3 - Manage Schedules And Model Defaults (Priority: P3)

**Goal**: A web user can manage schedules and select default models only from the host-provided catalog.

**Independent Test**: Create/update/enable/disable/run-now/delete a schedule, select a default model, verify invalid models are rejected, and verify no provider credential fields render.

### Tests for User Story 3

- [x] T045 [P] [US3] Add schedule management unit tests in `tests/unit/test_capability_management.py`
- [x] T046 [P] [US3] Add model default unit tests in `tests/unit/test_capability_management.py`
- [x] T047 [P] [US3] Add schedules/model defaults web API integration tests in `tests/integration/test_webapi_schedule_model_management.py`
- [x] T048 [P] [US3] Add schedules/model defaults UI tests in `apps/web/src/__tests__/CapabilitySettings.test.tsx`
- [x] T049 [P] [US3] Add browser credential-boundary regression test in `apps/web/src/__tests__/CapabilitySettings.test.tsx`

### Implementation for User Story 3

- [x] T050 [US3] Implement schedule operation models in `src/loopplane/host/capabilities.py`
- [x] T051 [US3] Implement model default operation models in `src/loopplane/host/capabilities.py`
- [x] T052 [US3] Add host schedule management methods in `src/loopplane/host/host.py`
- [x] T053 [US3] Add host model default methods in `src/loopplane/host/host.py`
- [x] T054 [US3] Add schedule/model default request and response views in `src/loopplane/webapi/models.py`
- [x] T055 [US3] Add schedule/model default routes in `src/loopplane/webapi/app.py`
- [x] T056 [US3] Add schedule/model default API client methods in `apps/web/src/api/client.ts`
- [x] T057 [US3] Render schedule controls in `apps/web/src/components/CapabilitySettings.tsx`
- [x] T058 [US3] Render model default controls in `apps/web/src/components/CapabilitySettings.tsx`
- [x] T059 [US3] Preserve 074 per-session model selection behavior in `apps/web/src/App.tsx`

**Checkpoint**: User Story 3 is functional and independently testable. Browser model defaults use only host-provided catalog entries.

---

## Phase 6: Type Artifacts And Compatibility

**Purpose**: Keep web-facing types and desktop compatibility aligned after capability management routes are added.

- [ ] T060 [P] Add generated type wrapper tests for capability views in `apps/web/src/__tests__/generatedTypes.test.ts`
- [ ] T061 Add backend-owned capability type fixtures in `src/loopplane/webapi/contract_types.py`
- [ ] T062 Align generated capability API types in `apps/web/src/api/generated.ts`
- [ ] T063 Wrap generated capability types in `apps/web/src/api/types.ts`
- [ ] T064 [P] Add desktop compatibility smoke for shared web types in `apps/desktop/src/__tests__/App.test.tsx`

---

## Phase 7: Polish & Cross-Cutting Validation

**Purpose**: Final cleanup, documentation, and delivery validation across all stories.

- [ ] T065 [P] Update 075 validation notes in `specs/075-web-capability-management/quickstart.md`
- [ ] T066 [P] Update roadmap status for 075 in `docs/loopplane-agent-board.md`
- [ ] T067 Run backend gates from `specs/075-web-capability-management/quickstart.md`
- [ ] T068 Run web gates from `specs/075-web-capability-management/quickstart.md`
- [ ] T069 Run desktop compatibility gates from `specs/075-web-capability-management/quickstart.md`
- [ ] T070 Run final public-safety gates from `specs/075-web-capability-management/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (P1)**: Depends on Foundational and is the MVP.
- **User Story 2 (P2)**: Depends on Foundational; follows US1 to reduce shared-file conflicts.
- **User Story 3 (P3)**: Depends on Foundational; follows US2 because schedules/model defaults share the settings surface.
- **Type Artifacts And Compatibility (Phase 6)**: Depends on all user stories.
- **Polish (Phase 7)**: Depends on all selected user stories and compatibility tasks.

### User Story Dependencies

- **US1**: No dependency on US2 or US3 after Foundational.
- **US2**: Can be implemented after Foundational, but sequential execution after US1 is recommended because both touch `CapabilitySettings.tsx`, `client.ts`, `models.py`, and `app.py`.
- **US3**: Can start after Foundational, but final UI integration should follow US1/US2 so settings navigation is stable.

### Parallel Opportunities

- T002-T005 can run in parallel after T001 is understood.
- T006-T012 can run in parallel because they create separate test files or independent test sections.
- T013-T016 can run in parallel before US1 implementation.
- T027-T031 can run in parallel before US2 implementation.
- T045-T049 can run in parallel before US3 implementation.
- T060 and T064 can run in parallel after user stories define their public shapes.
- T065-T066 can run in parallel after implementation is complete.

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 memory/skills management.
3. Run backend tests covering memory/skills plus web typecheck/tests/build.
4. Confirm existing read-only inspection and 074 chat/session behavior before continuing.

### Incremental Delivery

1. Add US1 memory and skills management and validate independently.
2. Add US2 MCP and project/workspace context management and validate independently.
3. Add US3 schedules and model defaults and validate independently.
4. Align type artifacts and desktop compatibility.
5. Run final quickstart gates and update board status.

### Notes

- Do not remove existing read-only inspection endpoints.
- Do not add browser provider credential collection.
- Do not modify raw `openspec/`.
- Do not change runtime event semantics, content model, Tool Gateway ownership, or provider ownership.
- Keep commits scoped to completed phases or independently validated story increments.
