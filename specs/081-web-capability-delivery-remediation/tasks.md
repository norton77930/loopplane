---

description: "Implementation tasks for 081 Web Capability Delivery Remediation"
---

# Tasks: Web Capability Delivery Remediation

**Input**: Design documents from `specs/081-web-capability-delivery-remediation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Tests are required and must be written red-first for each behavior slice.

**Organization**: Tasks are grouped by user story. Unit 076 and 080 spec/tasks are frozen; all remediation traceability lives here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it edits different files and does not depend on an incomplete task
- **[Story]**: Maps to a user story from `spec.md`
- Every task names its primary file path

## Phase 1: Setup and Working-Tree Protection

**Purpose**: Establish 081 as the active remediation unit without losing or misclassifying existing 076/080/local work.

- [x] T001 Record the 076/080/081/local ownership inventory and mixed-hunk cautions in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T002 Add an in-progress 081 roadmap row, block 077, and align the active-feature text with `.specify/feature.json` in `docs/loopplane-agent-board.md`
- [x] T003 Review `AGENTS.md` and `CLAUDE.md` managed Spec Kit blocks for the 081 plan pointer without changing non-managed rules
- [x] T004 [P] Review `specs/081-web-capability-delivery-remediation/checklists/requirements.md` and `checklists/security-readiness.md`; resolve any requirement-quality gap in 081 artifacts before code changes

**Validation**: T003–T004 confirm the active pointer, requirement quality, and frozen-history boundaries before production edits.

**Rollback**: Revert only the 081 pointer/board documentation hunks to their pre-081 values; do not delete, reset, stash, or rewrite any 076/080/local file.

**Checkpoint**: 081 is the documented active unit; 076/080 artifacts and `.superpowers/**` remain untouched.

---

## Phase 2: Foundational Test Seams

**Purpose**: Prepare shared fakes and contract expectations used by multiple user stories.

**⚠️ CRITICAL**: Complete before story implementation.

- [x] T005 Add reusable principal-aware allowed-context provider fixtures and invalid/collision cases in `tests/unit/test_capability_management.py`
- [x] T006 [P] Add reusable blocking managed-adapter/lease fixtures for manager lifecycle scenarios in `tests/integration/test_capability_runtime_activation.py`
- [x] T007 [P] Add shared-capability safe-detail and action fixtures in `apps/web/src/__tests__/capabilitySettingsHelpers.ts`

**Validation**: Import/collection of the new fixtures succeeds, while the story behavior tests remain red until their production slices are implemented.

**Rollback**: Remove only the newly added 081 fixtures and helper module if they cannot remain isolated; no runtime or persisted state is involved.

**Checkpoint**: Red-test fixtures exist without changing production behavior.

---

## Phase 3: User Story 1 — Manage Network MCP Safely (Priority: P1) 🎯 MVP

**Goal**: Reject credential-bearing or structurally invalid browser-managed endpoints and retire stale owner-scoped adapters immediately without interrupting in-flight calls.

**Independent Test**: Save/reconnect a valid approved endpoint; reject every unsafe endpoint before persistence; then update, delete, and force reconnect failure while proving new resolution is removed, an in-flight call completes, shutdown happens once, and another principal is unaffected.

### Red Tests for User Story 1

- [x] T008 [P] [US1] Add table-driven manager endpoint-admission and public-safe result tests in `tests/unit/test_capability_management.py`
- [x] T009 [P] [US1] Add direct persistence-bypass rejection and legacy-invalid-record tests in `tests/unit/test_capability_settings_store.py`
- [x] T010 [P] [US1] Add HTTP contract tests for unsafe URL/stdio refusal without value disclosure in `tests/contract/test_web_capability_management_contract.py`
- [x] T011 [P] [US1] Add active-adapter red tests for update, delete, structural invalidity, policy denial, connection/candidate failure, state-write failure, registry-replacement failure, and successful reconnect in `tests/integration/test_capability_runtime_activation.py`; every terminal path must cover immediate new-resolution removal, in-flight completion, exactly-once shutdown, durable/runtime consistency, and cross-principal isolation
- [x] T012 [P] [US1] Add host/API caller tests that require awaiting managed-MCP upsert/delete while preserving HTTP response envelopes, plus the independent mutation-off/runtime-on, mutation-on/runtime-off, both-off, and both-on MCP mutation/resolution matrix, in `tests/integration/test_webapi_context_management.py`

### Implementation for User Story 1

- [x] T013 [US1] Implement side-effect-free managed-MCP structural endpoint validation in `src/loopplane/host/capabilities.py`
- [x] T014 [US1] Apply defense-in-depth MCP record validation before writes while retaining tolerant legacy loads in `src/loopplane/host/capability_store.py`
- [x] T015 [US1] Convert managed-MCP upsert/delete to async, add one private deactivation helper, and retire adapters on all terminal failure states in `src/loopplane/host/capability_manager.py`
- [x] T016 [US1] Convert public managed-MCP upsert/delete forwarding methods to async in `src/loopplane/host/host.py`
- [x] T017 [US1] Await the approved async host mutations without changing route paths or JSON envelopes in `src/loopplane/webapi/app.py`
- [x] T018 [US1] Update all Python callers and tests for the approved async host API in `tests/unit/test_capability_management.py`, `tests/integration/test_webapi_context_management.py`, and `tests/integration/test_capability_runtime_activation.py`
- [x] T019 [US1] Ensure principal activation treats every non-connected managed-MCP status as inactive in `src/loopplane/host/capability_manager.py`
- [x] T020 [US1] Run the US1 focused tests from `specs/081-web-capability-delivery-remediation/quickstart.md` and record literal red/green results in that file

**Validation**: T008–T012 fail for the intended missing behavior before T013–T019 and pass afterward; T020 records both observations without replacing failures with reruns.

**Rollback**: Disable capability mutations and runtime activation independently, reject invalid legacy records as non-connectable, and revert only the 081 manager/host/Web API lifecycle hunks if the runtime slice must be withdrawn.

**Checkpoint**: US1 independently satisfies endpoint admission, public safety, immediate retirement, lease completion, exactly-once shutdown, and cross-principal isolation.

---

## Phase 4: User Story 2 — Bind an Allowed Workspace Context (Priority: P2)

**Goal**: Project host-approved contexts to the correct principal, fail closed on ambiguity, and bind them only to sessions owned by that principal.

**Independent Test**: Configure distinct allowed context sets for two principals and exercise provider absence, success, provider failure, duplicate identity, owner/provider collision, detail, bind, and non-owner session flows.

### Red Tests for User Story 2

- [x] T021 [P] [US2] Add config default/coercion/callable-validation tests for the optional allowed-context provider and prove provider absence preserves byte-identical owner-only behavior in `tests/unit/test_capability_management.py`
- [x] T022 [P] [US2] Add provider absence, two-principal visibility, failure, duplicate, collision, and safe-projection tests in `tests/unit/test_capability_management.py`
- [x] T023 [P] [US2] Add allowed-context list/detail/bind and non-disclosing session/context tests across mutation-off/runtime-on, mutation-on/runtime-off, both-off, and both-on states in `tests/integration/test_webapi_context_management.py`; read-only Open must remain available and Bind must depend only on its existing projected-action/mutation authority

### Implementation for User Story 2

- [x] T024 [US2] Define the principal-aware allowed workspace context provider Protocol in `src/loopplane/host/capabilities.py`
- [x] T025 [US2] Add the default-None provider field, mapping coercion, and callable validation in `src/loopplane/host/config.py`
- [x] T026 [US2] Rebuild allowed-context safe projections and implement fail-closed merge/get collision logic in `src/loopplane/host/capability_manager.py`
- [x] T027 [US2] Preserve existing session ownership and non-disclosing bind behavior while accepting allowed contexts in `src/loopplane/host/host.py`
- [x] T028 [US2] Add the approved provider surface and async managed-MCP host signatures to public API coverage in `tests/contract/test_api_reference.py`
- [x] T029 [US2] Run the US2 focused tests and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`

**Validation**: T021–T023 fail for the absent provider/gate behavior before T024–T028 and pass afterward, including the two-principal and four-state gate matrices.

**Rollback**: Set the optional provider back to `None` and revert only the 081 provider/config/projection hunks; owned durable contexts and existing session metadata remain authoritative and require no migration.

**Checkpoint**: US2 independently provides optional allowed contexts with owner-only fallback, deterministic collision refusal, and principal/session non-disclosure.

---

## Phase 5: User Story 3 — Inspect Shared Capabilities Without Mutation (Priority: P2)

**Goal**: Provide action-driven safe read-only details for all shared capability types and remove the legacy mutable settings surface.

**Independent Test**: Open shared memory, skill, MCP, and allowed context details; verify only safe metadata and projected actions are available, owner-only values are absent from presentation, and no legacy settings route/import remains.

### Red Tests for User Story 3

- [x] T030 [P] [US3] Add backend tests for the exact shared memory/skill/MCP/context allow-lists, 160-code-point memory truncation, empty shape-preserving owner-only strings, nested-sensitive-field exclusion, and safe projected actions in `tests/unit/test_capability_management.py`
- [x] T031 [P] [US3] Add API non-disclosure and over-limit shared-memory projection tests in `tests/integration/test_webapi_capability_management.py` and `tests/integration/test_webapi_context_management.py`
- [x] T032 [P] [US3] Add action-driven read-only detail, bind, keyboard/focus, no-mutation-control, and mutation-disabled Open-availability tests in `apps/web/src/__tests__/CapabilitySettingsView.test.tsx`
- [x] T033 [P] [US3] Add a structure regression that forbids the legacy settings component/import path in `apps/web/src/__tests__/CapabilitySettingsStructure.test.ts`

### Implementation for User Story 3

- [x] T034 [US3] Sanitize shared memory, skill, and MCP detail projections while preserving owner detail shapes in `src/loopplane/host/capability_manager.py`
- [x] T035 [P] [US3] Create the reusable accessible read-only detail component in `apps/web/src/components/settings/CapabilityDetail.tsx`
- [x] T036 [US3] Replace scope-special-cased interactions with projected-action handling in `apps/web/src/components/settings/MemorySettings.tsx` and `apps/web/src/components/settings/SkillSettings.tsx`
- [x] T037 [US3] Replace scope-special-cased interactions with projected-action handling in `apps/web/src/components/settings/McpSettings.tsx` and `apps/web/src/components/settings/WorkspaceSettings.tsx`
- [x] T038 [P] [US3] Add bilingual detail labels, statuses, and failure text in `apps/web/src/i18n/strings.ts`
- [x] T039 [P] [US3] Add responsive, forced-color, reduced-motion, and focus styles for read-only details in `apps/web/src/styles.css`
- [x] T040 [US3] Remove `apps/web/src/components/CapabilitySettings.tsx` and its dedicated legacy test `apps/web/src/__tests__/CapabilitySettings.test.tsx`, then update remaining imports/fixtures
- [x] T041 [US3] Run the US3 backend/Web focused tests and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`

**Validation**: T030–T033 fail for the unsafe/legacy behavior before T034–T040 and pass afterward; focused Web checks include both locales, keyboard/focus, mutation-disabled Open, and safe Bind presentation.

**Rollback**: Revert the presentation-only 081 detail component/settings/i18n/style hunks independently and restore the legacy file only if required for a source-level rollback; backend owner detail and persisted state require no migration.

**Checkpoint**: US3 independently exposes safe shared details through one supported Settings experience with action-driven authorization and accessibility coverage.

---

## Phase 6: User Story 4 — Trust the Delivered Capability Release (Priority: P3)

**Goal**: Produce fresh evidence, synchronize status/release/API documents, and leave 077 blocked until 081 is genuinely Verified.

**Independent Test**: Run every required gate from a fresh dependency state, execute the Chromium matrix, inspect tracked/staged/untracked candidates, and compare the pointer, board, CHANGELOG, API reference, and 081 validation record.

### Verification and Delivery Tasks for User Story 4

- [x] T042 [P] [US4] Run fresh focused Python capability/Gateway/context/contract suites and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T043 [US4] Run `uv sync --locked`, Ruff format/check, strict mypy, full pytest with isolated basetemp, and `uv build`; record literal failures/skips/results in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T044 [P] [US4] Run Web npm ci/typecheck/full Vitest/production build and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T045 [P] [US4] Run Desktop npm ci/typecheck/full Vitest and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T046 [US4] Execute the fresh Chromium 1440/1024/768/375 plus 640/320 reflow, en/zh-TW, light/dark, keyboard/focus, reduced-motion, forced-color matrix and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T047 [US4] Run whitespace, architecture-boundary, Spec Kit alignment, openspec exclusion, tracked/staged/untracked public-safety scans and record literal results in `specs/081-web-capability-delivery-remediation/quickstart.md`
- [x] T048 [US4] After T042–T047 are green, update approved async managed-MCP methods and allowed-context provider documentation in `docs/api-reference.md`
- [x] T049 [US4] After T042–T047 are green, add accurate 076, 080, and 081 entries under `[Unreleased]` in `CHANGELOG.md`
- [x] T050 [US4] Re-run the relevant documentation/API/public-safety contract tests after T048–T049 synchronization and append the literal results to `specs/081-web-capability-delivery-remediation/quickstart.md`

**Validation**: T042–T047 provide fresh implementation/browser evidence, T048–T049 synchronize documentation, and T050 proves the synchronized state before final ownership/artifact review.

**Rollback**: Restore CHANGELOG/API/feature-pointer documentation to the last internally consistent in-progress state; if a product gate regresses, keep 081 in-progress and 077 blocked.

**Checkpoint**: US4 supplies fresh, reproducible implementation, browser, and synchronized-documentation evidence for the final review phase.

---

## Phase 7: Polish and Cross-Cutting Review

**Purpose**: Final traceability, simplification, and delivery-safety review.

- [x] T051 [P] Review every 081 requirement against `specs/081-web-capability-delivery-remediation/checklists/security-readiness.md` and annotate unresolved gaps without changing 076/080 frozen artifacts
- [x] T052 Review the final changed-file/hunk inventory against 076/080/081/local ownership and prove `.superpowers/**`, raw `openspec/**`, QA artifacts, and unknown user files are excluded
- [x] T053 Run `/speckit-analyze` again after implementation and resolve all blocking artifact inconsistencies in `specs/081-web-capability-delivery-remediation/`
- [x] T054 Only after T050–T053 and T055 are green/no-blocker, transactionally mark this task complete and update `docs/loopplane-agent-board.md` plus `.specify/feature.json` for the 081 Verified/077-next transition, then immediately re-run final diff, ownership, public-safety, Spec Kit, and documentation-consistency checks covering those exact new hunks; append the literal post-write result to `quickstart.md` and retain the Verified transition only if every check remains green, otherwise restore this checkbox, 081 in-progress, and the 081 pointer while keeping 077 blocked
- [x] T055 Before T054, produce the pre-transition completion record with changed-file scope, literal verification evidence, approved human gate, known limitations, rollback, and explicit confirmation that no commit/push/release occurred; T054 owns the final transition and appends its literal post-write checks to that record

**Validation**: T051–T053 leave no unresolved checklist, ownership, public-safety, or analyze finding; T054 is an atomic candidate-write/post-write-check transition and is the sole task allowed to retain 081 as Verified; T055 cites only evidence actually produced in this run.

**Rollback**: If final review finds drift, reopen the affected story phase, revert only its owned 081 hunks, restore the last consistent documentation state, and keep 081 in-progress until the phase gates are rerun. Any T054 post-write failure must restore the prior board/pointer state before the task exits.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: starts immediately; blocks all implementation
- **Phase 2 Foundational**: depends on Phase 1; blocks all stories
- **US1 (Phase 3)**: depends on Phase 2 and is the MVP/security-critical slice
- **US2 (Phase 4)**: depends on Phase 2; may run in parallel with US1 after shared fixtures exist, but both edit `capability_manager.py`, so production edits should be serialized
- **US3 (Phase 5)**: backend projection tasks depend on US2 context projection; Web tests/components can begin after Phase 2 fixtures
- **US4 (Phase 6)**: depends on US1–US3 completion
- **Phase 7**: depends on all stories and documentation synchronization

### User Story Dependencies

- **US1**: no dependency on other user stories; required before any Verified claim
- **US2**: independent host-provider slice, but shares manager/config surfaces with US1
- **US3**: uses US2 allowed-context actions and US1 public-safe MCP status; shared UI component remains independently testable
- **US4**: integrates all prior stories; final T054 is the only task allowed to mark 081 Verified and depends on green/no-blocker T042–T053 evidence

### Within Each Story

1. Write the listed tests first and observe expected failures.
2. Implement the smallest production change that turns the focused tests green.
3. Run the story-focused suite and record literal results.
4. Do not claim full completion from focused tests.

### Parallel Opportunities

- T005–T007 use separate test files and can run in parallel.
- T008–T012 can be authored in parallel before production changes.
- T021–T023 can be authored in parallel.
- T030–T033 can be authored in parallel.
- T035, T038, and T039 use different frontend files and can run in parallel after the shared-detail contract is stable.
- T042, T044, and T045 may run in parallel only after all code changes stop; do **not** run full pytest concurrently with multi-agent workflows.

---

## Parallel Example: User Story 1

```text
Task: "Add manager endpoint-admission tests in tests/unit/test_capability_management.py"
Task: "Add persistence-bypass tests in tests/unit/test_capability_settings_store.py"
Task: "Add HTTP public-safety tests in tests/contract/test_web_capability_management_contract.py"
Task: "Add lifecycle lease tests in tests/integration/test_capability_runtime_activation.py"
```

## Parallel Example: User Story 3

```text
Task: "Create read-only detail component in apps/web/src/components/settings/CapabilityDetail.tsx"
Task: "Add bilingual detail strings in apps/web/src/i18n/strings.ts"
Task: "Add detail accessibility styles in apps/web/src/styles.css"
```

---

## Implementation Strategy

### MVP First — User Story 1

1. Complete Setup and Foundational phases.
2. Write all US1 red tests.
3. Implement structural endpoint admission and lease-safe retirement using existing Gateway primitives.
4. Validate US1 independently before allowed-context or UI work.

### Incremental Delivery

1. US1 closes the highest-risk MCP security/lifecycle gap.
2. US2 fulfills owned-or-allowed context behavior with default-None fallback.
3. US3 provides safe action-driven shared details and removes the legacy surface.
4. US4 supplies fresh full evidence and documentation convergence.

### Safety Rules

- Do not edit `specs/076-web-capability-management-hardening/{spec,plan,tasks}.md` or `specs/080-web-frontend-visual-refactor/{spec,plan,tasks}.md`.
- Do not stage or modify `.superpowers/**` or raw `openspec/**`.
- Do not use destructive cleanup, blanket staging, commit, push, tag, release, or deployment operations without separate authorization.
- If implementation requires an unapproved HTTP schema, persistence schema, dependency, default, Gateway SPI/stage-order, Event Bus, or checkpoint change, stop for human approval.
