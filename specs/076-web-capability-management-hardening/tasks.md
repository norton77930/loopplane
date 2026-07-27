# Tasks: Web Capability Management Hardening

**Input**: Design documents from `specs/076-web-capability-management-hardening/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by Constitution Principle X and FR-020. Write focused failing tests before implementation for each user story.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after foundational work is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish shared contracts, type fixtures, and roadmap context for the new 076 unit.

- [X] T001 Verify roadmap rows for inserted 076 and shifted later units in `docs/loopplane-agent-board.md`
- [X] T002 [P] Add failing 076 backend contract artifact expectations in `tests/contract/test_web_type_artifacts.py` and `src/loopplane/webapi/contract_types.py`
- [X] T003 [P] Add failing 076 generated API type expectations in `apps/web/src/__tests__/generatedTypes.test.ts`
- [X] T004 [P] Verify 076 public-safety scan targets in `specs/076-web-capability-management-hardening/quickstart.md`
- [X] T005 [P] Add capability settings UI test fixture helpers in `apps/web/src/__tests__/capabilitySettingsHelpers.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add durable settings, mutation gating, public-safe operation handling, and scoped runtime activation seams used by all stories.

**Critical**: No user story implementation starts until this phase is complete.

### Tests for Foundational Behavior

- [X] T006 [P] Add durable round-trip, hashed filename, corruption, atomic-write, and sensitive-field unit tests in `tests/unit/test_capability_settings_store.py`
- [X] T007 [P] Add default-off mutation/activation gate and no-storage failure unit tests in `tests/unit/test_capability_management.py`
- [X] T008 [P] Add capability settings status, principal scoping, actions, and non-disclosure contract tests in `tests/contract/test_web_capability_management_contract.py`
- [X] T009 [P] Add scoped Tool Gateway descriptor, execution, replacement lease, and idempotent shutdown tests in `tests/unit/test_tool_gateway.py`
- [X] T010 [P] Add runtime activation owner/non-owner tests in `tests/integration/test_capability_runtime_activation.py`
- [X] T011 [P] Add web capability settings view smoke tests in `apps/web/src/__tests__/CapabilitySettingsView.test.tsx`

### Implementation for Foundational Behavior

- [X] T012 Implement durable records, scope/actions, settings status, MCP endpoint policy, and schedule runner protocols in `src/loopplane/host/capabilities.py`
- [X] T013 Implement versioned per-principal JSON, hashed paths, keyed locks, and atomic replacement in `src/loopplane/host/capability_store.py`
- [X] T014 Add default-off `CapabilityManagementConfig`, network MCP policy, and schedule runner validation to `src/loopplane/host/config.py`
- [X] T015 Implement capability orchestration in `src/loopplane/host/capability_manager.py` and wire the store through `src/loopplane/host/assembly.py`
- [X] T016 Add scoped managed adapter registration, replacement, descriptor filtering, and shutdown in `src/loopplane/gateway/gateway.py`
- [X] T017 Thread principal-aware tool descriptor selection into model request assembly in `src/loopplane/loop/loop.py`
- [X] T018 Thread principal-scoped memory/skill providers and context metadata updates through controller session assembly in `src/loopplane/controller/controller.py`
- [X] T019 Add public-safe capability operation/settings-status views and `GET /v1/capabilities/settings` in `src/loopplane/webapi/models.py` and `src/loopplane/webapi/app.py`
- [X] T020 Align generated capability API fixtures in `src/loopplane/webapi/contract_types.py`
- [X] T021 Align generated frontend capability types in `apps/web/src/api/generated.ts`
- [X] T022 Wrap generated capability hardening types in `apps/web/src/api/types.ts`

**Checkpoint**: Durable settings, mutation gate, scoped gateway/runtime seams, and shared public-safe contracts are ready.

---

## Phase 3: User Story 1 - Manage Memory And Skills End-To-End (Priority: P1)

**Goal**: A signed-in user can manage owned memory and skills end-to-end, see shared host resources as read-only, and activate owned valid capabilities only for their later sessions.

