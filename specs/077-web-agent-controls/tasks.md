---

description: "Implementation tasks for 077 Web Agent Controls"
---

# Tasks: Web Agent Controls

**Input**: Design documents from `specs/077-web-agent-controls/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Tests are required and must be written red-first for every behavior slice.

**Organization**: Tasks are grouped by user story. Completed 076/080/081 spec/plan/tasks are frozen; all 077 behavior, evidence, rollback, and transition traceability lives here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it edits different files and does not depend on an incomplete task
- **[Story]**: Maps to a user story from `spec.md`
- Every task names its primary file path

## Phase 1: Setup, Human Gate, And Working-Tree Protection

**Purpose**: Establish the only authorized 077 scope and block implementation until the outward-contract decision is explicit.

- [x] T001 Obtain explicit maintainer approval or rejection for the safe projection including `active_run`/`last_accepted_run`, optional per-run mode input, bounded non-image upload handoff/`read_upload` fallback, and generated artifacts in `contracts/agent-control-projection.md` plus `contracts/cost-context-and-references.md`; record the exact decision in `specs/077-web-agent-controls/plan.md` and `quickstart.md`, and start no source/test/generated-type task before approval
- [x] T002 Refresh the complete inventory, 077 delivery-candidate classification, mixed-hunk cautions, and nine frozen hashes in `specs/077-web-agent-controls/quickstart.md`
- [x] T003 [P] Review all items in `specs/077-web-agent-controls/checklists/requirements.md` and `checklists/agent-controls-readiness.md`; reopen any item whose cited requirement drifted
- [x] T004 [P] Record inbound-import/boundary cautions for `context.py`, `host/assembly.py`, `webapi/app.py`, Gateway/Event Bus/checkpoint/default/dependency invariants, and current tests in `specs/077-web-agent-controls/quickstart.md`

**Validation**: T001 contains an explicit decision; T002–T004 prove the current tree, frozen history, requirements, and load-bearing boundaries before any implementation edit.

**Rollback**: Revert only 077 setup/artifact hunks and restore the managed active-plan pointer; never reset, clean, stash, rewrite, or delete prior-unit/local files.

**Checkpoint**: 077 remains specification-only until T001 is approved. Rejection keeps all later tasks blocked and requires returning to the spec/plan rather than weakening the contract.

---

## Phase 2: Foundational Red-Test Seams

**Purpose**: Create reusable principal, runtime, transport, and Web fixtures after the gate is approved, without changing production behavior.

**⚠️ CRITICAL**: T001 approval and Phase 1 completion block this phase and every user story.

- [x] T005 Add reusable safe-projection, invalid-mode, budget-state, and two-principal fixtures in `tests/unit/test_agent_controls.py`
- [x] T006 [P] Add reusable per-run fake model/tool/question fixtures and checkpoint-rebuild assertions in `tests/integration/test_webapi_agent_controls.py`
- [x] T007 [P] Add Web agent-control/cost/context/reference fixtures and request spies in `apps/web/src/__tests__/agentControlsHelpers.ts`
- [x] T008 [P] Add generated-artifact fixture expectations for the approved route and input field in `tests/contract/test_web_agent_controls_contract.py`

**Validation**: New fixtures import/collect, while all behavior assertions added in later story phases remain red until their production slices are implemented.

**Rollback**: Remove only isolated 077 fixture/helper additions; no runtime, transport, or persisted state has changed.

**Checkpoint**: Shared red-test infrastructure exists and principal/request/effect counters can prove non-disclosure and zero hidden work.

---

## Phase 3: User Story 1 — Control Plan And Permission Posture Safely (Priority: P1) 🎯 MVP

**Goal**: Project authoritative safe posture and apply one host-approved mode to one accepted run while preserving deny-wins and the existing plan-exit question path.

**Independent Test**: For an owned session, read safe posture, submit default/allowed/plan/invalid/bypass modes over applicable transports, exercise exit approve/reject, and prove per-run reset, no checkpoint persistence, no policy bypass, and principal isolation.

### Red Tests for User Story 1

- [x] T009 [P] [US1] Add safe projection/default-empty/duplicate/unknown/`bypassPermissions` rejection, raw-rule/config exclusion, authoritative active/last posture, and `read_upload`-driven action tests in `tests/unit/test_agent_controls.py`
- [x] T010 [P] [US1] Add mode-aware deny/ask/allow, explicit-deny precedence, default byte-identity, and context-reading plan-policy tests in `tests/unit/test_permission_modes.py`
- [x] T011 [P] [US1] Add controller tests for one-run selection, plan-state initialization, authoritative in-memory active/last-accepted posture, settled transition, and absence from rebuilt session/checkpoint state in `tests/unit/test_controller_core.py`
- [x] T012 [P] [US1] Add approved request/response shape, generated-type drift, no-value-echo, and non-owner 404 tests in `tests/contract/test_web_agent_controls_contract.py`
- [x] T013 [P] [US1] Add REST/session-turn/live-submit integration tests for accepted/default/plan/invalid modes, active/fast-settled authoritative projection refresh, host-restart unavailability, and two-principal isolation in `tests/integration/test_webapi_agent_controls.py`
- [x] T014 [P] [US1] Add existing question-roundtrip tests for plan exit approve/reject/stale/disconnect/non-owner behavior without a direct exit mutation in `tests/integration/test_webapi_agent_controls.py`
- [x] T015 [P] [US1] Add Settings category, at-most-two-action category reachability, one-action chat return, safe posture, read-only fallback, mode draft/authoritative active-or-last/reset, and no-direct-plan-exit tests in `apps/web/src/__tests__/AgentControlsSettings.test.tsx`
- [x] T016 [P] [US1] Add App/transport tests that include the mode only on explicit send, label it authoritative only after `active_run`/`last_accepted_run` projection refresh, and preserve chat/draft/dialog state in `apps/web/src/__tests__/App.agentControls.test.tsx`

### Implementation for User Story 1

- [x] T017 [US1] Define safe projection/value objects, authoritative non-durable active/last posture, mode/tool-action allow-list validation, public-safe failures, and default-empty behavior in `src/loopplane/host/agent_controls.py`
- [x] T018 [US1] Add the default-empty host-approved browser mode configuration and validation that excludes approval-bypassing modes in `src/loopplane/host/config.py`
- [x] T019 [US1] Add optional per-run permission-mode metadata without changing TYPE_CHECKING/tool boundaries in `src/loopplane/context.py`
- [x] T020 [US1] Extend existing named-mode resolution with a precompiled context-reading per-run policy that preserves explicit deny, safe-failure, and existing stage ordering in `src/loopplane/governance/modes.py`
- [x] T021 [US1] Accept/stamp one-run mode, initialize the existing `PlanModeState`, and maintain display-only active/last-accepted posture in live controller session memory in `src/loopplane/controller/controller.py`
- [x] T022 [US1] Wire the default-off safe projection and mode-aware existing decider composition without new Gateway stage/import changes in `src/loopplane/host/assembly.py`
- [x] T023 [US1] Add public host projection for safe defaults/actions plus live active/last posture and per-run drive forwarding with ownership/default behavior intact in `src/loopplane/host/host.py`
- [x] T024 [US1] Add the approved Pydantic projection models including active/last accepted posture and optional run input field without sensitive values in `src/loopplane/webapi/models.py`
- [x] T025 [US1] Add the approved owner-scoped route and forward the validated optional mode across run/session-turn/live-submit paths in `src/loopplane/webapi/app.py`
- [x] T026 [US1] Regenerate/update backend-owned contract artifacts for the approved additions in `src/loopplane/webapi/contract_types.py` and `apps/web/src/api/generated.ts`
- [x] T027 [US1] Add typed client/transport support for projection and optional per-run mode in `apps/web/src/api/types.ts` and `apps/web/src/api/client.ts`
- [x] T028 [US1] Add `AgentControlsSettings` as a first-level Settings category and connect mode/status state through `apps/web/src/components/settings/AgentControlsSettings.tsx` and `apps/web/src/components/CapabilitySettingsView.tsx`
- [x] T029 [US1] Connect draft/accepted/reset mode state to explicit send while preserving existing question/approval dialogs in `apps/web/src/App.tsx` and `apps/web/src/components/Composer.tsx`
- [x] T030 [P] [US1] Add en/zh-TW mode, plan, read-only, pending, rejected, and public-safe failure strings in `apps/web/src/i18n/strings.ts`
- [x] T031 [P] [US1] Add responsive/focus/forced-color/reduced-motion styles for the Agent Controls category and per-run selector in `apps/web/src/styles.css`
- [x] T032 [US1] Run the US1 focused Python/Web tests from `specs/077-web-agent-controls/quickstart.md` and record literal red/green results in that file

**Validation**: T009–T016 fail for the intended missing behavior before T017–T031 and pass afterward. Omitted mode is byte-identical; selected mode affects one run only; no direct plan exit, checkpoint write, event change, Gateway bypass, or cross-principal disclosure exists.

**Rollback**: Empty/disable the browser mode allow-list first, remove the approved route/input field and 077 context/decider/UI slices, and regenerate prior contract artifacts. Existing host-config mode, plan policy, questions, sessions, and checkpoints remain authoritative.

**Checkpoint**: US1 is independently usable as a safe read-only posture view plus optional per-run plan/permission choice.

---

## Phase 4: User Story 2 — Understand Cost And Budget Status Honestly (Priority: P1)

**Goal**: Replace authoritative-looking local estimates with owner-scoped server values and safe guard posture that distinguishes zero, unknown, unavailable, partial, and unpriced states.

**Independent Test**: Exercise priced known-zero/nonzero, unpriced, partial, unavailable ledger, disabled/within/near/exceeded guards, pre-turn refusal, refresh failure, and two-principal monthly/session isolation.

### Red Tests for User Story 2

- [x] T033 [P] [US2] Add safe budget-posture calculation tests for disabled/within/80%-near/exceeded/unknown and no raw cap/rate/ledger fields in `tests/unit/test_budget_caps.py`
- [x] T034 [P] [US2] Add agent-control projection tests for tracking/pricing/guard combinations and failure containment in `tests/unit/test_agent_controls.py`
- [x] T035 [P] [US2] Add owner-scoped session/monthly cost plus projection integration tests for known-zero/null/unavailable/unpriced/partial and two principals in `tests/integration/test_webapi_agent_controls.py`
- [x] T036 [P] [US2] Add Web client/view tests for exact decimal values, separate scopes, refresh timing, truthful fallback, and `budget-exceeded` guidance in `apps/web/src/__tests__/AgentControlsCost.test.tsx`
- [x] T037 [P] [US2] Add regression tests preventing the bundled local estimate from being presented as authoritative in `apps/web/src/__tests__/ChatHeader.test.tsx`

### Implementation for User Story 2

- [x] T038 [US2] Add a public-safe, fail-soft budget posture read over existing counters/ledger without changing enforcement in `src/loopplane/budget/__init__.py`
- [x] T039 [US2] Compose session/principal budget posture into the existing safe projection in `src/loopplane/host/agent_controls.py` and `src/loopplane/host/assembly.py`
- [x] T040 [US2] Add existing session/monthly cost response types and client methods without changing their routes in `apps/web/src/api/types.ts` and `apps/web/src/api/client.ts`
- [x] T041 [US2] Render authoritative session/month cost, pricing/tracking states, guard posture, refresh, and public-safe failures in `apps/web/src/components/settings/AgentControlsSettings.tsx`
- [x] T042 [US2] Replace or clearly demote the bundled local estimate in `apps/web/src/components/ChatHeader.tsx` and refresh authoritative values from `apps/web/src/App.tsx`
- [x] T043 [P] [US2] Add en/zh-TW cost, pricing, guard, refusal, unavailable, and unpriced strings in `apps/web/src/i18n/strings.ts`
- [x] T044 [US2] Run the US2 focused Python/Web tests and record literal results in `specs/077-web-agent-controls/quickstart.md`

**Validation**: T033–T037 fail before T038–T043 and pass afterward. No missing/unpriced value renders as zero; existing BudgetChecker/pre-turn behavior remains the sole enforcement authority.

**Rollback**: Remove only safe posture reads and Web authoritative-cost presentation; retain existing accounting, ledger, guards, cost routes, and termination semantics. Do not restore an unlabeled local estimate as authoritative.

**Checkpoint**: US2 independently provides honest owner-scoped cost/guard visibility with no accounting or enforcement rewrite.

---

## Phase 5: User Story 3 — Work With Session Context And Safe References (Priority: P2)

**Goal**: Bind existing owner/allowed contexts and use only current-session opaque upload/artifact references without browser raw-content access, new indexing, or sharing.

**Independent Test**: Bind owner/allowed contexts, submit structured uploads, preserve tool artifact references, attach an opaque reference to editable input, and prove missing/stale/non-owner/private-content cases remain safe.

### Red Tests for User Story 3

- [x] T045 [P] [US3] Add Web transport tests proving completed uploads use the existing structured `uploads` field and frontend code never concatenates reference control syntax into user prompts in `apps/web/src/__tests__/Attachments.test.tsx`
- [x] T046 [P] [US3] Add reducer/type tests that preserve current-session `artifact_reference` and clear it on session isolation boundaries in `apps/web/src/__tests__/chatReducer.test.ts`
- [x] T047 [P] [US3] Add ToolCard/reference tests for metadata-only display, attach-to-editable-input, long labels, and absence of raw-open/download/execute actions in `apps/web/src/__tests__/ToolCard.test.tsx`
- [x] T048 [P] [US3] Add Settings context tests for owner/allowed bind actions, stale authorization, read-only fallback, and non-owner non-disclosure in `apps/web/src/__tests__/AgentControlsReferences.test.tsx`
- [x] T049 [P] [US3] Add contract/integration regressions for exact 8-item/256-byte constant-key non-image handoff, image exclusion, principal ownership, projected `read_upload` action, stale/unavailable pre-model rejection, WebAPI no-dispatch, unchanged context/artifact ownership, and no raw artifact-content calls in `tests/contract/test_web_agent_controls_contract.py` and `tests/integration/test_webapi_agent_controls.py`

### Implementation for User Story 3

- [x] T050 [US3] Extend transport-neutral submit options to carry completed upload references through `apps/web/src/api/types.ts` and `apps/web/src/api/client.ts`
- [x] T051 [US3] Preserve upload references in draft state, submit/remove/retry without frontend prompt concatenation, validate host-projected `read_upload` availability at submission, and assemble the approved exact bounded non-image metadata only after existing owner validation—without WebAPI tool resolve/authorize/invoke—in `apps/web/src/App.tsx`, `apps/web/src/components/Attachments.tsx`, `src/loopplane/webapi/app.py`, and `src/loopplane/webapi/multimodal.py`
- [x] T052 [US3] Preserve safe artifact-reference metadata in transport-neutral chat state in `apps/web/src/state/chat.ts`
- [x] T053 [US3] Add metadata-only artifact reference affordances that populate editable input and never fetch raw content in `apps/web/src/components/ToolCard.tsx`
- [x] T054 [US3] Integrate current bound context, existing projected bind actions, and current-session safe references into `apps/web/src/components/settings/AgentControlsSettings.tsx`
- [x] T055 [P] [US3] Add en/zh-TW context/reference/status/action/failure strings in `apps/web/src/i18n/strings.ts`
- [x] T056 [P] [US3] Add wrapping, status, focus, narrow-layout, forced-color, and reduced-motion styles for references in `apps/web/src/styles.css`
- [x] T057 [US3] Run the US3 focused Web/backend ownership regressions and record literal results in `specs/077-web-agent-controls/quickstart.md`

**Validation**: T045–T049 fail before T050–T056 and pass afterward. Context ownership/actions remain authoritative; only structured/opaque references cross the controls; no raw browser content, path, index, sharing, persistence, or hidden send is added.

**Rollback**: Remove 077 reference/context presentation and transport-state additions. Existing context bindings, upload store, artifact store, messages, and owner checks require no migration or rollback.

**Checkpoint**: US3 independently exposes safe context/reference workflow without becoming a browser file system or content viewer.

---

## Phase 6: User Story 4 — Continue Work With Deterministic Suggestions (Priority: P3)

**Goal**: Offer up to three localized visible-state suggestions that only populate editable input and generate no hidden work.

**Independent Test**: Derive suggestions for empty/completed/budget-blocked/context/attachment/tool outcomes, then select/edit/dismiss/send while proving zero derivation requests/model/tool calls and ordinary send semantics.

### Red Tests for User Story 4

- [x] T058 [P] [US4] Add table-driven pure derivation tests for eligibility, priority, stale-state invalidation, locale/session changes, and three-item cap in `apps/web/src/__tests__/followUpSuggestions.test.ts`
- [x] T059 [P] [US4] Add interaction tests for accessible group, keyboard selection, composer focus, edit/dismiss, no automatic send, and pending-dialog coexistence in `apps/web/src/__tests__/FollowUpSuggestions.test.tsx`
- [x] T060 [P] [US4] Add App request-spy tests proving derivation/selection causes zero fetch and explicit send still uses normal mode/upload/auth transport in `apps/web/src/__tests__/App.followUpSuggestions.test.tsx`

### Implementation for User Story 4

- [x] T061 [US4] Implement the pure visible-state derivation and stale-key logic in `apps/web/src/followUpSuggestions.ts`
- [x] T062 [P] [US4] Implement the accessible optional suggestion group in `apps/web/src/components/FollowUpSuggestions.tsx`
- [x] T063 [US4] Integrate suggestion derivation, dismissal, editable composer population, and explicit send in `apps/web/src/App.tsx` and `apps/web/src/components/Composer.tsx`
- [x] T064 [P] [US4] Add complete en/zh-TW suggestion strings and labels in `apps/web/src/i18n/strings.ts`
- [x] T065 [P] [US4] Add responsive/focus/forced-color/reduced-motion suggestion styles in `apps/web/src/styles.css`
- [x] T066 [US4] Run the US4 focused Web tests and record literal zero-hidden-effect results in `specs/077-web-agent-controls/quickstart.md`

**Validation**: T058–T060 fail before T061–T065 and pass afterward. Derivation and selection make zero requests/calls/sends/cost; only explicit ordinary send may start work.

**Rollback**: Remove the pure derivation/component/App wiring; the existing composer, empty state, message history, and send path remain unchanged.

**Checkpoint**: US4 independently improves continuation UX without becoming an agent action or cost source.

---

## Phase 7: User Story 5 — Trust The Delivered Agent Controls (Priority: P3)

**Goal**: Produce fresh full-stack, browser, ownership, public-safety, and documentation evidence from the reviewed mixed working tree.

**Independent Test**: Run all required gates, two-principal matrices, and Chromium scenarios, then reconcile artifacts/docs/status without frozen-history or local-file contamination.

### Verification And Delivery Tasks for User Story 5

- [x] T067 [P] [US5] Run fresh focused Python governance/host/Web API/ownership/contract suites and record literal results in `specs/077-web-agent-controls/quickstart.md`
- [x] T068 [US5] Run `uv sync --locked`, repository-wide Ruff format/check, strict mypy, full pytest with isolated basetemp, and `uv build`; record original failures/skips/results in `specs/077-web-agent-controls/quickstart.md`
- [x] T069 [P] [US5] Run fresh Web dependency sync, typecheck, full Vitest, generated-type drift checks, and production build; record audit/install limitations and literal results in `specs/077-web-agent-controls/quickstart.md`
- [x] T070 [P] [US5] Run Desktop dependency sync permitted by the environment, typecheck, and full Vitest; record any lifecycle-script adjustment and literal results in `specs/077-web-agent-controls/quickstart.md`
- [x] T071 [US5] Execute the fresh Chromium 1440/1024/768/375 plus 640/320 reflow, en/zh-TW, light/dark, keyboard/focus, reduced-motion, forced-color, plan/cost/context/reference/suggestion, two-principal, and state-return matrix; assert/record every control category is reached within at most two navigation actions and unchanged chat returns in one action, store only ignored evidence under `.playwright-mcp/spec077-agent-controls/`, and record literal results in `specs/077-web-agent-controls/quickstart.md`
- [x] T072 [US5] Run whitespace, architecture-boundary, Gateway/Event Bus/checkpoint/default/dependency, Spec Kit, generated-contract, raw-openspec exclusion, frozen-hash, and tracked/staged/untracked public-safety scans; record literal results in `specs/077-web-agent-controls/quickstart.md`
- [x] T073 [US5] After T067–T072 are green, update approved public host/Web surfaces in `docs/api-reference.md` and relevant Web host/capability documentation
- [x] T074 [US5] After T067–T072 are green, add an accurate 077 entry under `CHANGELOG.md` `[Unreleased]` when required by repository rules
- [x] T075 [US5] Re-run documentation/API/public-safety/Spec Kit consistency checks after T073–T074 and append literal results to `specs/077-web-agent-controls/quickstart.md`

**Validation**: T067–T072 provide fresh implementation/browser evidence; T073–T074 synchronize public documentation; T075 proves the synchronized state before final ownership and transition review.

**Rollback**: Restore docs/status to the last internally consistent in-progress state and keep 077 unverified if any product, browser, ownership, safety, or documentation gate regresses.

**Checkpoint**: US5 supplies reproducible, literal evidence for every behavior and delivery boundary; no publication action has occurred.

---

## Phase 8: Polish And Cross-Cutting Review

**Purpose**: Final traceability, requirement quality, simplification, ownership, and transaction-safe completion review.

- [x] T076 [P] Re-evaluate all 59 items in `specs/077-web-agent-controls/checklists/requirements.md` and `checklists/agent-controls-readiness.md` against final behavior/docs; record any regression before completion
- [x] T077 Review every requirement and success criterion against implemented tests/tasks and record the coverage map in `specs/077-web-agent-controls/quickstart.md`
- [x] T078 Review the complete inventory and every candidate hunk against 076/080/081/077/local ownership; prove frozen hashes, `.superpowers/**`, raw `openspec/**`, QA artifacts, and unknown user files are excluded in `specs/077-web-agent-controls/quickstart.md`
- [x] T079 Run `/speckit-analyze` after implementation and resolve all blocking 077 artifact inconsistencies in `specs/077-web-agent-controls/`
- [x] T080 Produce the pre-transition completion record with approved human gate, changed scope, literal verification, known limitations, rollback, and explicit no-stage/commit/push/release statement in `specs/077-web-agent-controls/quickstart.md`
- [x] T081 Only after T075–T080 are green/no-blocker, transactionally mark this task complete and update `docs/loopplane-agent-board.md` plus `.specify/feature.json` for the 077 Verified/next-unit transition, then immediately re-run final diff, ownership, frozen-hash, public-safety, Spec Kit, and documentation-consistency checks; retain the transition only if every check remains green, otherwise restore this checkbox, 077 in-progress, and the 077 pointer

**Validation**: T076–T080 leave no requirement, coverage, analyze, ownership, safety, or evidence blocker; T081 is the only task allowed to retain a Verified transition.

**Rollback**: Reopen the affected story, revert only its owned 077 hunks, restore the last internally consistent docs/pointer/task state, and rerun the affected gates. Never edit frozen 076/080/081 artifacts.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup/Gate**: starts immediately; T001 approval blocks every source/test/generated-type task
- **Phase 2 Foundational**: depends on all Phase 1 tasks and approved T001; blocks every user story
- **US1 (Phase 3)**: depends on Phase 2 and is the MVP/security-critical policy slice
- **US2 (Phase 4)**: depends on the US1 safe projection but preserves independent accounting/enforcement behavior
- **US3 (Phase 5)**: depends on the US1 Settings category/client state; context/upload/artifact behavior remains independently testable
- **US4 (Phase 6)**: depends only on transport-neutral visible state from US1/US3 and remains pure client behavior
- **US5 (Phase 7)**: depends on US1–US4 completion
- **Phase 8**: depends on all stories and synchronized documentation

### User Story Dependencies

- **US1**: no story dependency after Foundation; establishes the safe projection, approved transport field, and Settings category
- **US2**: uses the US1 projection/category but reuses existing cost/guard authority
- **US3**: uses the US1 category/state and existing 081 context projection; does not depend on US2 accounting
- **US4**: may begin after the shared App/composer state shape is stable; no backend dependency
- **US5**: integrates all prior stories and owns fresh delivery evidence

### Within Each Story

1. Write the listed tests first and observe intended failures.
2. Implement the smallest boundary-preserving production change.
3. Run the story-focused suite and record literal red/green evidence.
4. Do not infer full completion from focused results.
5. Stop immediately if implementation requires any unapproved contract/ADR boundary.

### Parallel Opportunities

- T003–T004 use separate artifact/review concerns and can run in parallel.
- T005–T008 create separate Python/Web fixtures and can run in parallel after approval.
- T009–T016 are red tests in separate files and can be authored in parallel.
- T030–T031, T043, T055–T056, and T062/T064/T065 edit separate presentation files/components where noted, but shared `strings.ts`/`styles.css` work must be serialized across stories.
- T033–T037, T045–T049, and T058–T060 are story-specific red-test batches.
- T067, T069, and T070 may run in parallel only after code changes stop; do not run full pytest concurrently with multi-agent workflows.

---

## Parallel Example: User Story 1

```text
Task: "Add safe projection/mode rejection unit tests in tests/unit/test_agent_controls.py"
Task: "Add mode-aware deny-wins tests in tests/unit/test_governance_modes.py"
Task: "Add request/generated contract tests in tests/contract/test_web_agent_controls_contract.py"
Task: "Add Settings posture/mode tests in apps/web/src/__tests__/AgentControlsSettings.test.tsx"
```

## Parallel Example: User Story 3

```text
Task: "Add structured upload tests in apps/web/src/__tests__/Attachments.test.tsx"
Task: "Add artifact-reference reducer tests in apps/web/src/__tests__/chatReducer.test.ts"
Task: "Add metadata-only ToolCard tests in apps/web/src/__tests__/ToolCard.test.tsx"
Task: "Add context/reference Settings tests in apps/web/src/__tests__/AgentControlsReferences.test.tsx"
```

## Parallel Example: User Story 4

```text
Task: "Add pure suggestion derivation tests in apps/web/src/__tests__/followUpSuggestions.test.ts"
Task: "Add accessible suggestion interaction tests in apps/web/src/__tests__/FollowUpSuggestions.test.tsx"
Task: "Add zero-request App integration tests in apps/web/src/__tests__/App.followUpSuggestions.test.tsx"
```

---

## Implementation Strategy

### MVP First — User Story 1

1. Complete Phase 1 and obtain the exact outward-contract approval.
2. Complete foundational fixtures.
3. Write all US1 red tests.
4. Implement safe projection plus one-run host-approved mode selection through existing decide ownership.
5. Validate US1 independently and stop before cost/reference/suggestion expansion if any policy boundary is unclear.

### Incremental Delivery

1. US1 establishes safe plan/permission controls.
2. US2 adds authoritative cost and guard visibility without accounting changes.
3. US3 adds context and opaque current-session references without browser content/storage expansion.
4. US4 adds pure deterministic continuation suggestions.
5. US5 and Phase 8 produce fresh evidence, docs convergence, and transaction-safe status.

### Safety Rules

- Do not start T005 or any later source/test/generated-type task until T001 is explicitly approved.
- Do not edit frozen 076/080/081 `spec.md`, `plan.md`, or `tasks.md`.
- Do not stage or modify `.superpowers/**`, raw `openspec/**`, ignored QA evidence, or unknown user files.
- Do not use destructive cleanup, blanket staging, commit, branch, push, pull request, tag, version, release, or deployment operations without separate authorization.
- Do not introduce browser-side enforcement, raw rule/config/resource content, direct plan exit, durable permission/budget state, artifact indexes/sharing, Event Bus/checkpoint/Gateway/default/dependency changes.
- If a required design crosses any listed boundary, stop for a new maintainer/ADR gate rather than broadening this unit silently.
