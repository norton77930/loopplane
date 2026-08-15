# Tasks: Desktop Capability Parity

**Input**: Design documents from `specs/083-desktop-capability-parity/`

**Prerequisites**: `plan.md`, `spec.md`; 078 Verified

**Tests**: Required. Each slice is red → green → focused regression → broader gate. Test tasks appear before their implementation tasks.

**Organization**: Grouped by wave. Each wave ends green on all gates and is an independent revert boundary.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on an incomplete task in the same phase.
- **[Story]**: Maps to the five user stories in `spec.md`.
- Every task names concrete files and FR/SC traceability.

**Standing rule for every wave that adds a sidecar method**: `_DESKTOP_METHOD_NAMES` in `apps/desktop/sidecar/bridge.py` and the exact-equality list in `tests/integration/test_desktop_sidecar.py` are updated in the same change. This is a task, never a cleanup step (FR-015).

**Standing rule for every wave that adds an IPC channel**: the channel is registered in `ipc-channels.ts`, added to the `channels` array in `ipc-handlers.ts`, guarded with `guard(event)`, exposed through `preload.ts` and `apps/desktop/src/global.d.ts`, and gains its own untrusted-sender test (FR-019).

---

## Phase 1: Wave 1 — Cost Visibility

- [ ] T001 [US1] Write focused RED tests for a cost projection in `tests/unit/test_desktop_cost_methods.py`: exact `Decimal` strings preserved without float coercion; unpriced, partially priced, unavailable, and zero each distinct; a host with no pricing or no ledger answers unavailable rather than zero; no path, exception, or principal identifier in any field (FR-001, FR-002; SC-001)
- [ ] T002 [US1] Implement `apps/desktop/sidecar/methods/cost.py` projecting `LoopPlaneHost.session_cost` and `monthly_spend`, register it in `build_rpc_dispatcher`, and add `cost.get` to `_DESKTOP_METHOD_NAMES` and to the exact list in `tests/integration/test_desktop_sidecar.py` (FR-001, FR-002, FR-015, FR-016)
- [ ] T003 [US1] Add the `lp:cost:get` channel across `ipc-channels.ts`, `ipc-handlers.ts`, `preload.ts`, and `global.d.ts`, with an untrusted-sender test in `apps/desktop/src/__tests__/main-security.test.ts` (FR-019)
- [ ] T004 [US1] Surface the session figure in the header context strip and the month-to-date figure in the inspection sidebar in `apps/desktop/src/App.tsx`, rendering absence as its own state; add English and zh-TW strings in `apps/desktop/src/i18n.tsx` (FR-001, FR-002, FR-021; SC-001, SC-007)
- [ ] T005 [US1] Extend `tests/contract/test_desktop_public_safety_routing.py` over the cost projection and rerun all gates plus the repository public-safety scan (SC-004)

---

## Phase 2: Wave 2 — Model Selection

- [ ] T006 [US2] Write focused RED tests in `tests/unit/test_desktop_model_methods.py`: the catalog lists only what the configured provider offers; an unconfigured provider answers unavailable; a rejected model id returns a fixed public reason and no partial state (FR-003, FR-005)
- [ ] T007 [US2] Extend the provider surface with a catalog read in `apps/desktop/sidecar/methods/` and register `model.catalog`, updating `_DESKTOP_METHOD_NAMES` and the exact list (FR-003, FR-015)
- [ ] T008 [US2] Add the model-catalog IPC channel with its untrusted-sender test (FR-019)
- [ ] T009 [US2] Add a composer model selector in `apps/desktop/src/` that submits the selection with the run rather than storing a durable field, disabled while a run is in flight, showing the host-accepted selection and never a renderer draft (FR-003, FR-004; SC-002)
- [ ] T010 [US2] Add en/zh-TW strings and rerun all gates (FR-021; SC-007)

---

## Phase 3: Wave 3 — Presentation Extraction (no new behavior)

- [ ] T011 [P] Write RED tests in `packages/cowork-presentation/src/__tests__/settings-ports.test.tsx` asserting each moved panel renders from an injected service and never imports a transport type (FR-020)
- [ ] T012 [P] Move `McpSettings` to `packages/cowork-presentation/src/components/settings/` behind a narrow service interface modeled on `AgentControlsSettings`; leave `apps/web/src/components/settings/McpSettings.tsx` as an adapter over `ApiClient` (FR-020; SC-006)
- [ ] T013 [P] Move `MemorySettings` the same way (FR-020; SC-006)
- [ ] T014 [P] Move `SkillSettings` the same way (FR-020; SC-006)
- [ ] T015 [P] Move `ScheduleSettings` the same way (FR-020; SC-006)
- [ ] T016 [P] Move `WorkspaceSettings` the same way (FR-020; SC-006)
- [ ] T017 [P] Move `ModelDefaultSettings` the same way (FR-020; SC-006)
- [ ] T018 Run the Web contract suites (`tests/contract/test_web_*_contract.py`, `test_webapi_boundary.py`, `test_web_type_artifacts.py`) and the Web Vitest suite without editing them; any failure is a regression, not an expected diff (SC-006)

---

## Phase 4: Wave 4 — Capability Management