**Independent Test**: Create memory and a skill as one user, verify owner-only list/detail/update/delete/import, verify non-owner non-disclosure, verify shared read-only status, and verify owner-only later-session activation.

### Tests for User Story 1

- [X] T023 [P] [US1] Add memory CRUD owner/shared/non-owner tests in `tests/unit/test_capability_management.py`
- [X] T024 [P] [US1] Add skill create/import/delete owner/shared/non-owner tests in `tests/unit/test_capability_management.py`
- [X] T025 [P] [US1] Add memory and skill web API integration tests in `tests/integration/test_webapi_capability_management.py`
- [X] T026 [P] [US1] Add memory prompt activation tests in `tests/integration/test_capability_runtime_activation.py`
- [X] T027 [P] [US1] Add scoped skill descriptor and execution tests in `tests/integration/test_capability_runtime_activation.py`
- [X] T028 [P] [US1] Add memory and skill settings UI tests in `apps/web/src/__tests__/CapabilitySettingsView.test.tsx`

### Implementation for User Story 1

- [X] T029 [US1] Implement owner/shared memory projections in `src/loopplane/host/capabilities.py`
- [X] T030 [US1] Implement principal-scoped memory management methods in `src/loopplane/host/host.py`
- [X] T031 [US1] Implement owner-scoped memory augmentation in `src/loopplane/memory/provider.py`
- [X] T032 [US1] Implement owner/shared skill projections in `src/loopplane/host/capabilities.py`
- [X] T033 [US1] Implement principal-scoped skill create/import/delete methods in `src/loopplane/host/host.py`
- [X] T034 [US1] Activate persisted owner skills at later run/session/resume/fork boundaries in `src/loopplane/host/capability_manager.py` and `src/loopplane/host/host.py`
- [X] T035 [US1] Add memory and skill request/response views in `src/loopplane/webapi/models.py`
- [X] T036 [US1] Add principal-scoped memory and skill routes in `src/loopplane/webapi/app.py`
- [X] T037 [US1] Add memory and skill client methods in `apps/web/src/api/client.ts`
- [X] T038 [US1] Build memory management section in `apps/web/src/components/CapabilitySettingsView.tsx`
- [X] T039 [US1] Build skill management and import section in `apps/web/src/components/CapabilitySettingsView.tsx`
- [X] T040 [US1] Preserve read-only inspection behavior in `apps/web/src/components/InspectionPanel.tsx`

**Checkpoint**: User Story 1 is functional and independently testable.

---

## Phase 4: User Story 2 - Manage MCP And Workspace Contexts (Priority: P2)

**Goal**: A signed-in user can manage durable owned MCP configurations, reconnect them into owner-scoped runtime tools, manage workspace contexts, and bind an owned session to an allowed context.

**Independent Test**: Add/update/reconnect/delete an MCP configuration, verify owner-only tool availability and public-safe failure status, create/delete a workspace context, bind it to an owned session, and verify non-owner non-disclosure.

### Tests for User Story 2

- [X] T041 [P] [US2] Add MCP durability, default-deny endpoint policy, stdio refusal, approved reconnect, and public-safe failure unit tests in `tests/unit/test_capability_management.py`
- [X] T042 [P] [US2] Add managed MCP adapter replacement tests in `tests/unit/test_tool_gateway.py`
- [X] T043 [P] [US2] Add MCP owner-scoped runtime activation tests in `tests/integration/test_capability_runtime_activation.py`
- [X] T044 [P] [US2] Add workspace context and session binding tests in `tests/integration/test_webapi_context_management.py`
- [X] T045 [P] [US2] Add MCP and workspace context web API tests in `tests/integration/test_webapi_context_management.py`
- [X] T046 [P] [US2] Add MCP reconnect and context binding UI tests in `apps/web/src/__tests__/CapabilitySettingsView.test.tsx`

### Implementation for User Story 2

