# Tasks: Desktop Capability Parity

**Input**: Design documents from `specs/083-desktop-capability-parity/`

**Prerequisites**: `plan.md`, `spec.md`; 078 Verified

**Tests**: Required. Each slice is red → green → focused regression → broader gate. Test tasks appear before their implementation tasks.

**Organization**: Grouped by wave. Each wave ends green on all gates and is an independent revert boundary.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on an incomplete task in the same phase.
- **[Story]**: Maps to the five user stories in `spec.md`.
- Every task names concrete files and FR/SC traceability.

**Standing rule for every wave that adds a sidecar method**: `_DESKTOP_METHOD_NAMES` in `apps/desktop/sidecar/bridge.py`, **both** exact-equality lists in `tests/integration/test_desktop_sidecar.py` (the packaged-handshake assertion and the in-process dispatcher assertion), and the `REQUIRED_METHODS` exact-membership allowlist in `apps/desktop/electron/sidecar-rpc.ts` are updated in the same change — the TS client refuses the runtime as incompatible on any mismatch. This is a task, never a cleanup step (FR-015).

**Standing rule for every wave that adds an IPC channel**: the channel is registered in `ipc-channels.ts`, added to the `channels` array in `ipc-handlers.ts`, guarded with `guard(event)`, exposed through `preload.ts` and `apps/desktop/src/global.d.ts`, and gains its own untrusted-sender test (FR-019).

---

## Phase 1: Wave 1 — Cost Visibility