- [ ] T019 [US3] Write RED tests in `tests/unit/test_desktop_capability_methods.py` for MCP: list/get/upsert/delete project metadata only; **no endpoint, header, token, or credential appears in any response**; an unreachable server is reported unavailable with a reason; a mutation without the lease is refused busy (FR-006, FR-018; SC-003, SC-004)
- [ ] T020 [US3] Implement MCP methods in `apps/desktop/sidecar/methods/capability.py` over `list/get/upsert/delete_managed_mcp`, taking the profile mutation lease with the `_require_mutation` pattern; register and update the exact method list (FR-006, FR-015, FR-016, FR-017)
- [ ] T021 [US3] Write RED tests for managed skills, then implement over `list/write/import/get/delete_managed_skill` with the same lease discipline (FR-007, FR-017)
- [ ] T022 [US3] Write RED tests for managed memory, then implement over `list/write/get/delete_managed_memory`, including search (FR-008, FR-017)
- [ ] T023 [US3] Add the `lp:capability:*` channels with main-generated mutation ids and one untrusted-sender test per channel (FR-017, FR-019)
- [ ] T024 [US3] Add sidecar-backed service adapters in `apps/desktop/src/services/` and mount the MCP, skills, and memory tabs in the settings view in `apps/desktop/src/App.tsx` (FR-006–FR-008; SC-003)
- [ ] T025 [US3] Add en/zh-TW strings for every new label, action, and failure reason (FR-021; SC-007)
- [ ] T026 [US3] Extend `tests/contract/test_desktop_public_safety_routing.py` across all three domains, asserting absence of endpoint/credential/path/exception rather than presence of expected fields (FR-018; SC-004)

---

## Phase 5: Wave 5 — Governance Surface

- [ ] T027 [US4] Write RED tests in `tests/unit/test_desktop_governance_methods.py` for schedules, workspace contexts, and the model default, including unavailable-domain reporting through `capabilities.list` rather than protocol negotiation (FR-009–FR-012)
- [ ] T028 [US4] Implement `apps/desktop/sidecar/methods/governance.py` over the schedule, workspace-context, and model-default host methods; register and update the exact method list (FR-009–FR-011, FR-015, FR-016)
- [ ] T029 [US4] Add the `lp:governance:*` channels with untrusted-sender tests (FR-019)
- [ ] T030 [US4] Mount the schedules, workspace-context, and model-default tabs with their service adapters; the model default is chosen from the catalog, never typed freely (FR-009–FR-011)
- [ ] T031 [US4] Add en/zh-TW strings and extend the public-safety routing test (FR-021; SC-004, SC-007)

---

## Phase 6: Wave 6 — Host Commands

- [ ] T032 [US5] Write RED tests asserting a leading `/` is answered by `CommandRegistry` with no model call, no Gateway invocation, and no Event Bus emission; an unknown command returns the normalized message; non-command input is byte-identical to today (FR-013, FR-014)
- [ ] T033 [US5] Wire `/cost`, `/model`, `/memory`, and `/compact` through the sidecar's existing host command surface and expose them in the composer, mirroring the CLI and Web paths (FR-013)
- [ ] T034 [US5] Add en/zh-TW strings for the command list and its results (FR-021; SC-007)

---

## Phase 7: Wave 7 — Convergence

- [ ] T035 [P] Document the capability-management surface in `docs/desktop-gui.md`, including which domains report unavailable and why, and add the 083 row to `docs/capabilities.md` (SC-003)
- [ ] T036 [P] Confirm `git diff --stat src/loopplane` is empty for this unit and record it as the no-runtime-change claim's evidence (NG-006; SC-008)
- [ ] T037 Run the negative self-check on `tests/contract/test_desktop_boundary.py` — inject a forbidden import, observe red, restore — so the guard is proven rather than assumed
- [ ] T038 Run every gate: `ruff format`, `ruff check`, `mypy`, full `pytest`, typecheck and tests across all three TypeScript workspaces, and the desktop build (SC-005–SC-007)
- [ ] T039 Verify reversibility: revert the unit's commits on a scratch branch and confirm Desktop behavior and the Web suites match today's tree (SC-008)
- [ ] T040 Request the packaged delivery run and confirm `scripts/smoke-desktop-artifact.ps1 -Scenario all` passes with all seven locators resolving exactly once (SC-005)
- [ ] T041 Request maintainer completion approval; only after fresh evidence transition 083 to Verified in `docs/loopplane-agent-board.md`. Do not commit, tag, version, release, sign, or deploy without separate authorization

---

## Dependencies and Execution Order

1. **Wave 1** and **Wave 2** are independent of each other and of Wave 3; either may go first. Wave 1 is listed first because it addresses the sharpest gap.
2. **Wave 3** must precede **Waves 4–5**, so those waves wire an already-shared component instead of authoring a second implementation.
3. **Wave 4** precedes **Wave 5** only by priority, not by dependency.
4. **Wave 6** depends on nothing in this unit beyond the composer being present.
5. **Wave 7** depends on every wave that is actually taken; a wave may be dropped without invalidating the others.

## Notes

- Every task uses the required checkbox/ID/path format; story tasks include `[US#]`.
- `[P]` means file-level parallelism, not permission to run the full pytest suite and multi-agent work concurrently.
- No task in this unit may edit `src/loopplane`. If one appears to need to, stop: the assumption that the host already exposes everything has failed and the plan needs revisiting before code does.
- Read the smoke-coupling section of `docs/desktop-gui.md` before changing any Desktop presentation.
- Commit, push, PR, tag, version, release, sign, and deploy each require separate user authorization.