- [X] T047 [US2] Implement durable MCP configuration records in `src/loopplane/host/capabilities.py`
- [X] T048 [US2] Implement principal-scoped MCP management methods in `src/loopplane/host/host.py`
- [X] T049 [US2] Implement policy-approved candidate MCP reconnect and public-safe status mapping in `src/loopplane/host/capability_manager.py` and `src/loopplane/host/host.py`
- [X] T050 [US2] Integrate credential-free `MCPToolAdapter` candidates with scoped gateway replacement without exposing raw adapter failures in `src/loopplane/host/capability_manager.py`
- [X] T051 [US2] Implement durable workspace context records in `src/loopplane/host/capabilities.py`
- [X] T052 [US2] Implement principal-scoped workspace context methods in `src/loopplane/host/host.py`
- [X] T053 [US2] Move existing session context metadata writes behind a principal-checking controller method without changing checkpoint schema in `src/loopplane/controller/controller.py` and `src/loopplane/host/host.py`
- [X] T054 [US2] Add MCP and workspace request/response views in `src/loopplane/webapi/models.py`
- [X] T055 [US2] Add principal-scoped MCP and workspace routes in `src/loopplane/webapi/app.py`
- [X] T056 [US2] Add MCP, workspace, reconnect, and bind client methods in `apps/web/src/api/client.ts`
- [X] T057 [US2] Build MCP management and reconnect section in `apps/web/src/components/CapabilitySettingsView.tsx`
- [X] T058 [US2] Build workspace context and session binding section in `apps/web/src/components/CapabilitySettingsView.tsx`
- [X] T059 [US2] Keep active context visible in the chat header in `apps/web/src/App.tsx`

**Checkpoint**: User Story 2 is functional and independently testable.

---

## Phase 5: User Story 3 - Manage Schedules And Model Defaults (Priority: P3)

**Goal**: A signed-in user can manage owned schedules and choose a default model only from the host catalog without browser credential collection.

**Independent Test**: Create/open/update/disable/enable/run-now/delete a schedule, verify disabled run-now refusal, select a catalog model default, verify invalid defaults cannot be selected, and verify no credential fields render.

### Tests for User Story 3

- [X] T060 [P] [US3] Add schedule durability, owner scoping, instruction, enable/disable, runner dispatch, and safe refusal unit tests in `tests/unit/test_capability_management.py`
- [X] T061 [P] [US3] Add model default catalog-only unit tests in `tests/unit/test_capability_management.py`
- [X] T062 [P] [US3] Add schedules and model-default web API tests in `tests/integration/test_webapi_schedule_model_management.py`
- [X] T063 [P] [US3] Add schedule and model-default settings UI tests in `apps/web/src/__tests__/CapabilitySettingsView.test.tsx`
- [X] T064 [P] [US3] Add credential-boundary regression tests in `apps/web/src/__tests__/CapabilitySettingsView.test.tsx`

### Implementation for User Story 3

- [X] T065 [US3] Implement durable schedule instruction and runner status records in `src/loopplane/host/capabilities.py`
- [X] T066 [US3] Implement principal-scoped schedule CRUD, enable/disable, and injected run-now dispatch in `src/loopplane/host/capability_manager.py` and `src/loopplane/host/host.py`
- [X] T067 [US3] Implement durable model default records in `src/loopplane/host/capabilities.py`
- [X] T068 [US3] Implement catalog-only model default methods in `src/loopplane/host/host.py`
- [X] T069 [US3] Add additive schedule instruction and model-default request/response views in `src/loopplane/webapi/models.py`
- [X] T070 [US3] Add principal-scoped schedule CRUD, enable, disable, run-now, and model-default routes in `src/loopplane/webapi/app.py`
- [X] T071 [US3] Add schedule and model-default client methods in `apps/web/src/api/client.ts`
- [X] T072 [US3] Build schedule management section in `apps/web/src/components/CapabilitySettingsView.tsx`
- [X] T073 [US3] Build catalog-only model default section in `apps/web/src/components/CapabilitySettingsView.tsx`
- [X] T074 [US3] Preserve per-session model selection behavior in `apps/web/src/App.tsx`

**Checkpoint**: User Story 3 is functional and independently testable.

---

## Phase 6: Settings View Integration And Compatibility

**Purpose**: Integrate the independent settings view while preserving existing chat, inspection, and desktop compatibility.