- [x] T001 [US1] Write focused RED tests for a cost projection in `tests/unit/test_desktop_cost_methods.py`: exact `Decimal` strings preserved without float coercion; unpriced, partially priced, unavailable, and zero each distinct; a host with no pricing or no ledger answers unavailable rather than zero; no path, exception, or principal identifier in any field (FR-001, FR-002; SC-001)
- [x] T002 [US1] Implement `apps/desktop/sidecar/methods/cost.py` projecting `LoopPlaneHost.session_cost` and `monthly_spend`, carrying the unpriced / partially-priced / unknown distinction from `agent_controls(session_id).budget.pricing` (`session_cost` alone is `Decimal | None` and cannot express it); give the cost domain its availability card in `capabilities_list` (`apps/desktop/sidecar/methods/inspection.py`) with a reason when neither pricing nor a ledger is configured (FR-012); register it in `build_rpc_dispatcher`, and add `cost.get` to `_DESKTOP_METHOD_NAMES`, to both exact lists in `tests/integration/test_desktop_sidecar.py`, and to `REQUIRED_METHODS` in `apps/desktop/electron/sidecar-rpc.ts` (FR-001, FR-002, FR-012, FR-015, FR-016)
- [x] T003 [US1] Add the `lp:cost:get` channel across `ipc-channels.ts`, `ipc-handlers.ts`, `preload.ts`, and `global.d.ts`, with an untrusted-sender test in `apps/desktop/src/__tests__/main-security.test.ts` (FR-019)
- [x] T004 [US1] Surface the session figure in the conversation pane's status area and the month-to-date figure in the inspection sidebar in `apps/desktop/src/App.tsx`, rendering absence as its own state; obey the two smoke couplings in `docs/desktop-gui.md` (the runtime-status `aria-label` keeps the word `usable`; the conversation keeps rendering inside the `LoopPlane smoke latest outcome` pane body) and leave all seven fixed accessible names attached to exactly their current elements; reuse the shared `SessionCost` type and the `sessionCost`/`monthlyCost` props `AgentControlsSettings` already accepts, and light the shared sidebar's existing Cost row (`inspection.cost` is that row's label key — en default in the shared vocabulary, zh-TW override in the Desktop map); add English and zh-TW strings in `apps/desktop/src/i18n.tsx` (FR-001, FR-002, FR-021; SC-001, SC-007)
- [x] T005 [US1] Extend `tests/contract/test_desktop_public_safety_routing.py` over the cost projection and rerun all gates plus the repository public-safety scan (SC-004)

---

## Phase 2: Wave 2 — Model Selection

- [x] T006 [US2] Write focused RED tests (TS) for the curated provider catalog: each supported provider lists its curated models with the configured id marked current (and appended when absent from the curated list); an unknown or unconfigured provider yields an empty catalog; no entry carries key material (FR-003)
  - **VERIFIED 2026-08-15 — original per-run premise FAILED; wave STOPPED.** The parameter chain exists (`host.session(model=)` at `host.py:249`, `fork_session(model=)` at `:404`, both via `_effective_model`), but the string has no effect on a single-adapter host: `ModelBoundary` is `stream_turn(request)` only and `ModelRequest` carries no model id (`src/loopplane/model/boundary.py:53-61,104-108`); the loop calls `self._model.stream_turn(request)` (`loop.py:360`) with the adapter's construction-time model. Web switches models by routing to a per-model host (`webapi/app.py:195-203`), which Desktop's one-profile/one-host architecture cannot mirror. **Maintainer decision 2026-08-19: re-scoped to the one-step ADR 0016 switch below (plan.md Wave 2).**
- [x] T007 [US2] Implement the curated catalog as static data in `apps/desktop/electron/provider-catalog.ts` (model ids verified against current provider documentation, not memory) and answer it from Electron main over the vault's current provider + model id — the vault, not the spawn env, is the truth after a save. No sidecar method and no registry change (FR-003)
- [x] T008 [US2] Add the `lp:providers:catalog` channel across `ipc-channels.ts`, `ipc-handlers.ts`, `preload.ts`, and `global.d.ts` with `guard(event)` and an untrusted-sender test (extend the `PROVIDER_CHANNELS` table in `main-security.test.ts`) (FR-019)
- [x] T009 [US2] Upgrade the Model provider panel: the model field offers the catalog (free-form input stays possible) and a one-step "save and restart" action runs the existing `providersSave` (stored key reused) then the existing `providersRestart`; the one-step action is disabled while a run is in flight (FR-003, FR-004; SC-002)
- [x] T010 [US2] Add en/zh-TW strings for every new label and rerun all gates (FR-021; SC-007)

---

## Phase 3: Wave 3 — Presentation Extraction (no new behavior)

- [x] T011 [P] Write RED tests in `packages/cowork-presentation/src/__tests__/settings-ports.test.tsx` asserting each moved panel renders from an injected service and never imports a transport type (FR-020)
- [x] T012 [P] Move `McpSettings` to `packages/cowork-presentation/src/components/settings/` behind a narrow service interface modeled on `AgentControlsSettings`; leave `apps/web/src/components/settings/McpSettings.tsx` as an adapter over `ApiClient` (FR-020; SC-006)
- [x] T013 [P] Move `MemorySettings` the same way (FR-020; SC-006)
- [x] T014 [P] Move `SkillSettings` the same way (FR-020; SC-006)
- [x] T015 [P] Move `ScheduleSettings` the same way (FR-020; SC-006)
- [x] T016 [P] Move `WorkspaceSettings` the same way (FR-020; SC-006)
- [x] T017 [P] Move `ModelDefaultSettings` the same way (FR-020; SC-006)
- [x] T018 Run the Web contract suites (`tests/contract/test_web_*_contract.py`, `test_webapi_boundary.py`, `test_web_type_artifacts.py`) and the Web Vitest suite without editing them; any failure is a regression, not an expected diff (SC-006)

---

## Phase 4: Wave 4 — Capability Management

- [x] T019 [US3] Write RED tests in `tests/unit/test_desktop_capability_methods.py` for MCP: list/get/upsert/delete project metadata only; **no endpoint, header, token, or credential appears in any response**; an unreachable server is reported unavailable with a reason; a mutation without the lease is refused busy (FR-006, FR-018; SC-003, SC-004)
- [x] T020 [US3] Implement MCP methods in `apps/desktop/sidecar/methods/capability.py` over `list_managed_mcp`/`get_managed_mcp`/`upsert_managed_mcp`/`reconnect_managed_mcp`/`delete_managed_mcp`, taking the profile mutation lease with the `_require_mutation` pattern; align the existing mcp `capabilities_list` card's availability and reason (FR-012); register and update all method registries per the standing rule (FR-006, FR-012, FR-015, FR-016, FR-017)
- [x] T021 [US3] Write RED tests for managed skills, then implement over `list_managed_skills`/`write_managed_skill`/`import_managed_skill`/`get_managed_skill`/`delete_managed_skill` with the same lease discipline, extending the skills `capabilities_list` card the same way (FR-007, FR-012, FR-017)
- [x] T022 [US3] Write RED tests for managed memory, then implement over `list_managed_memory`/`write_managed_memory`/`get_managed_memory`/`delete_managed_memory`, with search as a client-side filter over listed metadata (no host search method exists and none is added), extending the memory `capabilities_list` card the same way (FR-008, FR-012, FR-017)
- [x] T023 [US3] Add the `lp:capability:*` channels with main-generated mutation ids and one untrusted-sender test per channel (FR-017, FR-019)
- [x] T024 [US3] Add sidecar-backed service adapters in `apps/desktop/src/services/` and mount the MCP, skills, and memory tabs in the settings view in `apps/desktop/src/App.tsx` (FR-006–FR-008; SC-003)
- [x] T025 [US3] Add en/zh-TW strings for every new label, action, and failure reason (FR-021; SC-007)
- [x] T026 [US3] Extend `tests/contract/test_desktop_public_safety_routing.py` across all three domains, asserting absence of endpoint/credential/path/exception rather than presence of expected fields (FR-018; SC-004)

---

## Phase 5: Wave 5 — Governance Surface

- [x] T027 [US4] Write RED tests in `tests/unit/test_desktop_governance_methods.py` for schedules, workspace contexts, and the model default, including unavailable-domain reporting through `capabilities.list` rather than protocol negotiation (FR-009–FR-012)
- [x] T028 [US4] Implement `apps/desktop/sidecar/methods/governance.py` over the schedule methods (`list_managed_schedules`/`upsert`/`get`/`enable`/`disable`/`run_managed_schedule_now`/`delete` — the Web panel's full verb set), the workspace-context methods including `bind_session_context`, and the model default including `clear_model_default`; every durable mutation takes the profile mutation lease with the `_require_mutation` pattern and a main-generated mutation id (FR-017); add the schedules / workspace-contexts / model-default `capabilities_list` cards (FR-012); register and update all method registries per the standing rule (FR-009–FR-012, FR-015, FR-016, FR-017)
- [x] T029 [US4] Add the `lp:governance:*` channels with main-generated mutation ids and untrusted-sender tests (FR-017, FR-019)
- [x] T030 [US4] Mount the schedules, workspace-context, and model-default tabs with their service adapters; the model default is chosen from the catalog, never typed freely (FR-009–FR-011)
- [x] T031 [US4] Add en/zh-TW strings and extend the public-safety routing test (FR-021; SC-004, SC-007)

---

## Phase 6: Wave 6 — Host Commands

- [x] T032 [US5] **Boundary gate resolved (2026-08-19): admitted — ADR 0017.** Add `loopplane.commands` to `RUNTIME_ALLOWED_PREFIXES` in `tests/contract/test_desktop_boundary.py` in the same change as the sidecar's first import of it. Then write RED tests in `tests/unit/test_desktop_command_methods.py` asserting a leading `/` is answered by `CommandRegistry` with no model call, no Gateway invocation, and no Event Bus emission; an unknown command returns the normalized message; non-command input is byte-identical to today (FR-013, FR-014)
- [x] T033 [US5] Implement a `command.execute` sidecar method over `loopplane.commands.default_registry()` with the full standing-rule registry discipline, add its IPC channel across the four files with `guard(event)` and an untrusted-sender test, and expose `/cost`, `/model`, `/memory`, and `/compact` in the composer, mirroring the CLI and Web paths (FR-013, FR-015, FR-019)
- [x] T034 [US5] Add en/zh-TW strings for the command list and its results (FR-021; SC-007)

---

## Phase 7: Wave 7 — Convergence

- [x] T035 [P] Document the capability-management surface in `docs/desktop-gui.md`, including which domains report unavailable and why, and add the 083 row to `docs/capabilities.md` (SC-003)
- [x] T036 [P] Confirm `git diff --stat src/loopplane` is empty for this unit and record it as the no-runtime-change claim's evidence (NG-006; SC-008)
  - Recorded 2026-08-16: `git diff --stat src/loopplane` produced no output with every wave's working-tree changes present.
- [x] T037 Run the negative self-check on `tests/contract/test_desktop_boundary.py` — inject a forbidden import, observe red, restore — so the guard is proven rather than assumed
  - Run 2026-08-16: injected `from loopplane.controller.controller import RuntimeController` into `sidecar/methods/governance.py` → 2 failed; byte-exact restore verified → 6 passed.
- [x] T038 Run every gate: `ruff format`, `ruff check`, `mypy`, full `pytest`, typecheck and tests across all three TypeScript workspaces, and the desktop build (SC-005–SC-007)
  - Run 2026-08-16: ruff format/check + mypy clean; full pytest 2064 passed / 33 skipped; typecheck ×3 clean; Vitest shared 68 / desktop 277 / web 202 (web untouched); desktop build green.
- [x] T039 Verify reversibility: revert the unit's commits on a scratch branch and confirm Desktop behavior and the Web suites match today's tree (SC-008)
  - **DONE 2026-08-19:** `git revert ea741f6` on a scratch branch produced a tree byte-identical to pre-083 (`git diff 2aa46e3 HEAD --stat` empty); on the reverted tree the Desktop (23 files), Web (58), and presentation (11) Vitest suites and the desktop pytest subset (237 passed) were all green. Branch deleted, never pushed.
  - Note 2026-08-16: the unit is still uncommitted, so there are no commits to revert; "reverted" state IS current HEAD, which 078's Verified evidence and green CI already prove. Equivalent evidence today: additive-only change set (all six registries, channels, tabs enumerable from `git status`/`git diff`), `src/loopplane` diff empty (T036). Run the literal scratch-branch revert after the commits exist (maintainer authorization).
- [x] T040 Request the packaged delivery run and confirm `scripts/smoke-desktop-artifact.ps1 -Scenario all` passes with all seven locators resolving exactly once (SC-005)
  - **DONE 2026-08-19:** maintainer Stage-C approval on exact commit `9b42cab` triggered delivery run 32265836163 - source recheck, Stage-C verification, and "Token-free package, freeze, and external UI Automation smoke" (`-Scenario all`, exit-0-or-throw wrapper) all succeeded. An earlier run on `f7e2b88` failed its source recheck on the public-safety scan; fixed by `9b42cab` before this run.
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
