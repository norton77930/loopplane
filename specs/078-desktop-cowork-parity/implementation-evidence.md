# 078 Desktop Cowork Parity Implementation Evidence

This file records bounded evidence only. It is not approval authority: later gates must independently refetch and verify their required immutable review, commit, tree, and blob authorities.

## Stage A — PyInstaller build-lock materialization

<!-- STAGE-A-EVIDENCE START -->

- **External-human approval reference**: In the current interactive Claude Code session, the human user selected `批准 Stage A (Recommended)` in response to the explicit 078 Stage A gate prompt. The approved scope was limited to the three paths listed below and expressly excluded install, build, product/test source, workflow/manifest changes, commit, push, and PR creation.
- **Materialized at (UTC)**: `2026-07-31T16:55:38.579Z`
- **Approved direct input**: `pyinstaller==6.21.0`
- **Target interpreter**: Python `3.12`
- **Target platform**: `x86_64-pc-windows-msvc`
- **Resolver**: `uv 0.11.16 (135a36367 2026-05-21 x86_64-pc-windows-msvc)`
- **Compile constraints**: complete transitive resolution with `--generate-hashes --only-binary :all:`
- **Stage A write set**:
  - `apps/desktop/sidecar/pyinstaller-build.in`
  - `apps/desktop/sidecar/pyinstaller-build-windows-py312.txt`
  - `specs/078-desktop-cowork-parity/implementation-evidence.md`
- **Direct-input SHA-256**: `91aedc3e7790bedcabc79b3bd897ba9498252b290887d686ee9a393e9da26cb2`
- **Candidate PyInstaller lock SHA-256**: `363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6`
- **Resolved package count**: `7`
- **Resolved packages**: `altgraph`, `packaging`, `pefile`, `pyinstaller`, `pyinstaller-hooks-contrib`, `pywin32-ctypes`, `setuptools`
- **Structural validation**: PASS — the input is byte-exact, PyInstaller is pinned to `6.21.0`, the resolved package set is complete for this candidate lock, every package stanza carries SHA-256 hashes, and the generated-command header records Python 3.12, Windows x64, hash generation, and wheels-only resolution.
- **Runtime metadata check**: PASS — no `pyinstaller` reference occurs in `pyproject.toml` or `uv.lock`; the tool remains build-only.
- **Deterministic regeneration**: PASS — a second execution of the exact compile command produced the same lock SHA-256 before and after: `363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6`.
- **Excluded actions**: No dependency installation, product/test build, source/test/workflow/manifest/package-lock modification, commit, push, or PR was performed during Stage A. Pre-existing working-tree changes and `.superpowers/**` were not included or modified by Stage A.
- **Gate posture**: ADR 0015 remains `Proposed`. This candidate lock is not an accepted build input and authorizes no T003/T004 or product implementation. T002 still requires a distinct submitted external-human Stage-B bootstrap review and independent immutable GitHub authority verification.

Exact materialization command:

```powershell
uv pip compile apps/desktop/sidecar/pyinstaller-build.in `
  --output-file apps/desktop/sidecar/pyinstaller-build-windows-py312.txt `
  --python-version 3.12 `
  --python-platform x86_64-pc-windows-msvc `
  --generate-hashes `
  --only-binary :all:
```

<!-- STAGE-A-EVIDENCE END -->

## Stage B bootstrap (T002) — submitted review authority (comparison record only)

<!-- STAGE-B-BOOTSTRAP-EVIDENCE START -->

This block is a **comparison output only**. It is not locator authority and not final Stage-B acceptance. Later verifier modes must receive the immutable T002 review-ID/expected-commit pair as invocation inputs and rederive all values from GitHub API + content-addressed commit authority.

### Gate checks (refetched 2026-08-05)

| Check | Result |
|-------|--------|
| PR | `norton77930/loopplane` #3 (open) |
| PR author | `norton77930` |
| Review ID | `4864730949` |
| Review node ID | `PRR_kwDOS4xEH88AAAABIfXnRQ` |
| Review API URL | `https://github.com/norton77930/loopplane/pull/3#pullrequestreview-4864730949` |
| `state` | `APPROVED` |
| `submitted_at` | `2026-08-05T13:16:24Z` |
| Reviewer login | `norton777930` |
| `user.type` | `User` |
| `author_association` | `COLLABORATOR` |
| PR-author inequality | PASS (`norton777930` ≠ `norton77930`, case-insensitive) |
| Reviewed `commit_id` | `5319634a7e5c77b21ffa5355595fae18f9d82083` |
| PR head equality | PASS (equals PR #3 head at verification) |
| Reviewed tree SHA | `e98d150035560eac0b44cda16fda63e647f748cc` |
| Tree `truncated` | `false` (API recursive tree) |
| ADR 0015 status | **Proposed** (unchanged; bootstrap must not accept ADR) |
| Authorization | **T003 + T004 only** (no T006+ product work; no install/build; no freeze/package) |

### Recorded identities (non-authoritative locators for human comparison)

- **Stage B Bootstrap Approval API URL:** `https://github.com/norton77930/loopplane/pull/3#pullrequestreview-4864730949`
- **Stage B Bootstrap Approval ID:** `4864730949`
- **Stage B Bootstrap Approval Node ID:** `PRR_kwDOS4xEH88AAAABIfXnRQ`
- **Stage B Bootstrap Approval Submitted At:** `2026-08-05T13:16:24Z`
- **Stage B Bootstrap Approver Login:** `norton777930`
- **Stage B Bootstrap Reviewed Commit SHA:** `5319634a7e5c77b21ffa5355595fae18f9d82083`
- **Stage B Bootstrap Reviewed Tree SHA:** `e98d150035560eac0b44cda16fda63e647f748cc`
- **Stage B Bootstrap Review Bundle SHA-256:** `67f815901e64770453467786b6ccd3be25caedcf74b41527aeda2b6818a3961d`
- **Stage B Bootstrap Full-tree blob inventory SHA-256:** `291e88b754df9248a54d98a0ef8395dc6124ae9173490ef2192ef9d91453c24c` (local `git ls-tree -r` over reviewed commit; path/type/mode/blob lines)
- **Candidate PyInstaller lock SHA-256 (bound):** `363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6`

### Bootstrap bundle definition

Sorted relative paths + content SHA-256 (ordinal path order; line format `path␠␠sha256` + LF) over: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`, both checklists, all five contracts, complete Proposed ADR, `pyproject.toml`, `uv.lock`, `pyinstaller-build.in`, and candidate PyInstaller transitive lock (18 paths). Bundle SHA-256 is the UTF-8 SHA-256 of that manifest.

### Immutable invocation inputs for later modes (do not discover from this file)

- Owner: `norton77930`
- Repository: `loopplane`
- Pull request: `3`
- Expected approver (maintainer variable at T002 close-out): `norton777930`
- Optional C2 switch: `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` may remain `true` but was not required for this review (reviewer ≠ author)
- T002 bootstrap review ID: `4864730949`
- T002 expected commit SHA: `5319634a7e5c77b21ffa5355595fae18f9d82083`

### Explicit non-claims

- ADR 0015 is **not** Accepted.
- Root npm workspace/lock is **not** bound (T004/T005).
- Product source, verifier script, package freeze, and artifact smoke are **not** authorized.
- This evidence block cannot authorize itself or substitute for API refetch.

<!-- STAGE-B-BOOTSTRAP-EVIDENCE END -->

## T003 — delivery-gate RED observation

<!-- T003-RED-EVIDENCE START -->

- **When (local)**: after T002 bootstrap authorization
- **Artifacts**:
  - `tests/contract/test_desktop_delivery_gate.py`
  - `tests/helpers/desktop_stage_b_policy.py`
- **Command**: `uv run pytest tests/contract/test_desktop_delivery_gate.py -q`
- **Result**: **RED as required** — `32 failed, 8 passed`
  - 8 pure policy oracle tests pass (mode locators, C2 rule, tree-diff allowlist, extras)
  - 32 verifier entrypoint / `-SelfTest` cases fail because `scripts/verify-desktop-stage-b.ps1` is not yet implemented (T004)
- **Non-claims**: No product source, package manifests, workflow, or verifier implementation was added in T003.

<!-- T003-RED-EVIDENCE END -->

## T004 — verifier + final npm graph materialization

<!-- T004-EVIDENCE START -->

- **Verifier**: `scripts/verify-desktop-stage-b.ps1`
  - Modes: `bootstrap` | `final` | `delivery`
  - Credential seam: `LOOPPLANE_STAGE_B_GITHUB_TOKEN` only (no `GH_TOKEN`/`GITHUB_TOKEN` fallback)
  - `-SelfTest <case>` covers T003 contract cases without network
- **npm graph (pre-implementation final manifests)**:
  - root `package.json` (workspaces: web, desktop, cowork-presentation)
  - `packages/cowork-presentation/package.json`
  - updated `apps/web/package.json` / `apps/desktop/package.json` (workspace dep + final scripts/`main`/`files`)
  - sole root `package-lock.json`
  - removed app-local locks: `apps/web/package-lock.json`, `apps/desktop/package-lock.json`
- **Command**: `uv run pytest tests/contract/test_desktop_delivery_gate.py -q`
- **Result**: **GREEN** — `40 passed`
- **Non-claims**: No product presentation source scaffolding, no install/build of Desktop artifact, ADR remains Proposed, T006+ not authorized until T005.

<!-- T004-EVIDENCE END -->

## Stage B final (T005) — implementation authorization

<!-- STAGE-B-FINAL-EVIDENCE START -->

### Gate checks (refetched 2026-08-05)

| Check | Result |
|-------|--------|
| PR | #3 open; author `norton77930` |
| T002 bootstrap review | `4864730949` / commit `5319634a7e5c77b21ffa5355595fae18f9d82083` / approver `norton777930` |
| T005 final review | `4864943765` / commit `8fe0a00400abfbf6eb466c9dec9c21bf0352b8fb` / approver `norton777930` |
| Pairwise distinct IDs | PASS |
| Same PR | PASS |
| Final `state` | `APPROVED` |
| Final `user.type` / association | `User` / `COLLABORATOR` |
| PR-author inequality | PASS |
| Final tree SHA | `d09077f3a53bf5005cfa94c1eaf944a22ae926ad` |
| Tree truncated | false |
| T002→T005 full-tree allowlist | PASS after including T003 helper/tasks/board paths (see contract allowlist) |
| App-local locks | absent |
| ADR | **Accepted** |

### Identical final field set

Stage B Approval API URL: https://github.com/norton77930/loopplane/pull/3#pullrequestreview-4864943765
Stage B Approval ID: 4864943765
Stage B Approval Node ID: PRR_kwDOS4xEH88AAAABIfkmlQ
Stage B Approval Submitted At: 2026-08-05T13:37:41Z
Stage B Approver Login: norton777930
Stage B Reviewed Commit SHA: 8fe0a00400abfbf6eb466c9dec9c21bf0352b8fb
Stage B Reviewed Tree SHA: d09077f3a53bf5005cfa94c1eaf944a22ae926ad
Stage B Review Bundle SHA-256: da2b0b0594611209a21ad68f01bc38a15a1f53c4bd9bd1f7c18d681e9bba7dbc
Accepted PyInstaller lock SHA-256: 363a52720adf8cd9299334fa9b95719c627192aa23fcfeb1e6ecebafdaef3cf6
Accepted Root package-lock SHA-256: c1808e1b4b13bd191d9538d5dbed34a47eaefe3e48641ac1268b497fd5ab99cd

### Authorization

- **T006+ product implementation is authorized** under 078 tasks.
- Freeze/package/smoke remains blocked until **T090** Stage-C delivery review.
- Accepted manifests/root lock/PyInstaller lock are immutable after this gate; further graph changes require a new T005.

<!-- STAGE-B-FINAL-EVIDENCE END -->

## T007–T008 — workspace resolution and install/typecheck/test evidence

<!-- T007-T008-EVIDENCE START -->

### T007
- `apps/web/tsconfig.json` and `apps/desktop/tsconfig.json`: `paths` for `@loopplane/cowork-presentation` → package `src`
- `apps/desktop/vite.config.ts`: resolve alias for `@loopplane/cowork-presentation`
- Accepted package manifests/locks: **unchanged** (digest match below)

### T008
- Added `packages/cowork-presentation/vitest.config.ts` (`passWithNoTests: true`) and `src/test-setup.ts`
- `npm ci --ignore-scripts` from sole root lock: **exit 0** (695 packages)
- Sole lock check: root `package-lock.json` present; `apps/web` and `apps/desktop` app locks **absent**
- Typecheck: shared / web / desktop `tsc --noEmit` **exit 0**
- Tests:
  - shared vitest: **exit 0** (0 files, passWithNoTests)
  - web: **57 files / 192 tests passed**
  - desktop: **3 files / 12 tests passed**
- T003 delivery-gate regression: **40 passed**
- Verifier SelfTest `modes-declared`: **exit 0**
- Accepted root package-lock SHA-256: `c1808e1b4b13bd191d9538d5dbed34a47eaefe3e48641ac1268b497fd5ab99cd` (**MATCH**, no drift)

<!-- T007-T008-EVIDENCE END -->

## Phase 2 foundations (T010–T015)

<!-- PHASE2-EVIDENCE START -->

### Artifacts
- T010: `tests/helpers/public_safety.py`, `tests/contract/test_desktop_public_safety.py`
- T011: `tests/helpers/desktop_sidecar.py` (+ harness self-tests)
- T012: `apps/desktop/electron/__tests__/helpers.ts` (+ desktop self-tests)
- T013: `packages/cowork-presentation/src/__tests__/{host-contract,events,fixtures.selftest}.ts`
- T014: `tests/helpers/desktop_profile.py` (+ fixture self-tests)
- T015: `tests/helpers/test_phase2_false_green.py` intentional negative mutations

### Commands / results
- `uv run pytest tests/helpers tests/contract/test_desktop_public_safety.py tests/contract/test_desktop_boundary.py -q` → **21 passed**
- `npm run test -w @loopplane/cowork-presentation` → **2 passed** (fixture self-tests)
- `npm run test -w @loopplane/desktop` → **16 passed** (includes 4 electron-helpers self-tests)
- `uv run ruff check` on new helpers → clean
- False-green checks: secondary surfaces fail on secret leak; byte-split does not return full line at chunk size 1

### Checkpoint
Phase 2 harnesses/guards pass on baseline and fail on representative negative mutations. User-story implementation (US1 T016+) may begin.

<!-- PHASE2-EVIDENCE END -->

## User Story 1 — functional local interaction (T016–T033)

<!-- US1-EVIDENCE START -->

**Recorded (local, 2026-08-06)**. This is focused-suite evidence for the US1 Python/Electron/Desktop slice. It is **not** 078 Verified completion (US2–6 and final gates remain). Packaged Electron UI Automation smoke (delivery §6) was **not** re-run in this slice; credential-free coverage is unit/integration/contract level.

### Delivered surfaces
- Host: `working_scope` resume seam; `resume_session`; public `validate_active_generation`
- Sidecar: protocol/dispatcher; Profile Ownership Lock; generation publish; InteractionLease; Host-only `methods/interaction.py`; bridge bootstrap gate + shutdown teardown
- Electron main: `sidecar-rpc.ts` supervisor (byte frames, handshake, no-retry, drain/kill); security guards; typed IPC; lifecycle teardown
- Preload/renderer: frozen `loopplaneDesktop`; typed `SidecarTransport`; single-session `App` (start/progress/approval/question/cancel/outcome/unavailable)

### Focused commands / results

| Suite | Command | Result |
|-------|---------|--------|
| Desktop vitest | `npm run test -w @loopplane/desktop` / `npx vitest run` in `apps/desktop` | **41 passed** (7 files) |
| Python US1 focused | `pytest` on boundary, rpc_v1, generation_validation, profile_lock, runtime_bootstrap, interaction_methods, desktop_sidecar, host_resume_session | **33 passed** |
| Protocol matrix | `test_serialized_writer_and_100_malformed_matrix` | **100** deterministic malformed/stale cases exercised; failures counted without model-call side effects; unknown fallback `messageKey=desktop.error.internal_failure` |
| Boundary | `test_desktop_boundary.py` | **PASS** — sidecar has no live-store reach-through; generation validation only via `validate_active_generation` |

### Containment / public-safety notes (this slice)
- No local network listener in Electron main or sidecar entry (stdio only)
- No mutation auto-retry after child failure (`SidecarRpcClient`)
- Renderer never supplies request/mutation IDs or raw JSON-RPC
- Profile lock released only after Host `aclose` on process exit path; kernel release on crash
- Secondary-surface disclosure: contract boundary + public_safety harnesses still apply; this run did not inject secret fixtures beyond existing helpers

### Gaps vs full T033 / MVP claim
- Full packaged Windows UI Automation smoke (`happy` / missing / corrupt / incompatible sidecar) **not** executed here
- US2–US6 (multi-pane, projects, workspace, backup/restore, delivery packaging gates) **not** complete
- 078 must not be marked Verified from this evidence alone

<!-- US1-EVIDENCE END -->

## User Story 2 — profile / sessions / workspaces (T034–T047)

<!-- US2-EVIDENCE START -->

**Recorded (local, 2026-08-07)**. Focused durability + adapter evidence for US2. Not 078 Verified.

### Surfaces
- `ProfileState` / `ProjectStore` / `WorkspaceStore` / `ProfileMutationLease`
- Host-backed `session.*` + profile `project.*` + `workspace.*` RPC methods
- create/resume **workspace revalidate gate** (`methods/interaction.py` T046)
- Electron typed IPC + native directory chooser (paths stay main-private)
- Renderer `SidecarTransport` session/project/workspace adapters; `SessionSidebar` + App navigation
- Renderer-transient drafts only (`setDraft` / never in `profile.json`)

### Focused results
| Suite | Result |
|-------|--------|
| `test_desktop_profile.py` + workspace + interaction workspace gate + interaction methods + boundary | **25 passed** (representative US2 Python slice) |
| Desktop vitest (sessions sidebar + adapter + App) | **16 passed** in focused files; full desktop suite previously **41+** with US1 |
| Path non-disclosure | Sidebar/UI tests assert no `C:\` / `/Users/` in projections |
| Relink gate | `create_interactive` with `relink_required` → `workspace_relink_required` RpcError |
| Project remove safety | Removes grouping only; sessions not deleted by `ProjectStore.remove` |

### T036 / T037 follow-up (2026-08-07)
| Suite | Result |
|-------|--------|
| `tests/integration/test_desktop_sidecar.py` (legacy + RPC session/project/workspace) | **4 passed** |
| `electron/__tests__/sessions.test.ts` | **4 passed** |
| `electron/__tests__/workspace.test.ts` | **4 passed** (chooser cancel = no RPC; path not in result) |
| `electron/__tests__/preload.test.ts` | **2 passed** |

### Remaining honesty
- Full multi-process restart/fork/moved-workspace matrix still not exhaustive beyond unit/integration samples
- US3–US6 incomplete; 078 not Verified

<!-- US2-EVIDENCE END -->

## User Story 3 — multi-pane single-active lease (T048–T056)

<!-- US3-EVIDENCE START -->

**Refreshed (local, 2026-08-09)**. T048–T056 focused multi-pane, lease, keyboard, reflow, and Chromium evidence. Not 078 Verified.

### Surfaces
- `InteractionLease.require_owner` + busy `owner_pane_id` / `owner_session_id` correlation (T048/T052)
- `packages/cowork-presentation` pane state (`open/focus/claim/release/close`, draft local, session dedup)
- `CoworkShell` roving tab focus + `InspectionSidebar` Escape/focus return
- Shared `ApprovalDialog` / `QuestionDialog` safe Escape behavior and opener/fallback focus restoration
- Shared reflow, visible-focus, reduced-motion, and forced-colors CSS contracts
- Desktop `App` composes CoworkShell + SessionSidebar; second interactive claim fails at presentation and sidecar layers

### T050 focused RED inventory
The behavior seams were observed failing before their minimal T055 implementation:

| Seam | RED observation |
|------|-----------------|
| Pane keyboard navigation | `ArrowRight` expected `onFocusPane("two")`; received zero calls |
| Inspection dismissal | Escape expected one `onClose` call; received zero calls |
| Shared dismissal helper | package/module export was `undefined` |
| Public package surface | `ApprovalDialog`, `QuestionDialog`, and `dismissOnEscape` were absent from the entrypoint |

The first four browser attempts were **invalid harness failures**, not product RED: the harness inspected `BODY` focus, left the Settings view open, checked `aria-expanded` instead of `aria-pressed`, and used the wrong English label (`Back to conversation` instead of `Back to chat`). They are excluded from product evidence. The first valid exact matrix was v5 and was GREEN; no Chromium product failure is claimed retroactively.

### Fresh focused results
| Suite | Result |
|-------|--------|
| `tests/unit/test_desktop_interaction_lease.py` | **5 passed** (busy before second open; owner-only submit; release then re-acquire; outer profile lock) |
| shared panes + accessibility Vitest | **14 passed** (4 pane-state + 10 accessibility) |
| Desktop panes Vitest | **2 passed** |
| Web `AccessibilityStyles` Vitest | **1 passed** |

### Three-pane race (logic)
1. Open panes A/B/C via `openPane` — session dedup focuses existing.
2. `claimLease(A)` succeeds; `claimLease(B)` returns `ok:false` with `ownerPaneId=A` **before** any Host submit.
3. Sidecar second `session.createInteractive` → `busy` + `owner_pane_id`.
4. Drafts remain pane-local via `setPaneDraft`.
5. `releaseLease(A)` then `claimLease(B)` succeeds.
6. Fresh state/UI tests preserve pane-local drafts, owner correlation, read-only posture, deterministic roving focus, and lease release/re-acquisition.

### T050/T055 Chromium matrix — valid v5
- Runtime: Chromium `151.0.7922.108`
- Fixture: `spec078-empty-profile-ui-keyboard-v5`; synthetic authenticated empty-profile UI
- Determinism: `**/v1/**` was intercepted with a fixed HTTP 503 response; this empty path issued **0** API requests
- Cases: **18 / 18 passed**
- Assertions: **234 passed**, **0 failures**, **0 captured console errors**
- Light: all six viewports (`1440×900`, `1024×768`, `768×1024`, `375×812`, `640×900`, `320×800`) in `en` and `zh-TW`
- Dark + reduced motion: `1440×900` and `375×812` in both locales
- Forced colors: `375×812` light in both locales
- Per-case checks: locale, body/document zero horizontal overflow, keyboard composer input, visible focus outline, keyboard Settings open/close with focus return, theme, reduced-motion media, and forced-colors media
- Ignored local evidence only: `.playwright-mcp/spec078-desktop-cowork/results.json` plus screenshots; these paths are not delivery candidates

### Gaps
- Packaged three-pane GUI smoke remains blocked until the T090-reviewed delivery candidate
- US4–US6 incomplete

<!-- US3-EVIDENCE END -->

## User Story 4 — presentation host + inspection (T057–T067 partial)

<!-- US4-EVIDENCE START -->

**Refreshed (local, 2026-08-10)**. Transport-neutral host interfaces, shared Web presentation extraction, Web/Desktop adapters, T066 host-owned projection integration, and T067 fresh shared/Web/Desktop convergence are current.

### Delivered
| Item | Path |
|------|------|
| T061 models/host | `packages/cowork-presentation/src/{models,host}.ts` |
| T057 conformance | `packages/cowork-presentation/src/__tests__/host.test.ts` |
| T058 Web baseline | `apps/web/src/__tests__/presentation-host.test.tsx` plus the eight named component/i18n regression files |
| T062 shared extraction | chat state, shell, messages, dialogs, inspection, settings shell, agent controls, i18n, and full Web CSS now live under `packages/cowork-presentation/src`; Web keeps thin wrappers/adapters |
| T063 Web adapter | `apps/web/src/presentation-host.ts` owns `ApiClient + SessionTransport`; `apps/web/src/App.tsx` delegates session, stream, interaction, inspection, settings, cost, and upload operations through the stable host |
| T064 sidecar | `apps/desktop/sidecar/methods/inspection.py` (`inspection.get`, `agentControls.get`, `capabilities.list/invokeAction` allowlist) |
| T064 IPC/preload | channels + handlers + `loopplaneDesktop.inspection/agentControls/capabilities` |
| T065 adapter | `apps/desktop/src/presentation-host.ts` (`DesktopPresentationHost`) |
| T066 integration | shared capability/settings/inspection projections, honest status labels, Desktop one-run permission draft, and typed `permission_mode` submit mapping |
| App wiring | Inspection sidebar, settings, capability actions, accepted posture, and one-run draft remain separated through Host projections |

### T058 pre-extraction contract
- The current Web composition root is exercised with injected `ApiClient + SessionTransport` seams before T062/T063.
- Session listing, session creation, submit, normalized progress, approval identity/decision, question identity/answers, and cancellation identity are locked at observable Web behavior.
- Dialog safety now explicitly locks backdrop→deny, Escape/backdrop question dismissal with zero answer, and zero-option-selection no-submit.
- The extraction key-space used by AppShell/InspectionPanel is checked as nonblank and translated in both `en` and `zh-TW`.
- Existing named suites retain shell overlay/focus behavior, message rendering/actions, inspection public fields, capability ownership/disclosure boundaries, and authoritative-vs-draft agent-control states.
- Fixture correction during the first focused run: the new session-list fixture initially used the wrong field shape and crashed `SessionRow`; it was corrected to the existing generated `session_id`/`label` contract and is not counted as product RED.

### T062 extraction and containment
- Shared source imports no `apps/web`, `ApiClient`, HTTP `/v1`, Electron, or sidecar RPC modules.
- Web-only `ApiClient` ownership remains in `apps/web` wrappers; the package receives transport-neutral loader/service/render props.
- Existing Web imports remain stable through thin wrappers; T063 `WebPresentationHost` was not implemented early.
- T055 focus APIs and dialog behavior were merged with existing Web modal/backdrop semantics; package entrypoint exports remain current.
- Main-agent inspection caught a blocking CSS extraction defect after the first build: the package stylesheet self-imported and had dropped the original Web CSS, producing only **1.30 kB**. A focused selector test was RED, then the full original Web stylesheet plus T055 additions was restored. The repaired production CSS is **30.05 kB** (gzip **6.15 kB**).

### T063 Web host boundary
- `WebPresentationHost` preserves exact session/request identity and transport error identity for submit, approval, question, cancel, history, and live progress.
- Renderer-owned subscriptions stop forwarding after unsubscribe; `teardown()` invalidates every remaining subscription without mutating server state.
- `App.tsx` contains no direct `ApiClient`, `ApiError`, `SessionTransport`, `client.*`, `transport.*`, or `host.webClient` product calls. Web-only wrappers receive the host and keep Web transport ownership outside shared presentation.
- Shared package source remains free of `apps/web`, `ApiClient`, `fetch`, `EventSource`, Electron, and sidecar imports.

### T066 projection and one-run draft
- Shared status rendering centrally preserves `available`, `read_only`, `priced`, `unpriced`, `partially_unpriced`, `unavailable`, and unknown values without inventing zero/allowed/configured states.
- Desktop cost/context/upload/artifact facets report explicit unavailable projections where V1 provides no authority; missing capability projection is an error rather than an empty success.
- Desktop permission selection remains a renderer-local draft, does not alter active/last-accepted posture, is mapped through the typed preload/main boundary to RPC `permission_mode` only on the next submit, and clears only after the accepted run completes. No-draft submit retains the original `{prompt}` shape.
- Electron main rejects a non-string permission draft before RPC dispatch; capability actions remain Host-allowlisted.

### Focused results
| Suite | Result |
|-------|--------|
| T066 shared projection RED→GREEN | initial `Unpriced` missing; final **3 passed** |
| T066 Desktop App/preload/IPC/host focused | **4 files / 17 tests passed** |
| T066 Web agent-control/settings focused | **3 files / 20 tests passed** |
| T063 direct host tests | **6 passed** |
| T058 exact 9-file Web regression set after T063 | **9 files / 56 tests passed** |
| Web full Vitest after T063 | **58 files / 202 tests passed** |
| cowork-presentation full Vitest after CSS repair | **5 files / 23 tests passed** |
| cowork-presentation typecheck | **PASS** |
| Web typecheck | **PASS** |
| Web production build | **PASS** (549 modules; CSS 30.05 kB) |
| `test_desktop_inspection_methods.py` + interaction + boundary | **14 passed** |
| Desktop inspection IPC + App | **17 passed** (focused) |

### T067 fresh convergence
| Gate | Fresh result |
|------|--------------|
| cowork-presentation typecheck | **PASS** |
| cowork-presentation full Vitest | **6 files / 26 tests passed** |
| Web typecheck | **PASS** |
| Web full Vitest | **58 files / 202 tests passed** |
| Web production build | **PASS** (551 modules; CSS 30.05 kB, gzip 6.15 kB) |
| Desktop typecheck | **PASS** after resolving strict IPC/process/state diagnostics without suppressions |
| Desktop full Vitest | **14 files / 63 tests passed**; two pre-existing React `act(...)` warnings remain visible |
| Desktop renderer production build | **PASS** (515 modules; JS 539.83 kB, gzip 164.80 kB; chunk-size warning only) |
| Chromium accessibility/regression | **18/18 cases; 234 assertions; 0 failures; 0 fresh console errors** on Chromium 151.0.0.0 |
| Diff hygiene | `git diff --check` **PASS**; CRLF normalization notices only |

- Chromium fixture: `spec078-empty-profile-ui-keyboard-t067-v2`; screenshots/results stay ignored under `.playwright-mcp/spec078-desktop-cowork-t067/`.
- The first attempted rerun was invalid harness evidence: the old Vite process exited and the locale locator was case-sensitive. It is excluded from product evidence. A fresh Vite server plus corrected locale/theme locators produced the matrix above.
- Full Desktop `npm run build` reaches and passes renderer `vite build`, then intentionally stops because `tsconfig.main.json` and `tsconfig.preload.json` do not exist yet. The approved plan assigns those emitted main/preload build configs to T085; T067 does not create them early or weaken the build script.

### Honesty
- Capability invoke allowlist is refresh-only for memory/skills/inspection
- No generic tool/MCP dispatch from Desktop presentation
- 078 still not Verified; US5–US6 open

<!-- US4-EVIDENCE END -->

## User Story 5 — audit + backup/restore (T073–T081)

<!-- US5-EVIDENCE START -->

**Refreshed (local, 2026-08-12)**. T068–T081 are PASS-current: checkpoint-derived audit, Host-owned backup/snapshot provenance, restore publication/handover, retained runtime/storage authority, the Electron and presentation facades, and the explicit Windows/POSIX convergence replay are complete. US6, Stage-C, final convergence, and maintainer completion approval remain open.

### Delivered
| Item | Notes |
|------|--------|
| T068/T073 | checkpoint-derived `host.list_turn_audit` / exact metadata-only `TurnAuditEntry`; no runtime-history projection |
| T068/T074 | cursor-based `audit.list` RPC + sender-validated IPC/preload/global typing |
| T069/T075 | Host-owned consistent SQLite backup plus read-only staged validation and checkpoint-referenced Gateway-artifact provenance; checkpoint/artifact payloads use bounded no-follow streaming |
| T069/T076 | acknowledged unencrypted disclosure; canonical ZIP/manifest/hash/path/type/depth/size/count/ratio checks; Project/safe-preference inclusion, draft/private-state exclusion, and atomic destination publication |
| T069/T076–T077 | `(owner, mutation identity)` Profile Mutation Lease gates every exposed session/interaction/Project/workspace/capability writer and competing backup/restore before dispatch; owning teardown starts no durable work |
| T069/T077 | validation-token ownership is bound to the exact restore lease identity; staged profile/Project/artifact inputs are revalidated before commit and reservations are released only by owning completion/cancel/expiry or teardown |
| T070 | public Host-validator, RestoreManager/BackupMethods, DesktopRuntimeOwner, and JSON-RPC seams carry focused contracts for streamed staging, token ownership/expiry/TOCTOU/teardown, named platform and transaction fault boundaries, dual-slot recovery, proof ambiguity, candidate-only post-commit I/O, and relink timing |
| T078 | dual full-preimage COW journals, pointer/proof publication, startup-only ambiguity adjudication, mutable runtime storage, active-profile principal ownership, Project/artifact consistency, no retained-generation guessing, and retryable candidate/previous Host cleanup are implemented through public restore/dispatcher seams |
| T071 | Electron handler/preload/global-typing RED contracts cover main-owned backup-save and restore-file choosers, disclosure/cancellation/sender/schema/token/path privacy, all five methods, exact fixed error rows, and sole-fallback rejection of malformed wire combinations |
| T079 | Shared sender authorization now protects every privileged IPC; the five backup/restore operations use exact plain-object inputs, path-free exact projections, structured-clone-safe envelopes, one unknown fallback, bounded opaque tokens, exact restore preview metadata, and a `Promise<void>` cancel facade. Runtime ownership cannot release the profile lock with a live Host; mapping construction preserves retained storage authority; Windows/POSIX cleanup uses retained deletion authority and fail-locks if the stale binding name is replaced or reappears. |
| T072 | Shared audit and Desktop backup/restore UI RED contracts cover metadata-only rendering, honest audit states, exact unencrypted-content disclosure, draft exclusion, acknowledgement, restore counts/reservation/confirmation/relink, and public-safe errors without renderer-visible archive paths |
| T080 | Shared metadata-only AuditView plus the Desktop backup/restore presentation and typed host adapter provide the exact disclosure, acknowledgement, restore preview/reservation/confirmation/progress/relink states, and fixed public-safe error projection. |
| T081 | Native Windows and Linux/WSL Python 3.12 matrices replay publication, COW/proof, rollback/fail-lock, Host handover, relink/draft/public-safety, and retained-storage boundaries. POSIX snapshot descendants are descriptor-anchored with first-acceptance-to-copy identity continuity. |

### T068 checkpoint audit contract
- Audit is derived only from durable `UserInputRecord`/`TerminationRecord` checkpoint records. It exposes deterministic opaque ID, session, ordinal, stable sequence, durable timestamp, completed/interrupted state, safe reason, and recorded turn count through an exact eight-field allowlist.
- Missing termination remains `interrupted` with reason/count `null`; no runtime event, prompt/model/tool/approval/question/principal/path/config/error payload is copied or inferred.
- Ordering is checkpoint sequence then deterministic ID. Cursor pagination is bounded to 1–100 and bound by current session/principal ownership; malformed, unknown, or cross-session cursors are rejected without enumeration.
- Reads are byte-stable/no-write across SQLite reopen. Fork audit belongs to the fork and does not mutate source audit.

### T069 backup/snapshot contract
- Backup owns the mutation lease before Host snapshot/profile serialization and through archive flush/publication; session create/rename/star/fork/delete, interactive open/submit/approval/question, Project mutation, Workspace bind/relink/remove/persisted revalidation, capability refresh, and competing backup/restore all return public-safe `busy` before Host/Profile/Store dispatch.
- The Host uses SQLite's backup API, validates snapshots through a dedicated read-only connection, and fails closed on missing, unreferenced, metadata-mismatched, replaced-call, linked/reparse, or identity-changing artifacts. Artifact metadata is bounded; checkpoint/artifact payloads are streamed rather than accumulated in memory.
- Archive validation requires canonical bounded JSON, one declared regular-file member per entry, central/local metadata parity, NFC/case-fold-safe paths, 2 GiB single-entry, 8 GiB aggregate, 10,000-entry, 8 MiB manifest, and 200:1 expansion limits. Pre-publication failure preserves an existing destination; a post-replace directory-flush failure is reported honestly as post-publication.
- The round trip independently reopens staged checkpoint records and proves matching principal, final starred metadata, user/model/tool/termination records, exact Project membership, safe preferences, draft exclusion, and byte-identical eligible artifact content. Host read-only validation leaves staged SQLite bytes unchanged.

### T070 restore RED contract
- The T025 public non-instance validator is kept narrowly responsible for injected pristine/initialized current-state probes. Both modes pass while monkeypatched Host, SQLite store, and ArtifactStore constructors remain unused and a sentinel generation tree remains byte/entry stable; pointer/proof/journal adjudication stays with `DesktopRuntimeOwner` startup tests.
- Validation RED cases now fail on missing product behavior rather than collection/fixture/platform setup: `extractall()` is forbidden; manifest ordering, duplicate/path/collision/type/compression/hash/short-read/exclusive staging, exact owning mutation, 15-minute expiry, archive-content TOCTOU, shutdown/restart cleanup, and all-writer pre-dispatch reservation are exercised through public manager/method/RPC seams.
- The test-owned named fault seam is attached without requiring a not-yet-existing constructor signature. Every POSIX, Windows, pre-proof rollback, post-proof cleanup, and proof-effect/pre-ack case asserts that its exact boundary was observed; failures therefore cannot all pass through one indistinguishable adapter call. Pre-authority faults require the exact prior pointer/proof pair, post-proof faults forbid candidate rollback, and the ambiguity case snapshots recovery/binding files at effect time and requires zero later mutation.
- Public RPC handover uses distinct source and destination Hosts/sessions. A successful commit must list only the restored source session and not the old destination session, so proof-file existence alone cannot satisfy candidate-only I/O.

### T078 restore publication and Host handover GREEN
- Restore publishes a canonical candidate generation, dual full-preimage journals, candidate pointer, serving Host swap, and independently matching proof in that order. Definitive pre-proof failures restore the exact prior pointer/proof pair; proof post-effect/pre-ack ambiguity freezes recovery/binding bytes for startup-only adjudication; post-proof cleanup failure never rolls back the authoritative candidate.
- Startup accepts only independently valid pointer/proof/journal authority. Missing authority with retained `restore-*` generations fails locked rather than guessing; pristine bootstrap remains available only when no restore authority or retained restore generation exists.
- Restored runtime storage is mutable and is the authority used for subsequent Project/session validation. Desktop create/resume binds to the active profile principal, rejects foreign-principal resume before replay, and preserves legacy `None` principal compatibility.
- Session deletion detaches the validated artifact tree before checkpoint deletion, keeps Project membership fail-safe, and uses anchored no-follow cleanup. Pre-effect checkpoint failure may roll back only while records prove survival; post-effect or indeterminate failure keeps deleted authorities consistent.
- Candidate readiness and pre-proof rollback retain a failed-to-close candidate Host and its storage for retry. Teardown attempts candidate, previous, and current Hosts, remains incomplete on any close/cleanup failure, and permits Profile Ownership Lock release only after a successful retry.
- The fresh R1 review over `runtime.py` → `durability.py` → `bridge.py` exception paths returned **PASS** with no blocking finding or blocking test gap.

### T071 Electron backup/restore RED contract
- `backup.describe`, acknowledged native `chooseAndCreate`, native `chooseAndValidateRestore`, `restore.commit`, and `restore.cancel` are exercised through trusted-sender handlers. Picker cancellation must return `null` with zero RPC; disclosure/input rejection and untrusted senders must occur before any picker or dispatch.
- Save/open paths exist only in main-owned chooser results and private sidecar params. Success projections deliberately include hostile `path`/`destination_path`/`source_path` fields from the test sidecar and require Electron main to remove them before renderer resolution.
- The complete backup/restore cause table is injected as wire errors and checked against exact Desktop category, retryability, required-or-absent recovery, and fixed `messageKey`. Internal-cause categories, unknown or mismatched code/category pairs, missing/extra/combined recovery, wrong retryability, and wrong/missing keys must collapse only to `internal_failure`/`desktop.error.internal_failure`/`true`/`restart_runtime` without raw message/path leakage.
- Preload/global source contracts require operation-specific `chooseAndCreate`/`chooseAndValidateRestore` methods and forbid renderer-facing `destinationPath`/`sourcePath` or Electron dialog APIs.

### T079 Electron facade and retained runtime authority GREEN
- One shared sender guard covers every privileged IPC. The five backup/restore handlers additionally require exact plain-object renderer inputs, exact success validation/projection, a bounded path-free `[A-Za-z0-9_-]{1,128}` restore token, and a structured-clone-safe `{ok,value}` / `{ok,error}` envelope.
- Restore validation exposes only `format`, exact `{major:1,minor:0}` version, canonical creation time, Project/session/artifact counts, required draft exclusion, and relink requirement. Internal entry/manifest/profile fields and all chooser/archive paths are removed. `cancelRestore` validates the sidecar success but resolves only `void` through main, preload, and global typing.
- Unknown or malformed success/error combinations collapse only to `-32603 internal_failure` / retryable / `restart_runtime` / `desktop.error.internal_failure`; fixed known rows retain exact category, retryability, required-or-absent recovery, and `messageKey` without raw cause labels.
- `DesktopRuntimeOwner.release()` refuses to release Profile Ownership Lock while a current Host remains. Direct attachment closes through `close_host()`; dispatcher handover updates the same owner authority and clears it only after successful Host teardown.
- `RuntimeConfig.from_mapping()` preserves the programmatic `StorageAuthorityFactory`. Windows retains shared profile/collection plus per-generation handles with retryable partial close; POSIX storage operations remain rooted in retained descriptors.
- Stale workspace binding cleanup no longer performs path-only deletion. Windows deletes the exact validated file HANDLE; POSIX unlinks relative to retained root/private descriptors. Both paths verify parent identity and exact-child absence after deletion, fail-lock if the parent is replaced or the name reappears, and preserve an external sentinel in both adversarial regressions.
- Final fresh code review and final fresh architecture review both returned **PASS — no blocking findings**.

### T072 audit/backup/restore presentation RED contract
- `AuditView` is resolved through the shared package's public entrypoint so the missing export is an intentional product RED rather than a module-resolution or TypeScript failure. The contract renders only the eight allowlisted logical-turn fields and injects prompt/model/tool/private-path fields that must remain absent from the audit region.
- Audit loading, empty, and unavailable states require honest `status`/empty/`alert` projections instead of silent blank content.
- Desktop tests enter backup/restore only through the public `App` composition seam and a typed `window.loopplaneDesktop.backup` facade. Backup creation remains disabled until the explicit unencrypted acknowledgement and must disclose user/model/tool conversation content, eligible artifacts, and unsent-draft exclusion before invoking the native chooser operation.
- Restore validation must project only opaque token-derived summary data: Project/session/artifact counts, active reservation, draft exclusion, explicit replacement confirmation, and relink-required state. Fixed Desktop error metadata may drive the UI, while raw error text and private archive paths must never render.

### T080 audit/backup/restore presentation GREEN
- Shared `AuditView` is exported through the transport-neutral package entrypoint and renders only the eight allowlisted logical-turn metadata fields. Prompt, model output, tool output, and private path extras remain absent; loading, empty, and unavailable states are explicit.
- `DesktopPresentationHost` adapts typed audit and backup/restore facade operations without exposing Electron channels, RPC envelopes, mutation IDs, chooser paths, or archive paths to presentation components. The public App loads audit pages only for the active session.
- `BackupRestoreView` blocks backup creation until the exact V1 unencrypted-content acknowledgement is checked. The disclosure states lossless user/model/tool conversation and eligible-artifact retention, sensitive-content risk, unsent-draft exclusion, LoopPlane-private exclusions, destination responsibility, and integrity-hash limitations.
- Restore validation presents only Project/session/artifact counts, reservation ownership, draft exclusion, replacement confirmation, and relink-required state. Validation/backup/commit/cancel progress is explicit; rollback/busy/retry/restart/contact-support outcomes come only from a fixed `messageKey` allowlist, while raw `Error.message` and private paths are never rendered.

### T081 Windows/POSIX convergence and retained-snapshot closure
- The final native Windows matrix exercises the Desktop RPC/public-safety, audit, backup, restore, profile/workspace, generation publication, runtime bootstrap, profile ownership, ArtifactStore, SQLite checkpoint, and Host-config seams: **370 passed, 11 skipped**. The skips are explicit POSIX-only descriptor tests plus symlink creation unavailable on this Windows configuration.
- The final Linux matrix ran under WSL with Python 3.12 on a true Linux `/tmp` base and the same source checkout: **363 passed, 19 skipped**. Every skip is an explicit Windows-only case-alias, junction, retained-handle, or retained-directory boundary.
- The snapshot-focused replay is **9 passed, 9 skipped** on Windows and **18 passed** on Linux. Arbitrary callback-authorized symlink roots remain rejected; exact retained `/proc/self/fd/<fd>` roots are accepted only as prevalidated capabilities.
- Reviewer-driven adversarial RED/GREEN slices closed five replacement windows across seven cases: checkpoint replacement before descriptor open and during SQLite backup; artifacts-ancestor replacement after open; legal session/artifacts replacement between inventory and copy; and legal session/artifacts replacement between first descriptor-relative `lstat` and no-follow open.
- Retained checkpoint backup now duplicates the exact root descriptor, performs descriptor-relative `lstat` plus `O_NOFOLLOW` open/`fstat` identity binding, reads SQLite through the exact opened descriptor, and rechecks the pathname identity after backup. Retained artifact inventory saves session, artifacts-directory, payload, and metadata identities; copy reopens every descendant relative to retained parent descriptors, compares against the inventory identities, streams bounded no-follow files, and rechecks ancestors before success.
- The final fresh C3 code review returned **PASS — no blocking findings** after two earlier fresh reviews identified and drove closure of the identity-reacquisition gaps.
- T081 power-loss/process-crash evidence is deterministic injection at the named POSIX fsync/rename and Windows flush/write-through/move/reopen/API boundaries. It is not claimed as a physical power-cut, kernel-crash, or hardware fault experiment. Windows process-crash behavior remains bounded by the documented API/reopen test seam.
- The temporary WSL uv/Python/venv/cache/install files and all `/tmp/loopplane-t081*` directories created solely for this replay were removed after the final matrix and review passed.

### Focused results
| Suite | Result |
|-------|--------|
| T068 Host/durability/sidecar Python | **18 passed** |
| T068 Electron audit IPC/preload/typing | **3 passed** |
| T068 selected Ruff format/check | **PASS** |
| T068 selected Host mypy | **PASS** |
| Desktop typecheck after audit facade | **PASS** |
| T069 final Host/sidecar/round-trip/public-safety set | **76 passed, 1 skipped** (symlink creation unavailable on this Windows configuration) |
| T069 changed-file Ruff format/check | **PASS** |
| T069 `mypy src/loopplane/host/snapshot.py` | **PASS** |
| T069 `git diff --check` | **PASS**; CRLF normalization notices only |
| T070 Host/restore unit + public RPC RED matrix | **50 failed, 13 passed**; zero collection/fixture failures and no platform skips |
| T070 selected Ruff format/check | **PASS** |
| T070 `git diff --check` | **PASS**; existing CRLF normalization notices only |
| T078 candidate cleanup lifecycle RED | **2 failed** at the public restore/teardown assertions: readiness failure removed storage while losing the Host reference; pre-proof rollback close failure allowed teardown to succeed |
| T078 candidate cleanup lifecycle GREEN | **2 passed**; adjacent candidate/previous/rollback lifecycle matrix **6 passed** |
| T078 Host/restore unit + public RPC matrix | **103 passed** |
| T078 ArtifactStore + Desktop sidecar matrix | **12 passed** |
| T078 focused Host/Desktop matrix | **193 passed, 1 skipped** (existing platform-dependent skip) |
| T078 changed-file Ruff format/check | **PASS** |
| T078 runtime scoped mypy | **PASS** with imports skipped and the file's existing fallback-import `unused-ignore` diagnostics excluded; direct standalone sidecar-graph invocation remains non-green on existing sibling/fallback import diagnostics and is not claimed as T093 broad mypy evidence |
| T078 `git diff --check` | **PASS**; existing CRLF normalization notices only |
| T078 fresh R1 lifecycle review | **PASS**; no blocking finding or blocking test gap |
| T071 Desktop typecheck with new tests | **PASS** |
| T071 Electron handler/preload RED matrix | **19 failed, 17 passed**; failures are native chooser, path-free facade, exact-row absence/category normalization, and malformed-wire containment gaps |
| T071 `git diff --check` | **PASS**; existing CRLF normalization notices only |
| T079 Electron audit/backup/restore IPC + preload | **56 passed** |
| T079 Desktop typecheck | **PASS** |
| T079 config/runtime/restore/backup/durability/sidecar/artifact/checkpoint Python matrix | **284 passed, 3 skipped** (current Windows platform; T081 owns the explicit cross-platform replay) |
| T079 selected Ruff format/check | **PASS** |
| T079 `mypy src` | **PASS — 205 source files** |
| T079 task-scoped `git diff --check` | **PASS** |
| T079 final fresh code review | **PASS — no blocking findings** |
| T079 final fresh architecture review | **PASS — no blocking findings** |
| T072 shared/Desktop typecheck | **PASS** |
| T072 shared `AuditView` RED contract | **2 failed**; both fail on the absent public `AuditView` export, with no compile or fixture failure |
| T072 Desktop `App` backup/restore RED contract | **3 failed**; all reach the public App seam and fail on the absent accessible Backup and restore entry point, with no compile or fixture failure |
| T072 `git diff --check` | **PASS** |
| T080 shared `AuditView` GREEN contract | **2 passed** |
| T080 Desktop backup/restore GREEN contract | **3 passed** |
| T080 Desktop App/presentation regression | **14 passed** (3 files) |
| T080 shared + Desktop typecheck | **PASS** |
| T080 task-scoped `git diff --check` | **PASS** |
| T081 retained replacement RED history | **7 failing cases observed at their owning race windows**; no collection, fixture, or environment failure |
| T081 retained replacement focused GREEN | **7 passed** |
| T081 snapshot replay — Windows | **9 passed, 9 skipped** |
| T081 snapshot replay — Linux/WSL Python 3.12 | **18 passed** |
| T081 full Python matrix — Windows | **370 passed, 11 skipped** |
| T081 full Python matrix — Linux/WSL Python 3.12 | **363 passed, 19 skipped** |
| T081 selected Ruff format/check | **PASS** |
| T081 `mypy src/loopplane/host/snapshot.py` | **PASS** |
| T081 final fresh C3 code review | **PASS — no blocking findings** |
| T081 temporary WSL environment cleanup | **PASS**; exact approved uv/Python/venv/cache/install and `/tmp/loopplane-t081*` paths absent after cleanup |

### Deferred
- T093's final broad gate has not run. The T079-scoped `uv run mypy src` is green; direct standalone sidecar-graph invocation still has existing sibling/fallback-import diagnostics and is not claimed as T093 evidence.

### Honesty
- T070's original **50 failed, 13 passed** result is retained as test-first history. T078 supersedes its assigned Python publication/handover failures; T079 supersedes T071's native chooser/path-free facade/exact error-row RED evidence; T080 supersedes T072's shared/Desktop presentation RED evidence.
- The T080 focused Desktop regression still emits the existing asynchronous App initialization `act(...)` warnings in one run-lifecycle test; all 14 product assertions pass, and the warning is not claimed as a T080 failure or as resolved test hygiene.
- T081 supersedes the earlier Windows-only T079 platform note. The final replay used native Windows plus temporary WSL Python 3.12 on Linux `/tmp`; platform-specific skips are listed explicitly above. The temporary WSL test environment was removed after the final PASS.
- Named fsync/flush/rename/write-through/reopen/API fault injection is the recorded power-loss/process-crash evidence; no physical power interruption or kernel crash was performed or claimed.
- The default Host snapshot provider remains unavailable; Desktop explicitly opts into the Host-owned SQLite provider.
- T078–T081 are PASS-current only for their declared restore/publication/handover/facade/storage-authority/presentation/platform-convergence scopes. US6, Stage-C, final convergence, and maintainer completion approval remain open; 078 is not Verified.

<!-- US5-EVIDENCE END -->

## User Story 6 — independent Desktop delivery (T082–T090)

<!-- US6-EVIDENCE START -->

**Refreshed (local, 2026-08-12)**. T082–T089 are complete through the RED contracts, packaged driver, failure-scenario extension, token-free wrappers, explicit renderer/main/preload source emits, delivery materialization/reassertion, isolated sidecar freeze route, Electron-builder alignment, fail-closed Windows delivery workflow, and packaged-only smoke source composition. Stage-C review and every first freeze/package/smoke remain open.

### T082 delivery-route RED contract

- `apps/desktop/electron/__tests__/packaging.test.ts` fixes the accepted Desktop manifest/sole-root-lock baseline, renderer/main/preload emitted-output paths, electron-builder resource alignment, descriptor-only package and sidecar routes, Windows delivery-step ordering, immutable T002/T005/T090 locators, tokenized-verifier/token-free-build separation, complete artifact-determinant path filters, and the external-CWD/checkout-path smoke boundary.
- `tests/contract/test_desktop_delivery_gate.py` extends the public PowerShell `-SelfTest` seam with delivery-descriptor materialization/reassertion cases plus package/sidecar sentinel cases for missing or stale authority, all three forbidden credential variables, reviewed dependency/source snapshots, checkout source/lock replacement, PATH/global/bare PyInstaller, sole sidecar delegation, and descendant environment scrubbing.
- Both wrapper live-entry contracts require `credential_environment_forbidden` before descriptor access whenever `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN` exists, while retaining the existing no-token/header/raw-body disclosure assertions.
- RED is at the owned product boundaries: the verifier does not yet implement the five delivery materialization/reassertion cases; both canonical wrappers and the smoke driver were absent at the T082 observation; main/preload emit configs and builder alignment are absent; and `.github/workflows/desktop.yml` remains the legacy Linux/apps-only source gate. There were no TypeScript collection, Python fixture, parser, or typecheck failures.

### T083 packaged UI Automation driver RED

- `scripts/smoke-desktop-artifact.ps1` now owns the exact external-path CLI, canonical checkout app/scratch/evidence/generated-profile/CWD rejection, ambient Python/Node and authority-token clearing, Windows built-in `UIAutomationClient`/`UIAutomationTypes`, unique Name/ControlType preflight, ordinary Value/Invoke/Window patterns, bounded happy-path submit/marker/close/relaunch flow, and create-new bounded non-secret evidence. It contains no Playwright/Appium/WinAppDriver, AutomationId, remote-debugging/DevTools, or raw hidden-control route.
- Seven public `-SelfTest` cases execute from the OS temporary directory without launching an application. They prove accepted external CWD, each checkout-contained path/CWD rejection, and `PYTHONPATH`/`NODE_PATH` clearing without disclosing checkout paths.
- The only remaining focused RED is the public application composition seam: Electron main does not yet expose the packaged-only bounded scenario, packaged-only accessibility enablement, or external smoke profile; the sidecar packaged entry point does not yet compose `ScriptedModel`; and the seven ordinary visible presentation controls/terminal marker are not yet present. Those behaviors belong to T089, so no source-mode substitute or fake packaged success is introduced.

### T084 failure-scenario driver extension

- The driver now accepts exactly `happy`, `missing-sidecar`, `corrupt-sidecar`, `incompatible-sidecar`, or `all`. `all` runs the four concrete scenarios serially with distinct `profile-<scenario>` directories below the validated external scratch root.
- Missing/corrupt/incompatible variants alter only the copied external `resources/sidecar/loopplane-sidecar.exe`. The accepted bytes are moved to a unique sibling backup, and a `finally` path removes the variant and restores the exact accepted file; focused self-tests verify byte restoration for all three variants. The incompatible case compiles a bounded built-in C# console helper that answers the handshake with an unsupported protocol version.
- Each failure variant waits at most 10 seconds for text below the unique `LoopPlane smoke runtime diagnostic`/Group, rejects executable/scratch/profile disclosure, closes through WindowPattern, preserves the fresh scenario profile, and records only bounded result enums/timing/pair inventory/orphan-listener booleans. Diagnostic text and exception details are not written to evidence.
- The extended Python driver contracts are GREEN except for the same intentional T089 application-composition RED. The Desktop packaging contract's failure-scenario route is also GREEN; the latest replay has four failures owned by T086/T087/T088.

### T085 token-free complete package route and Electron emits

- `scripts/build-desktop-package.ps1` is the sole complete package wrapper. Before reading a descriptor it rejects non-empty `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN`; all child processes inherit a process environment from which those names were explicitly removed.
- The wrapper accepts only a versioned `delivery` descriptor with pairwise-distinct T002/T005/T090 review IDs, a timestamp no older than 15 minutes and not in the future, descriptor paths below one materialization root, and the verifier's offline materialized-input assertion. It copies only reviewed Desktop/Web/shared source into a fresh GUID root, rejects reparse inputs, excludes local locks and mutable/generated state, hash-checks and create-new installs the accepted root/Web/Desktop/shared manifests plus sole root lock, and delegates freeze exactly once to the canonical sidecar wrapper.
- `apps/desktop/vite.config.ts` emits renderer assets to `dist`, bundled Electron main to `dist-electron/main.js`, and sandbox-compatible CommonJS preload to `dist-electron/preload.cjs`. `tsconfig.main.json` and `tsconfig.preload.json` provide explicit source checks without changing the accepted manifest or root lock. The actual source build completed and produced all three output classes; no package/freeze/smoke was invoked.
- The package wrapper invokes `npm ci`, shared typecheck, Web build, Desktop build, the canonical sidecar wrapper, and only then the accepted Desktop `dist` script. Its bounded result is create-new and contains only build/output paths plus the descriptor SHA-256. T086 now supplies materialized-input reassertion and the sidecar route; production execution remains intentionally blocked by T087–T090.

### T086 accepted-input materialization and isolated sidecar freeze route

- Delivery verifier mode can now materialize a fresh external GUID root only when explicit delivery mode, descriptor path, and the immutable T002/T005/T090 locator chain have passed. It compares every non-tree T002/T005 leaf, rejects symlink/gitlink/type/mode drift, requires accepted T005 manifests/root lock/Python authorities to remain byte-identical in T090, rejects app-local locks and tracked generated outputs, and selects only the bounded delivery determinant tree.
- Reviewed blobs are read from the local Git object database through non-interactive `git cat-file --batch`; each returned byte sequence is recomputed as a Git blob before create-new materialization. A focused regression exposed the Windows PowerShell redirected-input BOM/first-request defect, and the final batch protocol consumes a sacrificial missing-object query before binding every real object ID.
- The verifier writes separate reviewed-source and accepted-dependency trees, a bounded hashed inventory, and a bounded descriptor containing all three review/commit/tree identities plus delivery-bundle/root-lock/PyInstaller-lock digests. Every materialized file and descriptor is read-only; offline assertion rejects stale/future descriptors, reparse entries, additions, missing files, path/property mismatches, writable files, or digest mutation.
- `scripts/build-desktop-sidecar.ps1` rejects all three credential environments before descriptor access, clears inherited Python paths, reasserts materialized inputs before source copy and immediately before freeze, and copies only descriptor-reviewed `src/loopplane` plus `apps/desktop/sidecar`. Accepted `pyproject.toml`, `uv.lock`, and the exact PyInstaller lock are hash-checked and create-new installed into a fresh GUID build root.
- The sidecar wrapper exports only `anthropic`, `gemini`, `mcp`, `net`, `oauth`, and `openai`; creates Python 3.12; strictly syncs hashed wheels from the runtime export plus accepted build lock; runs `uv pip check`; requires isolated `.venv/Scripts/pyinstaller.exe` version `6.21.0`; and invokes the hardened reviewed spec. `loopplane-sidecar.spec` derives only sealed `SPECPATH` roots and `apps/desktop/sidecar/__main__.py` is the sole packaged entrypoint. No PATH/global/bare PyInstaller route remains.

### T087 Electron-builder alignment

- Without changing the accepted Desktop manifest or any lock, `electron-builder.yml` now packages only the T085 renderer `dist/**/*` and Electron `dist-electron/**/*` output trees. The obsolete nonexistent `electron/**/*.js`/`electron/**/*.cjs` source-output assumptions were removed.
- `extraResources` consumes exactly the package wrapper's `apps/desktop/sidecar/dist/loopplane-sidecar.exe` and places it under packaged `resources/sidecar`, matching the existing runtime resolver. Output remains the accepted unsigned Windows delivery path; no package command was executed.

### T088 Windows source and delivery workflow

- `.github/workflows/desktop.yml` now has workflow-level read-only contents/pull-request permissions and complete push/PR path filters over root npm/Python authorities, Desktop/Web/shared/Host/test sources, all four delivery scripts, ADR 0015, the 078 spec tree, and the workflow itself. The Windows source job uses the sole root lock and runs Python delivery contracts plus shared/Web/Desktop clean-install source gates.
- Only a submitted `pull_request_review` whose event state is approved can enter the Windows delivery job. Checkout is pinned to `github.event.review.commit_id` with credentials not persisted; the job rechecks exact `HEAD`, runs full Python and shared/Web/Desktop source gates, and performs no freeze/package/smoke before the isolated verifier step.
- The verifier step alone maps `${{ github.token }}` to `LOOPPLANE_STAGE_B_GITHUB_TOKEN`, receives T002/T005 locators and expected approver only from maintainer-controlled repository variables, receives T090 review/commit from the event, and writes only external run-root/descriptor paths to later step environment. The following step removes/checks all three token variables before invoking the sole package wrapper.
- After a successful token-free package, the workflow copies only `win-unpacked` to the external GUID run root and invokes the built-in UI Automation driver with `-Scenario all` from that root. It does not use `pull_request_target`, merge refs, event actor identity, evidence text, or repository files as approval authority.
- **Correction (2026-08-14).** As written for T088 the step established that working directory with `Push-Location $runRoot`, which moves only the PowerShell provider location and leaves the process working directory at the checkout. The driver asserts on `[System.IO.Directory]::GetCurrentDirectory()`, so every delivery run failed closed with `checkout_cwd_forbidden` roughly two seconds after packaging and never reached UI Automation at all. The Vitest contract that claimed to cover this property asserted the presence of `Push-Location $runRoot` — the construct that cannot establish it — and was therefore a false green. The step now launches the driver through `Start-Process -WorkingDirectory $runRoot`, and the contract pins that out-of-process working directory while rejecting a `Push-Location` invocation.

### T089 packaged-only source composition

- Electron main accepts only the four allowlisted `--loopplane-packaged-smoke=<scenario>` values on a packaged launch, requires the external profile variable, enables accessibility only after `app.whenReady()` for that accepted smoke mode, and explicitly clears the sidecar scenario environment on normal launches. The renderer never receives profile/scenario paths or a smoke control channel.
- The packaged sidecar entrypoint keeps `ScriptedModel` in the sealed freeze graph, while the existing sidecar bridge selects the exact `loopplane-packaged-smoke-ok` response through the normal Host/event/presentation path. `SidecarRpcClient` now rejects protocol name/version mismatch before becoming ready.
- The seven fixed Name/ControlType pairs are attached to the ordinary visible status, new-session, prompt, submit, latest-outcome, session-list, and runtime-diagnostic controls. The diagnostic Group remains in the accessibility tree when healthy without announcing an alert; failure diagnostics arrive through the existing typed main-to-preload-to-renderer status subscription.
- The driver rejects healthy diagnostic/session placeholders, waits within the existing deadlines for a real public-safe failure and persisted restart history, emits valid incompatible-sidecar JSON, and rejects reparse/junction aliases across executable, scratch, evidence, generated profile, and CWD paths. Source contracts continue to reject hidden IPC/RPC, local listener, AutomationId, DevTools, remote debugging, renderer-visible smoke environment, or private-path diagnostics.
- Architecture review initially found four blocking source contradictions (hidden healthy diagnostic Group, missing diagnostic-window owner, invalid incompatible JSON, ambient scenario inheritance) and then three follow-up concerns (placeholder false green, fixed-name interpretation, reparse alias). The technical contradictions were repaired with focused RED→GREEN contracts; the fixed names were retained because T089 explicitly requires them on the same ordinary visible controls rather than hidden smoke nodes. A fresh architecture re-review returned **PASS** for C1–C5. The preselected `claudex-code-reviewer` could not run because the current Claude Code permission rules explicitly deny that role; no code-review PASS is claimed.

### T090 Stage-C delivery review and first packaged delivery execution

#### Authority chain (refetched 2026-08-14)

| Gate | Review ID | State | Reviewed commit | Approver |
|------|-----------|-------|-----------------|----------|
| T002 bootstrap | `4864730949` | APPROVED | `5319634a7e5c77b21ffa5355595fae18f9d82083` | `norton777930` |
| T005 final | `4864943765` | APPROVED | `8fe0a00400abfbf6eb466c9dec9c21bf0352b8fb` | `norton777930` |
| T090 delivery | `4934698622` | APPROVED, submitted `2026-08-14T06:53:43Z` | `88e6f71ce64f40b62e8a4aeb5212c7384ccdbf74` | `norton777930` |

- All three IDs are pairwise distinct and belong to the same pull request (`norton77930/loopplane#3`). The delivery `commit_id` equals the pull-request head at review time.
- C2 self-approval rule is satisfied by default author inequality: the approver is `norton777930` (id 266602944) and the pull-request author is `norton77930` (id 75159321). `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` was not required.
- Two earlier delivery-review attempts are explicitly **not** authority and were superseded: `4916022110` is `COMMENTED`, not approved, despite a body naming a T090 approval; `4934293943` is a genuine approval but on the superseded commit `f6383f6`, whose delivery run failed.

#### Delivery execution

- Review `4934698622` triggered the required Windows `pull_request_review` delivery run **`31777897368`**, which completed **`success`** — the first successful run of that job. Steps: reviewed-source recheck, Stage-C verification with accepted-input materialization, and token-free package/freeze/external UI Automation smoke all `success`; the packaging-through-smoke step ran `2026-08-14T07:01:15Z` to `2026-08-14T07:05:33Z`.
- The step checks every failure mode explicitly (`credential_environment_forbidden` on any of the three token variables, `desktop_package_failed`, `win_unpacked_missing`, `desktop_smoke_failed` on the driver exit code), and the driver reaches `exit 0` only after every requested scenario passes and bounded evidence is written. Its success therefore attests that `-Scenario all` completed over the packaged artifact.
- The packaged application's own standard error appears twice in that step as `No handler registered for 'lp:app:status'`, the known signature of the missing-sidecar and corrupt-sidecar branches, confirming the artifact was actually launched through the failure scenarios rather than skipped.
- Preceding failed delivery runs on this branch: `31733415393` (`121f1c9`) and `31773635982` (`f6383f6`), both `FAIL packaged_smoke_failed` about two to three seconds after packaging.

#### Local packaged-artifact evidence

Driver `scripts/smoke-desktop-artifact.ps1`, invoked from an external working directory over a fresh external copy of `win-unpacked` (artifact `ffcebdd60543801fc7986280beaed7231ce520e03913a72216b72d45203b85f5`), fresh `ScratchRoot` and `EvidencePath` per run:

| Run | Scenario | Exit | Recorded result |
|-----|----------|------|-----------------|
| 1 | happy, first launch of an uncached copy | 0 | `passed`, 21811 ms |
| 2 | happy, fresh scratch | 0 | `passed`, 17690 ms |
| 3 | all | 0 | happy 19618 ms, missing 5199 ms, corrupt 5944 ms, incompatible 6961 ms |
| 4 | all, repeat | 0 | happy 19233 ms, missing 4525 ms, corrupt 5284 ms, incompatible 7842 ms |
| 5 | happy, repeat | 0 | `passed`, 26280 ms |

- Every run recorded exactly one instance of each fixed pair: `LoopPlane smoke runtime status`/Group, `LoopPlane smoke new session`/Button, `LoopPlane smoke prompt`/Edit, `LoopPlane smoke submit`/Button, `LoopPlane smoke latest outcome`/Group, `LoopPlane smoke session list`/List, `LoopPlane smoke runtime diagnostic`/Group.
- Every run recorded `orphan=false`, `listener=false`, `profile_preserved=true`, `copied_sidecar_restored=true`; every failure scenario recorded `failure_profile_unchanged=true`; the copied sidecar's SHA-256 was byte-identical after each run and no LoopPlane or sidecar process survived.
- All three failure diagnoses landed inside the fixed ten-second window: 4525–5199 ms missing, 5284–5944 ms corrupt, 6961–7842 ms incompatible.
- Checkout-CWD rejection was reproduced deliberately: invoking the same driver from a process whose working directory is the checkout fails closed with `checkout_cwd_forbidden` in 979 ms.

#### Defects found and repaired before the gate could pass

Each was identified from an exact failure code obtained through a local diagnostic copy of the driver that prints the underlying exception instead of the fixed public code, plus a millisecond-level probe of window, locator-cardinality, and status transitions.

| Exact code | Defect | Repair |
|------------|--------|--------|
| `runtime_not_usable` | The sidecar handshake was serialized after the renderer load, spending the same acceptance budget twice | Start the handshake alongside Electron and renderer startup |
| `runtime_not_usable` | `Update-ProcessNetworkObservation` cost 1.9–3.7 s per sample (`Get-NetTCPConnection` 1074–2712 ms, `Get-CimInstance Win32_Process` 793–1034 ms) inside the deadline-bounded waits, so the window measured the harness rather than the artifact | Replace both with built-in `GetExtendedTcpTable` and `CreateToolhelp32Snapshot`; per-sample cost falls to about 58 ms and recorded `observation_samples` rise from 15 to 71–88 |
| — | A cold packaged start could not answer `initialize` inside `SIDECAR_WARMUP_MS` plus the default 5 s deadline, reporting a healthy runtime as unavailable | Add `SIDECAR_INIT_TIMEOUT_MS = 7_000`, keeping the app's own handshake deadline at 9.5 s, inside the unchanged 10 s acceptance window |
| `uia_locator_timeout` | On Windows `spawn()` throws synchronously when the bundled executable is present but not loadable, so a corrupt sidecar escaped `createWindow` as an unhandled main-process error and no renderer was created | Move `spawn()` inside the existing visible-diagnostic `try` |
| `runtime_diagnostic_timeout` | The failure path reloaded a renderer that had already mounted, destroying the frame holding its status subscription, so the one-shot diagnostic was delivered to nothing | Send directly to a renderer that already loaded; only load a window that never started |
| `checkout_cwd_forbidden` | `Push-Location` in the delivery workflow does not change the process working directory (see the T088 correction above) | Launch the driver with `Start-Process -WorkingDirectory` |

Cross-checks for the replaced observation primitives: the parent table agreed with `Win32_Process` on all 737 common process IDs with zero parent mismatches, discovered a freshly spawned child, and reported no non-existent PID; the listener table agreed with `Get-NetTCPConnection` at 46 owning PIDs versus 46 with none missing and detected the probe's own listener. Timings: 37 ms versus 1282 ms, and 21 ms versus 2721 ms.

The fixed ten-second acceptance deadline was not changed.

### Focused results

| Suite | Result |
|-------|--------|
| T082 Python delivery contract RED | **31 failed, 40 passed**; failures are five unknown verifier delivery-materialization cases, two missing wrappers, their sentinel contracts, and six live forbidden-token entry checks |
| T082 Desktop packaging contract RED | **7 failed, 1 passed**; the accepted manifest/root-lock baseline passes, while emitted configs, builder alignment, wrappers, Windows delivery workflow, and smoke boundary remain absent |
| T082 Desktop typecheck | **PASS** |
| T082 selected Ruff format/check | **PASS** |
| T083 initial driver RED | **10 failed** because the canonical driver was absent |
| T083 driver/path/environment contracts | **9 passed** after adding the driver and public self-tests |
| T083 packaged application composition RED | **1 failed** at the absent `--loopplane-packaged-smoke=` Electron seam; no collection, fixture, parser, or environment failure |
| T083 selected Ruff format/check | **PASS** |
| T083 task-scoped whitespace checks | **PASS** |
| T084 initial failure-scenario RED | **8 failed, 9 passed**; six absent failure self-tests, absent scenario-matrix source contract, and the existing application-composition RED |
| T084 extended driver contracts | **16 passed**; path/environment, scenario set, exact restore, fresh profiles, bounded evidence, and built-in incompatible-helper compilation |
| T084 packaged application composition RED | **1 failed** at the unchanged T089-owned Electron seam |
| T084 Desktop packaging contract | **3 passed, 6 failed**; both smoke-boundary tests pass, remaining failures are emitted outputs/wrappers/workflow |
| T085 future-descriptor RED | **1 failed** because the package wrapper did not yet declare the public `reject-future-descriptor` self-test |
| T085 package-wrapper boundary | **14 passed, 58 deselected**; canonical path, ten public self-tests, and three live token-before-descriptor cases |
| T085 Desktop packaging contract | **5 passed, 4 failed**; accepted metadata/emitted configs/package wrapper/smoke route pass, with only T086 sidecar, T087 builder, and T088 workflow RED remaining |
| T085 Desktop typecheck + source build | **PASS**; renderer `dist`, main `dist-electron/main.js`, and preload `dist-electron/preload.cjs` emitted |
| T085 task-scoped whitespace checks | **PASS** |
| T086 initial verifier/sidecar RED | **18 failed, 54 passed**; five unknown materialization cases plus absent sidecar wrapper/self-tests/live token boundary |
| T086 Git batch protocol RED/GREEN | unknown self-test RED, then real `git_batch_object_mismatch` RED on the first Windows batch request; sacrificial-query protocol GREEN **1 passed** |
| T086 complete delivery contract | **74 passed**; verifier materialization/reassertion, both wrappers, future/stale authority, token-first failure, checkout/PATH/global/bare sentinels, and local Git blob identity |
| T086 Desktop packaging contract | **6 passed, 3 failed**; sidecar wrapper/spec/entrypoint route passes, leaving only T087 builder and T088 workflow RED |
| T086 `uv` CLI option inspection | **PASS**; export, multi-source strict hash sync, interpreter selection, and venv path options are supported by the accepted local `uv` |
| T086 entrypoint Ruff + spec AST parse | **PASS** |
| T086 task-scoped whitespace checks | **PASS** |
| T087 Desktop packaging contract | **7 passed, 2 failed**; builder outputs/sidecar resource alignment pass, with only both T088 workflow cases RED |
| T087 task-scoped whitespace checks | **PASS** |
| T088 Desktop packaging contract | **9 passed**; immutable review authority ordering, complete determinant filters, token-step isolation, and external-CWD `-Scenario all` workflow contracts |
| T088 linked Python delivery contract | **74 passed**; materialization and both token-free wrapper boundaries remain current after workflow integration |
| T088 Desktop typecheck | **PASS** |
| T088 task-scoped whitespace checks | **PASS** |
| T089 packaged smoke source contracts | **22 passed**; CLI/profile/scenario containment, ordinary visible UIA pairs, legal incompatible helper, placeholder rejection, restart history, reparse-path rejection, and hidden-channel negatives |
| T089 Desktop focused Vitest | **41 passed** across App, sessions, sidecar RPC, main security, and packaging; the existing cancel-run test still emits two non-failing React `act(...)` warnings |
| T089 shared focused Vitest | **16 passed** across accessibility and panes, including healthy diagnostic Group accessibility-tree presence |
| T089 Desktop + shared typecheck | **PASS** |
| T089 selected Ruff format/check | **PASS** |
| T089 task-scoped whitespace checks | **PASS** |
| T089 architecture re-review | **PASS** for C1–C5 after repairing all blocking source findings |
| T089 code review | **BLOCKED** by an explicit Claude Code permission rule denying `Agent(claudex-code-reviewer)`; no PASS claimed |
| T090 delivery run `31777897368` | **success**; reviewed-source recheck, Stage-C verification with accepted-input materialization, and token-free package/freeze/external `-Scenario all` smoke all green |
| T090 packaged-artifact smoke, five consecutive local runs | **exit 0** each; every fixed Name/ControlType pair observed exactly once, no orphan process, no local listener, profiles preserved, failure profiles unmutated, copied sidecar restored |
| T090 checkout-CWD rejection | **`checkout_cwd_forbidden` in 979 ms**, reproduced deliberately from a process rooted in the checkout |
| T090 driver public self-tests | **25 passed** from an external working directory |
| T090 replaced observation primitives cross-check | **PASS**; 737 common PIDs with zero parent mismatches, live child discovered, no phantom PID, 46 listener owners versus 46 with none missing |
| T090 Desktop Vitest | **165 passed** across 19 files with `--exclude '.build/**'` |
| T090 focused Python delivery gate, packaged smoke, and sidecar | **115 passed** |
| T090 full local `uv run pytest` | **1988 passed, 33 skipped** |
| T090 Desktop typecheck and build | **PASS** |
| T090 repository CI on the reviewed commit | **failure**; 5 failed / 1955 passed on Windows and 22 failed / 1944 passed on Ubuntu. All were repaired later in this unit — the delivery-script defects during T090, the 18 POSIX failures in the convergence repair — so none is deferred |
| T090 `web` and `desktop` source-gate workflows on the reviewed commit | **success**; both had failed on every prior commit of this branch |

### Honesty

- The first Vitest invocation supplied a repository-relative path after npm had already changed into the Desktop workspace, so Vitest reported `No test files found`. That harness-only attempt is excluded; the corrected workspace-relative command collected all eight tests and produced the recorded product RED.
- No sidecar freeze, `electron-builder` package, packaged-artifact smoke, network authority lookup, dependency install, accepted manifest/lock edit, workflow implementation, or delivery wrapper implementation ran in T082. T090 remains the mandatory gate before the first freeze/package/smoke.
- Checking T082 records only that the required tests were written and their expected failures observed. It does not make C4 PASS-current or authorize delivery execution.
- T085 source-build evidence is not packaged-artifact evidence. The observed Vite warnings preserve three runtime-resolved URLs and the renderer chunk-size warning is non-blocking; neither warning is claimed as resolved.
- T086 exercised synthetic materialization and one local `HEAD:package.json` Git-blob read only. It did not run live GitHub authority lookup, `uv export`, dependency sync/install, PyInstaller, electron-builder, or packaged smoke. C4 remains incomplete until T089–T095.
- T088 workflow structure was verified by Vitest source contracts, linked Python delivery contracts, Desktop typecheck, and whitespace checks. No local GitHub Actions YAML parser was available (`PyYAML` and Ruby were absent), no dependency/tool was installed to compensate, and no GitHub-hosted workflow run is claimed.
- T088 changed workflow source only. It did not execute live authority lookup, dependency installation, sidecar freeze, `electron-builder`, artifact copy, or UI Automation smoke; T090 still blocks the first such delivery execution.
- T089 evidence is source/test evidence only. It did not run PyInstaller, `electron-builder`, copy a real artifact, inspect a real Electron UIA tree, or perform a live Stage-C authority lookup. Those claims remain intentionally blocked by T090.
- The current permission configuration denies `Agent(claudex-code-reviewer)`. Architecture review is current and PASS, but the separately preselected code-review evidence remains unavailable rather than being silently substituted.
- The delivery job's reviewed-source recheck step runs fifteen commands under `shell: powershell`, which reports only the last command's exit code, so a mid-script `uv run ruff`, `uv run mypy`, `uv run pytest`, or `npm test` failure is masked. That step's `success` is therefore **not** evidence that the reviewed source is green, and repository CI was red on the same commit. The same masking applies to the eight-command source-gate step. This was found during T090 and deliberately left unrepaired at the time, because making the gate strict while CI was red would have blocked delivery on failures the unit had not yet fixed. Repository CI is now green on both platforms, so the reason to defer is gone and the masking is repaired — see "Delivery gate fail-open repair" below.
- The delivery run's bounded smoke evidence is written to the runner's external run root and is not uploaded, so it could not be read back. The per-scenario fields recorded above come from the five local runs; the delivery run contributes its job conclusion, step boundaries, and the packaged application's own standard-error signature only.
- The locally smoked artifact was produced by `electron-builder` with a local configuration for debugging, not through the descriptor-gated wrapper route. The descriptor-gated route's own evidence is the delivery run, whose artifact was neither retained nor independently inspected here.
- Repository CI was red on the reviewed commit: 22 failures on Ubuntu (chiefly `test_artifacts.py`, `test_desktop_restore.py`, `test_run_lifecycle.py`, `test_host_durability.py`) and 5 on Windows (verifier and driver self-tests). The Windows five and four of the Ubuntu failures were delivery-script defects, repaired during T090. **This entry originally claimed the remaining 18 Ubuntu failures predated this task. That was wrong.** `git log -S` on each failing test name returns this unit's own `e3384bd` ("fix(078): close artifact deletion lifecycle"), so they are 078 regressions, not inherited ones. Their repair is recorded under the POSIX correction below.
- `conftest.py`, `.github/workflows/web.yml`, and `docs/api-reference.md` were initially excluded from the delivery candidate as release tooling. That classification was wrong: contracts already committed for this feature assert all three, and the failing CI runs proved it. They are now part of the reviewed commit.

<!-- US6-EVIDENCE END -->

---

## Phase 9 convergence — T091 public-safety routing

T010 established the surface taxonomy and proved the scanner itself separates content
surfaces from secondary ones. It did **not** route any product payload through that
scanner: before this task the synthetic markers were referenced only by the scanner's own
tests and by the committed-file scan, so no shipped Desktop surface had ever been asserted
clean with them.

`tests/contract/test_desktop_public_safety_routing.py` closes that gap by driving real
product code:

- **RPC errors.** A `Dispatcher` method that raises with every prohibited marker
  concatenated into one exception yields only the fixed `desktop.error.internal_failure`
  envelope; the serialized frame discloses no secret, private path, rule, PID, or raw
  error. A second case sends marker-bearing request parameters to an unknown method and
  proves they are not echoed onto the error surface.
- **Diagnostics.** Every shipped `RpcError` in the public catalogue — internal failure,
  parse error, invalid request, method not found, invalid params — is scanned as a
  secondary surface and produces zero findings.
- **Backup manifest.** The shipped `describe_backup()` disclosure is scanned as a
  `backup_manifest` surface and is clean.
- **Snapshots and content routing.** A portable archive is built over a snapshot whose
  session entry carries authorized user and model content, while the input profile carries
  a prohibited marker in both an unsent composer draft and a credential field. The returned
  manifest, the revalidated manifest from `validate_archive`, and the exported
  `profile/profile.json` are all clean, proving the draft and credential exclusions hold;
  the archived session entry retains both authorized markers and is byte-identical to the
  input, proving authorized content survives losslessly.

The routing test states its own premise: it first asserts that the poisoned failure text
*is* detected on a secondary surface, so the clean envelope that follows is a real result
rather than an unscanned one.

| Suite | Result |
|-------|--------|
| T091 committed-file public-safety scan | **15 passed** |
| T091 surface-taxonomy contract (T010) | **4 passed** |
| T091 product-surface routing (new) | **5 passed** |
| T091 combined | **24 passed** |
| T091 Ruff format/check on the new file | **PASS** |

## Phase 9 convergence — T092 architecture, default, and generated-contract guards

| Guard | Suite | Result |
|-------|-------|--------|
| Gateway-only invocation | `tests/contract/test_tool_gateway.py` | PASS |
| Event Bus ownership | `tests/contract/test_runtime_events.py`, `tests/contract/test_event_replay_store.py` | PASS |
| Checkpoint record and schema | `tests/contract/test_checkpoint.py`, `tests/contract/test_checkpoint_sqlite.py` | PASS |
| Sidecar Host-only / live-store boundary | `tests/contract/test_desktop_boundary.py` | PASS |
| Default declining portable snapshot provider | `tests/unit/test_host_portable_snapshot.py` | PASS |
| `StorageConfig` and `RuntimeConfig` defaults | `tests/contract/test_host_config.py` | PASS |
| Unchanged Web outward contracts | `tests/contract/test_webapi_boundary.py`, `test_web_type_artifacts.py`, and the five `test_web_*_contract.py` suites | PASS |
| PyInstaller absent from runtime metadata | `tests/contract/test_packaging.py` | PASS |

Combined: **164 passed, 9 skipped**.

The PyInstaller guard was incomplete and is now closed. `test_runtime_dependencies_are_unchanged`
already bars the freeze tool from `[project]` through closed dependency and optional-dependency
sets, but nothing asserted the resolved runtime lock. `test_pyinstaller_stays_out_of_runtime_metadata`
now asserts absence from both `pyproject.toml` and `uv.lock`, and first asserts that the
build-only input `apps/desktop/sidecar/pyinstaller-build.in` does contain the tool, so the
guard cannot pass vacuously against a repository that simply never mentions it.

### Honesty

- T091 and T092 are source and contract evidence. They did not run the packaged artifact, a
  live Electron accessibility tree, or a delivery authority lookup.
- T091 routes the Desktop surfaces reachable without standing up a Host: the JSON-RPC error
  envelope, the shipped error catalogue, the backup disclosure, and the portable archive
  manifest and entries. Renderer-side IPC metadata is TypeScript and is covered by the
  Desktop Vitest boundary suites rather than by this Python routing scan; audit list
  projections were not routed because they require a live Host, and remain covered by their
  own unit contracts.
- T091 is explicitly not the final documentation scan. T099 must rescan every T096–T098
  output.
- The T092 result reflects the local tree. Repository CI remains red for reasons recorded
  under T090 and belonging to T093/T094.

## Phase 9 convergence — T096–T098 documentation

### T096 Desktop usage and delivery documentation

`docs/desktop-gui.md` was still a unit-019/024 document. It told the reader to
`pip install pyinstaller` and run `npm run dist` directly, which is exactly the bare route
078 removed, and it described `npm run dev` as building the renderer and launching Electron
when that script is now only `vite`. It was rewritten around the delivered system: the
shared presentation package, the trust boundary across renderer, main, and sidecar, the
two-phase startup, the on-disk profile-ownership layout, projects and chooser-bound
workspaces, the backup disclosure with its draft and credential exclusions and the
validate / commit / cancel restore lease, the four-script delivery table with PyInstaller
named as build-only, the two required Windows CI jobs, and external-CWD package validation.

That last section states the trap explicitly: the driver reads the **process** working
directory, `Push-Location` does not change it, and the run fails closed with
`checkout_cwd_forbidden` before any window appears. A worked `Start-Process
-WorkingDirectory` invocation is given.

`docs/manual-qa.md` lost the same `pip install pyinstaller` block. Its Desktop dev launch
now installs from the repository root and launches from `apps/desktop`, because the Electron
binary is a workspace devDependency and is not hoisted — the previously documented command
would not have resolved. Its packaged-artifact checklist is now the verifier-gated chain and
the external-CWD smoke acceptance rather than a bare tool sequence.

### T097 shared presentation and unchanged Web contracts

- `docs/web-frontend.md` gains a unit-078 section describing `packages/cowork-presentation`
  as presentation-only — no transport, no Host reference, no credential — rendered by both
  apps through their own adapters, and records that the Web app's outward behavior is
  unchanged with the asserting suites named. It also records the single root lock and the
  `-w` workspace addressing that replaced per-app locks.
- `docs/web-api-host.md` gains a unit-078 section stating that nothing on that surface
  changed and that Desktop does not mount, call, or depend on the host at all.
- `docs/api-reference.md` was updated earlier in this unit with the six Desktop storage
  authority symbols that `tests/contract/test_api_reference.py` compares against
  `__all__`.

### T098 capability, gap, architecture, and risk records

- `docs/capabilities.md` gains a **Desktop cowork parity** layer row for 078.
- `docs/gap-analysis.md` no longer calls 078 "the next reserved board unit"; it records the
  unit as implemented with its delivery gate passed, while naming the board as the only
  completion authority.
- `docs/architecture/ARCHITECTURE_AUDIT.md` is a frozen dated snapshot whose own maintenance
  rule forbids self-update, so its body was **not** rewritten. A dated known-drift note
  records that its "076–078 Not started" line is stale and that the shared package and the
  four-script delivery route postdate the snapshot.
- `docs/architecture/RISK_REGISTER.md` gains two risks this unit actually paid for:
  **R14 — a guard asserts the construct instead of the property**, taken from the
  `Push-Location` false green, and **R15 — fail-open multi-command CI steps**, taken from
  the reviewed-source gate that reports only its last command's exit code.
- `CHANGELOG.md` gains the 078 entry under `[Unreleased]`, which previously jumped from 077
  to 080. No version was bumped and no release was made.

### Honesty

- These are documentation edits. No new gate result is claimed by them.
- The unit-024 row in `docs/capabilities.md` still describes the historical packaging route;
  it was left as history and the new 078 row records that delivery replaced it.
- `docs/gap-analysis.md` still lists 079 and the later roadmap tail as future work; that was
  out of scope here.
- The architecture audit remains stale in substance. Only a drift marker was added; a real
  re-audit is a separate unit.

## Phase 9 convergence — T093 Python gates

| Gate | Result |
|------|--------|
| `uv run ruff format --check .` | **PASS**, 533 files already formatted |
| `uv run ruff check .` | **PASS** |
| `uv run mypy` | **PASS**, no issues in 205 source files |
| Focused: delivery gate, packaged smoke, sidecar | **115 passed** in 167 s |
| Full `uv run pytest -q` | **1994 passed, 33 skipped, 1 warning** in 563 s |
| `uv build` | **PASS**, `loopplane-0.4.0.tar.gz` and `loopplane-0.4.0-py3-none-any.whl` |

The single warning is the pre-existing `StarletteDeprecationWarning` from FastAPI's test
client. No test was rerun in isolation to obtain these numbers.

Two of these gates were red before this task and were repaired as part of it, both by
closing `.gitignore` gaps rather than by weakening a check:

- `ruff check .` reported one `I001` in `apps/desktop/.build/local-smoke-*/isolated-workspace/`,
  a stale copy of this workspace left by a local packaging run. That directory and
  `apps/*/dist-electron/` were untracked but **not** ignored, which also made them a
  bulk-`git add` hazard. Ignoring them removes the finding without touching the rule set.
- `uv build` failed with `FileNotFoundError` while the sdist builder walked
  `.claude/worktrees/082-open-source-release-readiness/tmp/full-long-path/...`, a sibling
  git worktree checked out inside this tree. Git excluded it only through the local,
  uncommitted `.git/info/exclude`, which the build backend does not read. `.gitignore` now
  covers `.claude/worktrees/`, so any contributor with a worktree there can build.

## Phase 9 convergence — T094 JavaScript gates

| Gate | Result |
|------|--------|
| Root clean `npm ci` | **PASS** |
| `@loopplane/cowork-presentation` typecheck | **PASS** |
| `@loopplane/cowork-presentation` Vitest | **29 passed** |
| `@loopplane/web` typecheck | **PASS** |
| `@loopplane/web` Vitest | **202 passed** |
| `@loopplane/web` build | **PASS** |
| `@loopplane/desktop` typecheck | **PASS** |
| `@loopplane/desktop` Vitest | **165 passed** across 19 files |
| `@loopplane/desktop` build | **PASS** |

The Chromium accessibility and reflow matrix runs inside those suites:
`packages/cowork-presentation/src/__tests__/accessibility.test.tsx` and
`apps/web/src/__tests__/AccessibilityStyles.test.ts`. No dependency was upgraded.

The Desktop Vitest run previously needed a manual `--exclude '.build/**'` or it collected
stale copies of the workspace and reported failures from old sources. That footgun is now
closed in `apps/desktop/vite.config.ts` rather than documented, so the plain workspace
command is correct.

## Phase 9 convergence — repository CI failure decomposition

Repository CI had never been green on this branch. Every failure was attributed to a cause
from its own log rather than inferred, and the pre-existing set was confirmed against run
`31708217334` on commit `121f1c9`, before any change in this task.

| Failures | Cause | Disposition |
|----------|-------|-------------|
| 4 verifier self-tests plus `profile-inventory-detects-mutation` (Windows) | The runner reported `Get-FileHash` as **not recognized**. The scripts called it to hash files, so the delivery verifier failed long after its own checks passed. | The four delivery scripts now compute SHA-256 with the .NET API they already used elsewhere. Digest parity with `Get-FileHash` was verified byte-for-byte. |
| `delivery-cat-file-binds-git-blob` (Ubuntu) | `Get-Command git.exe` — a Windows-only executable name — while the delivery contracts also run under `pwsh` on Linux. | A portable `Get-GitExecutable` resolves `git.exe` or `git` and still binds `-CommandType Application`, so no alias or function can stand in for it. |
| `reject-reparse-layout`, `incompatible-sidecar-restored`, `listener-observation-detects-listener` (Ubuntu) | NTFS junctions, the .NET Framework compiler behind `Add-Type -OutputAssembly`, and the `iphlpapi.dll` listener table have no Linux equivalent. The driver is a Windows UI-Automation tool. | Those three cases now skip on non-Windows; the other twenty-two remain portable and continue to run. |
| `test_api_reference`, `test_fresh_checkout_test_and_web_workflows_use_tracked_authorities` | `docs/api-reference.md`, `conftest.py`, and `.github/workflows/web.yml` were missing from the branch. | Fixed earlier in this unit; both now pass. |
| 18 POSIX artifact, restore, run-lifecycle, and host-durability failures (Ubuntu) | **This unit's own regressions.** `git log -S` on every failing test name returns `e3384bd` ("fix(078): close artifact deletion lifecycle"). They stayed invisible until the missing `conftest.py` was restored, which turned that run's 1048 `tmp_path` errors back into real results. | **Repaired here** — see "POSIX convergence repair" below. |

`apps/desktop/electron/__tests__/packaging.test.ts` asserted `toContain("Get-FileHash")`,
pinning the mechanism rather than the property, so it would have gone red on a correct fix.
It now asserts that the driver records a SHA-256 digest and rejects the old call, and both
new assertions were confirmed red against the previous revision. This is the second guard in
this unit found asserting a construct instead of a property; the pattern is recorded as R14.

### Honesty

- The delivery-script repairs are confirmed on the runners, not only locally. On the head
  commit the `web` and `desktop` workflows both pass — `desktop` covers both the push
  source-gate job and the pull-request one — the Windows `CI` job passes with no failures,
  and the Ubuntu `CI` job reports exactly **18 failed, 1951 passed, 28 skipped**: eleven in
  `test_artifacts.py`, four in `test_desktop_restore.py`, two in `test_run_lifecycle.py`,
  and one in `test_host_durability.py`. Nothing from this unit's contracts remains red.
- One repair needed a second pass. `Get-GitExecutable` first read `.Source` off the whole
  `Get-Command` result; a runner exposing three `git.exe` entries on PATH turned that into a
  single string of joined paths and broke the previously green Windows job. This machine has
  one `git.exe`, so only the runner could surface it. It now takes the first PATH match.
- The Ubuntu POSIX group was first recorded here as pre-existing and out of scope. **That
  attribution was wrong.** `git log -S` on each of the failing test names returns this unit's
  own `e3384bd`, so the group is an 078 regression and was repaired in this task rather than
  deferred.
- WSL was also first rejected as a reproduction environment for that group, on the grounds
  that the available distribution runs as root on a DrvFs mount whose rename and inode
  semantics differ from ext4. That reasoning holds only for a checkout under `/mnt`. Copying
  the sources into the WSL home on ext4 reproduced all 18 failures exactly and gave a ~0.5 s
  edit-test loop, which is how they were diagnosed.
- The gate numbers above come from a clean full run taken after every change in this task;
  an earlier run was discarded because the tree was edited while it was in flight.

## Phase 9 convergence — POSIX convergence repair

The 18 Ubuntu failures — eleven in `test_artifacts.py`, four in `test_desktop_restore.py`,
two in `test_run_lifecycle.py`, one in `test_host_durability.py` — were reproduced exactly
in a WSL copy of the sources on ext4 and repaired. Five are product defects; the rest are
contracts that encoded a call shape or a platform sequence the implementation does not use.

### Product repairs

| Defect | Why Windows never saw it | Repair |
|--------|--------------------------|--------|
| `ArtifactStore` rejected its own root. `DesktopStorageAuthorityFactory` hands the store a root that **is** one open directory descriptor of this process, exposed as `/proc/self/fd/<fd>`. `_directory_identity` read it with `lstat`, saw a symlink, and raised `artifact session layout invalid`; `_posix_open_directory_anchor` could not have opened it either, because `O_NOFOLLOW` on a procfs magic link returns `ENOTDIR`. Every desktop-restore artifact deletion failed. | Windows storage authority hands over a real path, so the shape never arises. | `_retained_descriptor_root()` recognises exactly `/proc/self/fd/<n>` and `/dev/fd/<n>`. That one root is stat'ed and opened following the link; every child anchor keeps `lstat` plus `O_NOFOLLOW`. The descriptor table is process-private, so following it cannot reach an attacker-chosen target. `loopplane.host.snapshot` already carried the identical rule. |
| The `finally` of `prepare_session_deletion` asserted all five anchors were non-`None`, but a failure while *acquiring* them leaves some unset. The `AssertionError` replaced the real cause. | The failing acquisition is the capability root above. | The retained-authority record is built only when all five anchors exist; the close-everything branch, which already tolerated gaps, handles the rest and still surfaces the original error. |
| POSIX rollback moved the source name resolved by the kernel, not the directory it had validated. `renameat2` resolves `source_name` itself, so a replacement installed after the pre-check would be moved instead. | The Windows branch already re-proved identity at the destination. | The POSIX branch now re-`stat`s the destination after the rename and fails closed if the identity changed. |
| A cleanup retry after a pass that removed the tree and then failed while releasing authority asserted on already-closed anchors. | POSIX-only code path. | The retry returns when no work remains and still raises `artifact deletion authority changed` when any member or cleanup name is still pending. |
| A rollback blocked by a foreign object owning the destination name released the caller's authority, which made the documented retry impossible. | POSIX-only code path. | That refusal now marks the deletion retryable and retains the authority. A store that is unusable (`_require_root` failure) still releases it, so `test_shared_session_rollback_preflight_failure_closes_authority` keeps its meaning. |

### Contract repairs

- **Eleven `test_artifacts.py` cases hooked call shapes the implementation does not use.**
  They patched `Path.unlink`, `os.rename` and full-path `os.lstat`; the implementation is
  fd-anchored — `os.unlink(name, dir_fd=)`, `_posix_rename_noreplace`, and
  `os.stat(name, dir_fd=, follow_symlinks=False)` — and quarantines each member under a
  `.erase-<uuid>` name before unlinking it, so hooks keyed on the original name or on a
  `.txt` suffix never fired. They now hook the real seams. Every safety property they
  asserted is preserved, and three of them assert the stricter fail-closed outcome the
  implementation actually produces.
- **Two cases encoded a Windows-only sequence.** Both injected exactly one close failure.
  Windows cannot move a directory that still has open handles, so the failed prepare retains
  its authority *without attempting a close* and the single failure lands on the retry.
  POSIX rolls the staged move back with the anchors still open, so the cleanup close does run
  during the first delete and consumes the budget there. The budget is now `1` on Windows and
  `2` on POSIX, with the reason recorded in place. No product behaviour changed; both
  platforms are correct as they stand.
- **One case had never run anywhere.** `test_artifact_commit_failure_drops_session_and_retries_before_next_delete`
  skips on Windows and was buried under the 1048 `conftest.py` errors on Ubuntu. It asserted
  that `bulk_delete_sessions` deletes a session that was never given a `SessionMetaRecord`,
  so the durable owner listing it filters on was empty and it could not have passed. The
  record is now appended, as its sibling test in the same file already did.

### Verification

| Gate | Result |
|------|--------|
| The four previously failing files, WSL ext4 (Ubuntu 22.04, glibc 2.35, Python 3.12.13) | **195 passed, 7 skipped** |
| Full suite, same environment | **1911 passed, 28 skipped**, 89 failed |
| Full suite, Windows | **1994 passed, 33 skipped**, 0 failed |
| `uv run ruff check` and `uv run ruff format --check` | **PASS** |
| `uv run mypy` (project configuration) | **Success: no issues found in 205 source files** |
| Repository CI on the pushed commit `371341b`, run `31817242567` | **success** on both legs: `test (ubuntu-latest)` **1969 passed, 28 skipped, 0 failed** and `test (windows-latest)` success. `web` and `desktop` also succeeded on push and pull request. |

### Honesty

- The 89 remaining ext4 failures are all local-mirror gaps, not product results: 87 are
  `FileNotFoundError: 'pwsh'` from the delivery-gate and packaged-smoke contracts, because
  this WSL distribution has no PowerShell Core while the GitHub Ubuntu runner ships it; one
  is `test_public_safety.py`, which shells out to `git ls-files` and the mirror carries no
  `.git`; one is Unit 082's untracked `test_docs_links.py`. All three groups pass on Windows
  and were already green on Ubuntu CI. Copying `.git` (2.0 GB) or installing `pwsh` was not
  done, so a fully green Linux run is **not** claimed from the local mirror. The
  authoritative check is repository CI, and run `31817242567` on the pushed commit reports
  Ubuntu green with zero failures.
- `mypy` was first run as `mypy src tests`, which overrides the configured file set and
  reported 956 errors across 121 files. The project gate is a bare `uv run mypy`; that is the
  invocation recorded above.
- The Windows-versus-POSIX close sequence was established by instrumenting an actual run on
  both platforms, not inferred from the source.

## Phase 9 convergence — delivery gate fail-open repair

R15: three `shell: powershell` steps in `.github/workflows/desktop.yml` ran their gates as
a bare sequence. That shell reports only the **last** command's exit code, so 21 gates could
fail without failing their step — including every `ruff`, `mypy`, `pytest` and `npm test` in
the delivery job's reviewed-source recheck. The step's `success` was therefore not evidence
that the reviewed source was green. It was recorded rather than repaired during T090 because
tightening the gate while CI was red would have blocked delivery on failures this unit had
not yet fixed; with CI now green on both platforms that reason no longer holds.

Each gate is now invoked through an `Assert-Gate` guard that throws on a non-zero exit, so a
failure both fails the step and stops the sequence. The affected steps are `Python delivery
contracts` (2 gates), `Shared, Web, and Desktop source gates` (8), and `Recheck reviewed
source before Stage C` (14). The two Stage-C steps already checked `$LASTEXITCODE` and are
unchanged.

### Guards

Two contracts in `tests/contract/test_desktop_delivery_gate.py` were written first and
observed RED against the unrepaired workflow, where they named all 21 masked gates:

- `test_powershell_delivery_steps_cannot_swallow_a_failed_gate` asserts the property rather
  than the mechanism — a bare native gate is allowed only where its own exit code is already
  the step's. It stays true under any guard implementation.
- `test_powershell_gate_guard_actually_inspects_the_exit_code` closes the obvious way to
  satisfy the first one falsely: a wrapper that runs the gate but discards its exit code.
  It requires the guard's definition to read `$LASTEXITCODE` and to `throw`.

This is the third guard in this unit that had to be checked for asserting a construct instead
of a property (R14), so both were confirmed RED before the workflow changed.

### Verification

| Gate | Result |
|------|--------|
| The two new contracts, before the repair | **RED**, naming all 21 masked gates |
| `tests/contract/test_desktop_delivery_gate.py` after the repair | **78 passed** |
| Desktop Vitest `packaging.test.ts` (reads the same workflow) | **9 passed** |
| Windows PowerShell 5.1 parse of all five extracted `run` blocks | **OK**, zero parse errors |
| `Assert-Gate` runtime proof under Windows PowerShell 5.1 | a passing gate does not throw; a failing gate throws its label; a later gate does **not** run after an earlier failure; `-w @loopplane/... -- --run` reaches the command verbatim |
| `uv run ruff format --check .` and `uv run ruff check .` | **PASS** (533 files) |
| `uv run mypy` | **Success: no issues found in 205 source files** |
| The two repaired push steps, live on the runner (`desktop` run `31825795739`) | both **success**. `Python delivery contracts` 108 passed; `Shared, Web, and Desktop source gates` ran all eight guarded gates — presentation 29 tests / 7 files, web 202 / 58, desktop 165 / 19, plus three typechecks and two builds. No guard fired spuriously. |

### Honesty

- The two push/pull-request steps are now verified live on the runner, including that the
  guard does not fire on a passing gate. The `Recheck reviewed source before Stage C` step
  runs only inside the delivery job, which requires an approved submitted review, so its
  repaired form is verified by parse, by runtime proof of the identical guard, and by
  contract — **not** by a live run.
- The guard is structural: no unit test can execute a workflow step, so it approximates
  "a failing gate fails the step" by forbidding the shape that cannot. The runtime proof
  above covers the behaviour the structure stands in for.

## Phase 9 convergence — desktop renderer presentation repair

The packaged application was unusable: it painted as raw serif HTML in a single
column. Two defects, found by reading build output rather than source.

### The renderer loaded no stylesheet

`apps/desktop` contained no `.css` reference at all — no import in `main.tsx`, no
`<link>` in `index.html`, and no CSS asset in the Vite build, which emitted only
`index.html` and one JS chunk. The Web build emits a 30 kB stylesheet from the
same shared package. Every shared component styles through `className` and none
use inline styles, so nothing had any appearance.

`main.tsx` now imports a renderer stylesheet that pulls in
`@loopplane/cowork-presentation/styles.css`, exactly as `apps/web/src/styles.css`
already did. Resolving that specifier also needed a Vite repair: a string alias
matches by **prefix**, so aliasing the bare package name alone routed the
`/styles.css` subpath into the index module's path and the build failed with
`ENOENT`. The subpath now has its own alias, declared first.

### `CoworkShell` had no layout to load

`CoworkShell` is rendered only by Desktop — Web imports `AppShell`,
`MessageList`, `InspectionPanel`, the dialogs and the settings views, but never
the pane workspace. So the shared stylesheet carried its T050/T055 accessibility
baseline and nothing else: `grid-template-columns: minmax(0, 1fr)`,
unconditionally, at every width. Nine desktop-owned classes had no rule anywhere.

The workspace now has three columns at 1180px and two at 760px, with the
inspection panel becoming a full-width bottom strip in between rather than being
dropped. Below 760px the accessibility baseline still governs, so the 320px
reflow contract and the reduced-motion and forced-colors blocks are untouched
and no content is hidden at any width. The desktop-owned classes are defined on
the existing tokens, so light/dark and spacing follow the shared system.

### Why every gate stayed green

This is the substantive finding. The packaged smoke drives the **accessibility
tree** through seven fixed Name/ControlType pairs; Vitest asserts DOM roles; the
shared accessibility CSS tests assert reflow at 320px — and a single-column
unstyled page passes reflow trivially. Nothing anywhere asserted that a
stylesheet was loaded at all, so an application nobody could use was green on
every platform and in every job.

### Guards

Both were written first and observed red against the unrepaired tree:

- `renderer stylesheet delivery` asserts the entry loads the shared design
  system and that Vite can resolve the specifier — the property all of the above
  missed.
- `packaged smoke locators` asserts each of the seven fixed pairs resolves
  exactly once, mirroring `Find-UniqueElement` one layer down so a rename or a
  duplicate fails in seconds instead of in a packaged UI Automation run. Proven
  to catch a duplicate by temporarily relabelling the cancel button.

### Verification

| Gate | Result |
|------|--------|
| Vitest, all three workspaces | web **202 passed / 58 files**, desktop **168 / 20**, shared **29 / 7** |
| `npm run typecheck` (all three) | **PASS** |
| Python desktop contracts (delivery gate, packaged smoke, packaging, public safety) | **130 passed** |
| Renderer build output | `index-*.css` **36.6 kB**, where it previously emitted none |
| Layout, headless capture at 1440 / 1000 / 700px | three columns / two columns plus bottom strip / single column, no content hidden |
| Packaged UI Automation smoke, `scripts/smoke-desktop-artifact.ps1 -Scenario all` | **exit 0**; `happy` passed and the three sidecar-fault scenarios diagnosed, each observing all **seven** Name/ControlType pairs, with `orphan=false`, `listener=false`, `profile_preserved=true`, `failure_profile_unchanged=true` and `copied_sidecar_restored=true` throughout |

### Honesty

- The layout was first verified by rendering the built renderer offscreen in a
  browser, where the transport bridge is absent so every capture shows the
  `unavailable` phase. The packaged application was then launched with a live
  local runtime and confirmed to render the same shell with the runtime in its
  usable state.
- **The smoke ran against a hand-assembled package**, not one produced by the
  normal build-and-package route: a copy of the last local `win-unpacked`
  outside the checkout, with its `app.asar` repacked around the freshly built
  renderer. That is enough to prove the renderer satisfies the accessibility
  contract under real UI Automation with a real sidecar; it is **not** a
  delivery-route artifact and is not claimed as one.
- Three earlier smoke attempts failed — `packaged_smoke_failed`,
  `runtime_not_usable`, and an unresolvable-path error. All three were caused by
  passing the 8.3 short form of the scratch and artifact paths
  (`C:\Users\NORTON~1.DEN\...`), which the driver cannot canonicalize. The same
  package passes the whole matrix once the paths are supplied in full. The
  `runtime_not_usable` result was **not** the known R16 timing margin, and was
  briefly misattributed to it before the control run exposed the real cause.
- The runtime status and the runtime diagnostic can show the same sentence when
  no specific diagnostic is available. That duplication is existing product
  behaviour and was left alone: the diagnostic's text is asserted by the driver
  self-tests, so changing it is not a presentation-scoped change.
- The repair changes renderer markup — the top bar wraps the title, status and
  actions, and the confirm dialogs moved into an overlay. The seven locators are
  guarded by the unit contract above and were then re-proved end to end by the
  packaged run recorded in the table.

## Phase 9 convergence — T095 post-gate packaged re-run

After the full gates, `apps/desktop` was rebuilt and repackaged, and the resulting
`win-unpacked` was copied to a fresh location outside the checkout. The packaged executable
hashes to `ffcebdd60543801fc7986280beaed7231ce520e03913a72216b72d45203b85f5`, byte-identical
to the artifact T090 accepted, confirming that everything committed since then changed
scripts, tests and documentation but not the Electron bundle.

`scripts/smoke-desktop-artifact.ps1 -Scenario all`, invoked from an external working
directory:

| Scenario | State | Elapsed | Pairs | Profile |
|----------|-------|---------|-------|---------|
| happy | passed | 19337 ms | 7 | preserved |
| missing-sidecar | diagnosed | 5361 ms | 7 | preserved, unchanged |
| corrupt-sidecar | diagnosed | 5774 ms | 7 | preserved, unchanged |
| incompatible-sidecar | diagnosed | 6794 ms | 7 | preserved, unchanged |

Overall `state=passed`, `orphan=false`, `listener=false`, 38046 ms, and the copied sidecar's
SHA-256 was byte-identical afterwards. This run also exercises the driver's replacement
hashing helper end to end.

**The first attempt failed and is recorded rather than discarded.** On the first launch of
the freshly copied artifact the driver reported `runtime_not_usable`. The probe timeline
shows why: the window appeared at 5236 ms and the seven locators at 5898 ms, the status was
still `Starting interaction…` at 9888 ms, and at 10725 ms the diagnostic became
`Local runtime unavailable`. That is the app's own handshake budget —
`SIDECAR_WARMUP_MS` plus `SIDECAR_INIT_TIMEOUT_MS`, 9500 ms — expiring because the frozen
sidecar had not answered `initialize` yet. The second and third launches of the same
artifact reached a usable runtime at 6618 ms and 5654 ms, and the re-run above passed.

The difference was machine state, not the artifact: the failing attempt ran immediately
after two full Python suites, a clean `npm ci`, and two `electron-builder` packages, with a
freshly written 330 MB copy still being scanned. The happy path therefore passes inside a
margin that load can erase. That is now **R16** in the risk register.

### Honesty

- T095 is a local re-run. The descriptor-gated route's own post-gate evidence would be a
  fresh delivery run, which requires a new Stage-C review on the current head.
- The first attempt's failure is a real observation about the margin, not a flake to be
  waved away. It is recorded above and registered as a risk.
- No acceptance deadline was changed to obtain the passing run.

## Phase 9 convergence — T099 final scan and FR/SC matrix

### Final public-safety and documentation scan

Rerun after every T096–T098 edit, over product, tests, manifests, workflows, ADR and
evidence, and each newly edited document.

| Scan | Result |
|------|--------|
| Committed-file public-safety contract | **15 passed** |
| Surface-taxonomy contract | **4 passed** |
| Product-surface routing | **5 passed** |
| Targeted pattern scan over all 25 files edited in this task | **0 findings** |

The targeted scan looked for the Windows user name, `AppData`, drive-rooted user paths, this
task's temporary artifact names, GitHub token prefixes, and assignment-shaped credential
literals. Eight `Bearer` matches were reviewed individually and none is a credential: a
documented `dev-token` placeholder, three `Bearer <token>` scheme descriptions, the delivery
verifier's own leak-detector regex, its synthetic `TEST_STAGE_B_TOKEN_VALUE_DO_NOT_LEAK`
sentinel, and one header built from a variable.

### FR matrix

| Requirements | Implementing surface | Verifying evidence |
|---|---|---|
| FR-001–FR-008 local runtime, protocol, trust | Sidecar JSON-RPC V1 with a negotiate-first startup; Electron main owning the child and the typed IPC; renderer sandboxed with context isolation and no node integration | 100-case protocol matrix (below); `test_desktop_rpc_v1.py` **13 passed**; `test_desktop_boundary.py` sidecar Host-only and no-gateway-reach-through; packaged `-Scenario all` opened no listener in any run |
| FR-009–FR-017 sessions, multi-pane, accessibility | Shared `packages/cowork-presentation` shell, pane workspace with a single-active interactive lease, focus and dismissal helpers | US1/US3/US4 sections above; shared Vitest **29 passed**; Desktop Vitest **165 passed**; Chromium accessibility and reflow matrix inside those suites |
| FR-018–FR-022 capabilities, agent controls, public safety | Host-authoritative inspection and capability projections; fixed public `desktop.error.*` catalogue | T091 routing scan (5 passed) proving marker-bearing exceptions and parameters never reach the wire; `test_desktop_public_safety*.py` |
| FR-023–FR-030 profile, workspace, resume | Profile Ownership Lock, validated generations with proof, projects, chooser-bound workspaces | US2 section; profile layout observed in every packaged run (`device-private/profile-owner.lock`, `generations/<id>/{profile,proof}.json`, `generation-storage/<id>/checkpoints.sqlite3`, `current-generation`); restart history asserted by the packaged happy scenario |
| FR-031–FR-039 audit, backup, restore | Checkpoint-derived audit projection; disclosure-first portable archive; validate / commit / cancel restore lease | US5 section; T091 proved the manifest, the revalidated manifest and the exported profile stay clean while the archived entry retains authorized content byte-identically |
| FR-040–FR-048 delivery, governance, defaults | Four delivery scripts behind a third external-human review; required Windows CI; PyInstaller build-only | T090 delivery run `31777897368` **success**; T092 guards **164 passed, 9 skipped**; `test_pyinstaller_stays_out_of_runtime_metadata` |

### SC matrix

| Criterion | Result | Evidence |
|---|---|---|
| SC-001 local run and protocol containment | **Met** | Packaged happy scenario completes initialization, a submitted prompt, the exact `loopplane-packaged-smoke-ok` marker, shutdown and a relaunch showing restart history — five consecutive T090 runs plus the T095 re-run |
| SC-002 100 mixed protocol cases | **Met** | `test_serialized_writer_and_100_malformed_matrix` exercises **100** deterministic malformed, unknown, stale, duplicate, cross-session and incompatible cases; failures counted without starting a run |
| SC-003 three-pane single-active | **Met** | US3 three-pane race: second claim returns `ok:false` with the owning pane id before any Host submit; release then re-acquire succeeds |
| SC-004 restart and resume | **Met** | Packaged relaunch asserts persisted restart history in the same external profile; profile inventory unchanged for failure scenarios |
| SC-005 public safety | **Met** | Final scan above: 24 contract tests plus a 0-finding targeted scan over every edited file |
| SC-006 backup round trip | **Met** | US5 section; T091 proved lossless authorized content with clean metadata and enforced draft/credential exclusions |
| SC-007 fault matrices | **Met, previously** | US5 T081 Windows and Linux matrices over publication, COW/proof, rollback, Host handover, relink and retained storage |
| SC-008 keyboard accessibility | **Met** | Shared and Web accessibility suites inside the T094 Vitest runs |
| SC-009 isolated package and required CI | **Met** | Delivery run `31777897368` success end to end; `desktop` source-gate and delivery jobs both green on the head commit |
| SC-010 regressions and defaults | **Met** | T093 full Python **1994 passed, 33 skipped**; T094 shared/Web/Desktop **29 / 202 / 165**; T092 default and outward-contract guards green |
| SC-011 traceability | **Met by this section** | Every FR group and SC above names its evidence; `tasks.md` records task-level FR/SC references |
| SC-012 human gates | **Met** | Stage A lock-only write; Stage B bootstrap `4864730949` and final `4864943765`; Stage C delivery `4934698622`; no version bump, tag, release or deploy |

### Named delivery evidence

- **Three distinct review identities**, all APPROVED on the same pull request and pairwise
  distinct: bootstrap `4864730949` on `5319634a…`, final `4864943765` on `8fe0a004…`,
  delivery `4934698622` on `88e6f71…`.
- **Immutable locator inputs**: T002 and T005 identities reach the workflow only from
  maintainer-controlled repository variables; the T090 identity comes only from the
  `pull_request_review` event; checkout is pinned to `github.event.review.commit_id` with
  credentials not persisted.
- **T002-to-T005 full-tree allowlist**: rerun by the verifier; recorded PASS after including
  the T003 helper, tasks and board paths.
- **Expected approver and C2 rule**: approver `norton777930` (id 266602944) differs from the
  pull-request author `norton77930` (id 75159321), so the default inequality rule is
  satisfied and `LOOPPLANE_DESKTOP_ALLOW_SELF_APPROVAL` was never required.
- **Credential handling with zero leakage**: `${{ github.token }}` is mapped only in the
  verifier step; the next step removes and re-checks all three token variables and fails
  closed on any survivor; both wrappers refuse to run if one is present. The delivery run's
  logs carry no token, header or raw body, and the verifier carries its own leak detector.
- **Four scripts and the full Windows trigger**: `verify-desktop-stage-b.ps1`,
  `build-desktop-package.ps1`, `build-desktop-sidecar.ps1`, `smoke-desktop-artifact.ps1`;
  `desktop.yml` filters every delivery determinant on push and pull request and enters the
  delivery job only on an approved submitted review.
- **Packaged accessibility preflight and external-copy smoke**: every run recorded exactly
  one instance of each of the seven fixed Name/ControlType pairs before interacting, over a
  copy outside the checkout, with checkout-CWD rejection reproduced deliberately
  (`checkout_cwd_forbidden` in 979 ms).
- **Platform gaps**: the packaged driver is a Windows UI-Automation tool; three of its
  self-tests exercise Windows-only mechanisms and skip elsewhere. The 18 Ubuntu artifact,
  restore, run-lifecycle and host-durability failures were this unit's own regressions and
  are repaired; see "POSIX convergence repair". No macOS or Linux packaged artifact is
  claimed.

### Honesty

- The FR matrix is grouped, not one row per requirement. Task-level FR references remain in
  `tasks.md`; this section maps each group to the evidence that verifies it.
- SC-003, SC-006 and SC-007 rest on evidence recorded by earlier tasks in this file and were
  not re-executed here; they are cited, not re-claimed.
- SC-010 says regressions preserve or exceed the pre-feature baseline. This section first
  recorded the 18 Ubuntu failures as predating the unit; that was wrong, and they are this
  unit's own regressions. They are repaired and verified on Linux, so SC-010 is now claimed
  on both platforms rather than on the local suites alone.

## Phase 9 convergence — T100 final candidate review

Nine commits carry this candidate beyond the previous one (`121f1c9`): the packaged-smoke
repair, the delivery working-directory repair with `conftest.py` and the web workflow, the
API reference symbols, the T090 delivery record, the public-safety routing tests, the
documentation pass, the script portability repairs with the ignore gaps, the git-resolution
follow-up, and the post-gate re-run record.

They change **32 files**: two workflows, `.gitignore`, `CHANGELOG.md`, eight Desktop app and
sidecar files, `conftest.py`, nine documents, the four delivery scripts, the two 078 spec
files, and four test files.

Every required exclusion was asserted against the complete `121f1c9..HEAD` file list and
holds:

| Excluded | Present in candidate |
|---|---|
| `.superpowers/**` | no |
| `apps/desktop/.build/**` and `apps/*/dist-electron/**` build outputs | no |
| `apps/*/dist/**` emitted renderer output | no |
| Unit 082 tree: `specs/082-…`, `GOVERNANCE.md`, `docs/release-process.md`, `docs/guides/**`, `.github/CODEOWNERS`, `.github/workflows/release.yml`, `scripts/release_sync_check.py`, `tests/contract/test_docs_links.py`, `tests/contract/test_release_sync.py` | no |
| Local profiles, backups, QA artifacts, logs, PIDs, tokens | no |

`CHANGELOG.md` needed care because it carried both this unit's `[Unreleased]` entry and an
uncommitted Unit 082 entry. Only this unit's hunk was placed in the index, with the working
tree left byte-identical, so the 082 entry stays uncommitted alongside its six other files.

Three files were initially misclassified as Unit 082 release tooling and excluded —
`conftest.py`, `.github/workflows/web.yml`, and `docs/api-reference.md`. Contracts already
committed for this feature assert all three, and the failing CI runs proved it, so they are
part of the candidate. That correction is recorded rather than quietly applied.

### Honesty

- Unit 082's work remains uncommitted in the working tree across seven files and its
  untracked additions. Nothing in this candidate touches it.
- The reviewed Stage-C commit was `88e6f71`; four commits have landed since. A further
  delivery run would require a new Stage-C review on the current head.