- [X] T075 [P] Add app-shell settings toggle tests in `apps/web/src/__tests__/App.capabilities.test.tsx`
- [X] T076 [P] Add desktop compatibility smoke tests for shared capability types in `apps/desktop/src/__tests__/App.test.tsx`
- [X] T077 Add independent settings workspace toggle while keeping sidebar, header, composer, and chat state mounted in `apps/web/src/App.tsx` and `apps/web/src/components/ChatHeader.tsx`
- [X] T078 Add responsive capability settings workspace styles and English/Traditional Chinese strings in `apps/web/src/styles.css` and `apps/web/src/i18n/strings.ts`
- [X] T079 Remove mutable capabilities from inspection and keep its skills/tools/MCP/memory tabs metadata-only in `apps/web/src/components/InspectionPanel.tsx`
- [X] T080 Align generated web contract wrappers in `apps/web/src/api/types.ts`

---

## Phase 7: Polish & Cross-Cutting Validation

**Purpose**: Final cleanup, documentation, and delivery validation across all stories.

- [X] T081 [P] Update 076 validation notes in `specs/076-web-capability-management-hardening/quickstart.md`
- [X] T082 [P] Update API reference for capability hardening in `docs/api-reference.md`
- [X] T083 Run backend gates from `specs/076-web-capability-management-hardening/quickstart.md`
- [X] T084 Run web gates from `specs/076-web-capability-management-hardening/quickstart.md`
- [X] T085 Run desktop compatibility gates from `specs/076-web-capability-management-hardening/quickstart.md`
- [X] T086 Run final public-safety gates from `specs/076-web-capability-management-hardening/quickstart.md`
- [X] T087 Update final roadmap status for 076 in `docs/loopplane-agent-board.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2; MVP scope.
- **Phase 4 US2**: Depends on Phase 2; can run after or alongside US1 once scoped gateway seams exist.
- **Phase 5 US3**: Depends on Phase 2; can run after or alongside US1/US2.
- **Phase 6 Integration**: Depends on implemented story surfaces intended for release.
- **Phase 7 Polish**: Depends on all released story phases.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 or US3 after foundational seams.
- **US2 (P2)**: No dependency on US1 after foundational seams, but shares scoped gateway/runtime activation infrastructure.
- **US3 (P3)**: No dependency on US1 or US2 after foundational seams.

### Parallel Opportunities

- T002-T005 can run in parallel after T001.
- T006-T011 can run in parallel before foundational implementation.
- T012-T022 are mostly sequential where later tasks depend on shared models and seams.
- Tests within each user story can run in parallel.
- US1, US2, and US3 implementation can proceed in parallel after Phase 2 if developers avoid editing the same files at the same time.
- T081-T082 can run in parallel with final validation gates.

## Implementation Strategy

### MVP First

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational durable settings, mutation gate, scoped gateway, and runtime seams.
3. Complete Phase 3 US1 memory and skills.
4. Validate US1 independently before expanding to MCP, contexts, schedules, and defaults.

### Incremental Delivery

1. Foundation ready: durable store, mutation gate, public-safe operations, scoped runtime seams.
2. US1: memory and skills end-to-end.
3. US2: MCP reconnect and workspace context binding.
4. US3: schedules and catalog-only model defaults.
5. Integration: independent settings view and compatibility validation.

### Notes

- Existing 075 endpoints must remain additive-compatible.
- Gateway changes must remain inside the Tool Gateway boundary and be covered by boundary tests.
- Browser UI must never render provider credential, API key, secret, token, or MCP auth token fields.
- Stop before implementation if a task requires event schema changes, checkpoint schema changes beyond existing metadata compatibility, new dependencies, or outward breaking API changes.

## Phase 8: Convergence

- [X] T088 Type memory and skill delete client responses as `CapabilityOperationResult`, surface public-safe stale-gate refusals in the independent settings view, and add focused Vitest coverage in `apps/web/src/api/client.ts`, `apps/web/src/components/CapabilitySettingsView.tsx`, and `apps/web/src/__tests__/CapabilitySettingsView.test.tsx` per FR-018 and `contracts/settings-ui.md` Mutation Gate (partial)
