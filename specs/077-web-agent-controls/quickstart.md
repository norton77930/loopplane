# Quickstart: Web Agent Controls

This guide defines fresh validation for 077. Do not reuse prior-unit pass counts. No implementation command may run until the outward-contract human gate in section 2 is explicitly approved.

## 1. Working-tree protection and baseline

From the repository root:

```powershell
git status --short -uall
git diff --name-status
git diff --unified=0
git diff --cached --name-status
git diff --cached --unified=0
git ls-files --others --exclude-standard

$frozen = @(
  "specs/076-web-capability-management-hardening/spec.md",
  "specs/076-web-capability-management-hardening/plan.md",
  "specs/076-web-capability-management-hardening/tasks.md",
  "specs/080-web-frontend-visual-refactor/spec.md",
  "specs/080-web-frontend-visual-refactor/plan.md",
  "specs/080-web-frontend-visual-refactor/tasks.md",
  "specs/081-web-capability-delivery-remediation/spec.md",
  "specs/081-web-capability-delivery-remediation/plan.md",
  "specs/081-web-capability-delivery-remediation/tasks.md"
)
$frozen | ForEach-Object { Get-FileHash $_ -Algorithm SHA256 }
```

Maintain two records:

1. complete staged/unstaged/untracked inventory; and
2. a narrower hunk-reviewed 077 delivery candidate set.

`.superpowers/**`, raw `openspec/**`, browser/QA evidence, local logs/PIDs, and unknown user files are excluded. Inventory is not staging authorization.

### Baseline inventory — 2026-07-27

- Complete working tree: 152 paths (0 staged, 64 unstaged tracked, 88 untracked).
- Protected `.superpowers/**`: 24 untracked paths.
- Raw `openspec/**`: 0 paths.
- Frozen SHA-256 baseline:
  - 076 `spec.md`: `54CA8323095D829DFF60FB1B9C5CB9F2F62A701FCF52B06637B797FA32296EF3`
  - 076 `plan.md`: `C5EDEF92B5EADF0A57B45F45EF922F3999433C952422184567C43470358A2A61`
  - 076 `tasks.md`: `DE617104BEE79B972FBCF935A3C23DC8466EA5A293862B81BD66AA3C360E7434`
  - 080 `spec.md`: `49EE166CF8E8DB436550FA8AA605E2BF821ABF89501850653A88344C9B450D5B`
  - 080 `plan.md`: `8A8DFC514E531B3DFE10BC2241E83B740E5B03113F4B80BCE7450A84FB698566`
  - 080 `tasks.md`: `214D9FA17C936DE21EE641AD2D32A2C9507349BBCE7256B9B3B5FD898EC20F3A`
  - 081 `spec.md`: `78D87997094603931E6542314E515E543C105DEE28C8E541C20B37A870949301`
  - 081 `plan.md`: `29B4E924B71C1E5D0181AB65E56D6BFB91E8EA370B677819E526DE0A853A8336`
  - 081 `tasks.md`: `B354434A16618EC7A62BBE8815ADD7A36D6B4274A91A3A1345A486C9D23013C5`

### Pre-implementation refresh — 2026-07-27

- Complete working tree remains 154 paths: 0 staged, 64 unstaged tracked, and 90 untracked.
- Protected local inventory remains 24 `.superpowers/**` paths and 0 raw `openspec/**` paths.
- All nine frozen 076/080/081 hashes were recomputed and match the baseline above exactly.
- `git diff --check` and `git diff --cached --check` pass; the index remains empty. Git reports only existing CRLF-to-LF warnings for generated/client TypeScript files, not whitespace errors.
- Candidate ownership remains split into prior-unit 076/080/081 implementation and artifacts, 077-only implementation/artifact hunks, and local/unknown exclusions. Inventory does not authorize staging.
- Mixed-hunk review is mandatory for `.specify/feature.json`, `AGENTS.md`, `CLAUDE.md`, `apps/web/src/App.tsx`, API generated/client types, i18n, `apps/web/src/styles.css`, `CHANGELOG.md`, `docs/api-reference.md`, and `docs/loopplane-agent-board.md`; only 077-attributable hunks may enter a later delivery candidate.
- Requirements quality was re-reviewed with 43/43 `requirements.md` and 16/16 `agent-controls-readiness.md` items still checked; no item was reopened.
- Load-bearing cautions: `context.py` must remain free of top-level tools imports; `host/assembly.py` remains the composition root; `webapi/app.py` transports validated metadata but never evaluates policy or dispatches tools; Gateway stage/SPI, Event Bus schema/ownership, checkpoint shape, dependencies, and defaults must remain unchanged. `read_upload` eligibility comes from an existing Gateway description and later invocation remains Gateway-routed.

## 2. Required human gate before implementation

Status: **APPROVED — 2026-07-27**.

The maintainer explicitly selected **「批准並實作（建議）」** for exactly:

1. `GET /v1/sessions/{session_id}/agent-controls`, including authoritative non-durable `active_run`/`last_accepted_run` posture, as defined in `contracts/agent-control-projection.md`;
2. optional per-run `permission_mode` in applicable run/session-turn/live-submit input;
3. bounded non-image upload handoff plus stale/`read_upload`-unavailable rejection semantics from `contracts/cost-context-and-references.md`; and
4. synchronized backend-owned generated Web type artifacts.

This approval permits local source/test/generated-type implementation only. It does not permit staging, commit, branch, push, pull request, tag, version, release, deployment, or any design expansion listed below.

If design changes require durable browser-mutated state, altered approval/enforcement precedence, new artifact storage/sharing, Event Bus/checkpoint/Gateway/dependency/default changes, stop and propose an ADR plus a separate approval request.

## 3. TDD-focused backend validation

After the gate is approved, write focused tests first and observe the intended red failures before production changes.

Planned focused command:

```powershell
uv run pytest -q `
  tests/unit/test_agent_controls.py `
  tests/unit/test_permission_modes.py `
  tests/unit/test_budget_caps.py `
  tests/unit/test_monthly_budget.py `
  tests/unit/test_multimodal_assembly.py `
  tests/unit/test_controller_core.py `
  tests/contract/test_web_agent_controls_contract.py `
  tests/contract/test_web_type_artifacts.py `
  tests/contract/test_tools_boundary.py `
  tests/integration/test_webapi_agent_controls.py `
  tests/integration/test_webapi_context_management.py `
  tests/integration/test_webapi_multimodal.py `
  --basetemp "$env:TEMP\loopplane-pytest-077-focused"
```

Required scenarios:

- default-empty selectable modes preserve current behavior and response actions are read-only;
- safe host projection excludes raw rules/config/principal ids/paths/resource content;
- `bypassPermissions`, unknown, malformed, stale, and unavailable mode submissions fail before model/tool execution without value echo;
- accepted mode applies to one run only, is confirmed only through owner-scoped `active_run`/`last_accepted_run` projection, and is absent from checkpoint/session rebuild;
- existing explicit deny and safety policies beat selected mode; approval ordering unchanged;
- plan mode blocks non-read-only tools and exits only through existing question approval; reject/disconnect/non-owner keep it active;
- two principals cannot inspect or choose posture for each other's sessions;
- known-zero/unknown/unavailable/unpriced/partial cost and disabled/within/near/exceeded guard states remain distinct;
- context bind uses existing projected actions and owner/session checks;
- upload references use structured input; non-image handoff is limited to 8 references and 256 UTF-8 bytes each with exact constant-key JSON, appears only after ownership validation/explicit send when `read_upload` is projected, and stale/unavailable submissions fail before model execution; artifact references never cause raw browser content retrieval;
- no event schema, checkpoint schema, Gateway SPI/stage, default, or dependency change.

## 4. Focused Web and Desktop validation

```powershell
npm --prefix apps/web run typecheck
npm --prefix apps/web test -- AgentControlsSettings App Composer Attachments ToolCard ChatHeader generatedTypes i18n
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop test
```

Required Web scenarios:

- Agent Controls is a first-level keyboard-operated Settings category; every control category is reachable within at most two user navigation actions and the unchanged chat is restored in one action, with session/draft/stream/approval/messages/inspection/scroll state preserved;
- draft mode is not labelled effective before acceptance; plan exit has no direct toggle;
- authoritative session/month cost and all availability/pricing states render honestly;
- workspace context actions are projection-driven;
- uploads travel as structured references and current-session artifact metadata has no raw-open action;
- suggestion derivation causes zero fetch/model/tool/automatic send and selection only populates editable input;
- en/zh-TW, status/alert/live-region, focus, forced-colors, reduced-motion, and long-label coverage;
- Desktop shared imports/types remain source compatible without new sidecar controls.

## 5. Full Python gates

Run without concurrent multi-agent load:

```powershell
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q --basetemp "$env:TEMP\loopplane-pytest-077-full"
uv build
```

Record the original full-suite outcome. If a known intermittent test fails, record it and an isolated rerun separately; do not replace the full-suite result.

## 6. Full Web and Desktop gates

```powershell
npm --prefix apps/web ci
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build

npm --prefix apps/desktop ci
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop test
```

If the environment blocks dependency lifecycle execution, record that refusal and use the least-expansive approved install mode (for example `--ignore-scripts`) without changing manifests, lockfiles, dependencies, or allow-script policy.

## 7. Browser and accessibility matrix

Use deterministic, synthetic two-principal fixtures and fresh standalone Chromium evidence.

| Viewport | Coverage |
|---|---|
| 1440 × 900 | wide Settings workspace, all control sections, chat-state return |
| 1024 × 768 | full-page Settings, long labels, dialog/question overlap |
| 768 × 1024 | Settings navigation and cost/context/reference sections |
| 375 × 812 | mobile controls, composer suggestions, no overflow |
| 640 × 900 | 200% reflow equivalent |
| 320 × 800 | 400% reflow equivalent |

Cover both locales, light/dark, keyboard-only navigation, visible focus, plan question approval/rejection, reduced motion, forced colors, document language, exact zero vs unknown/unpriced cost, mutation unavailable/read-only controls, context bind, safe references, deterministic suggestions, principal A/B non-disclosure, and document/body horizontal overflow. Record literal action counts proving each Agent Controls category is reachable in at most two navigation actions and chat restoration requires one action.

Save ignored screenshots/results only under `.playwright-mcp/spec077-agent-controls/`; never stage them. Record browser version, fixture identity, assertion count, failure count, console errors, and network effects. Suggestion generation must produce zero requests.

## 8. Diff, architecture, and public-safety gates

```powershell
git diff --check
git diff --cached --check
git status --short -uall
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
```

Also run targeted architecture/public-contract tests and scan all tracked/staged/untracked candidates for:

- raw `openspec/` content;
- credentials/tokens/private keys;
- private hosts/IPs and absolute personal paths;
- raw rule match expressions or RuntimeConfig dumps;
- raw upload/artifact content in agent-control payloads;
- `.superpowers/**`, logs, screenshots, PIDs, and unknown files;
- Gateway bypass, event re-emission, checkpoint/schema drift, top-level tools imports, and default/dependency changes.

Recompute all nine frozen hashes and require exact matches.

## 9. Documentation and status convergence

Only after the human gate is approved, implementation is complete, and sections 3–8 are green:

- update `docs/api-reference.md` for approved public host/Web surfaces;
- update relevant Web API/host capability documentation;
- add an accurate 077 `[Unreleased]` entry when repository rules require it;
- append literal evidence and known limitations below;
- run documentation/API/Spec Kit/public-safety consistency tests;
- transactionally complete 077 tasks, mark the board Verified, and move the pointer only if immediate post-write checks remain green;
- restore 077 in-progress/pointer/task state on any post-write failure.

No commit, push, pull request, tag, version, release, or deployment is authorized.

## 10. Validation record

Populate during implementation. Historical prior-unit counts are prohibited.

- Human gate: approved on 2026-07-27 for the exact route, per-run input, bounded upload handoff/rejection semantics, and backend-owned generated Web artifacts documented in section 2; local implementation only.
- Focused backend red/green: red evidence included missing `UploadHandoffRejected`, missing `BudgetChecker.guard_posture`, mutable-plan projection mismatch, and absent context/reference behavior. After the minimum production slices, the implementation gate passed Ruff format/check, strict mypy over 201 source files, and `102 passed, 1 warning` in 10.60s. Generated-contract checks separately passed `12 passed`; upload handoff passed `31 passed, 1 warning`; budget/owner projection passed `37 passed, 1 warning`. After correcting stale historical test filenames in the documented command, the exact section 3 suite was re-run and passed `109 passed, 1 warning` in 14.12s.
- Focused Web: red evidence included absent Agent Controls context/reference presentation and a stale six-category structure assertion after the new first-level category was added. The final fresh full run subsumed the focused suites: TypeScript typecheck passed and Vitest reported `57 passed` files / `192 passed` tests. Deterministic suggestion tests observed no request until explicit ordinary send.
- Full Python: `uv sync --locked` resolved/checked 68 packages. The original full run passed Ruff format/check and strict mypy, then reported `2 failed, 1494 passed, 8 skipped, 1 warning`: API-reference drift for `BudgetPostureSnapshot` / `per_run_permission_mode_policy`, plus a legacy conflict-host double without `inspect_tools`. Both defects were fixed; their focused regression rerun passed `8 passed, 1 warning`. A fresh complete rerun passed Ruff (`474 files already formatted`; all checks passed), mypy (`201 source files`), pytest (`1496 passed, 8 skipped, 1 warning` in 128.17s), and `uv build` produced both the 0.4.0 sdist and wheel. The warning is the existing Starlette/httpx TestClient deprecation.
- Full Web: `npm ci` installed 278 packages and reported 6 audit findings (3 moderate, 2 high, 1 critical) plus the existing unapproved `esbuild` lifecycle-script notice; no manifest, lockfile, allow-script policy, dependency, or automatic audit-fix change was made. TypeScript passed, Vitest passed `57` files / `192` tests, and the Vite production build completed (`538` modules transformed).
- Full Desktop: `npm ci` installed 550 packages and reported 21 audit findings (3 moderate, 16 high, 2 critical), deprecation notices, and existing unapproved `electron` / `esbuild` lifecycle-script notices; no dependency or policy change was made. TypeScript passed and Vitest passed `3` files / `12` tests.
- Chromium: the initial real Vite session verified the no-token login gate and token-backed login before the Playwright MCP connection closed. A standalone Chrome 150 DevTools run then rendered the real `App` and production components through an ignored deterministic synthetic client fixture. It passed `79/79` assertions across 1440×900, 1024×768, 768×1024, 375×812, 640×900, and 320×800 with en/zh-TW, light/dark, reduced-motion, forced-colors, seven Settings categories, at-most-two-action Agent Controls reachability, one-action chat return, no horizontal overflow, exact partial cost, safe current/shared context, local permission draft, keyboard focus, deterministic suggestion selection, structured non-image upload metadata, metadata-only artifact attachment, and principal-A/B non-disclosure. Suggestion and artifact selection produced 0 requests; browser console errors were 0. Screenshots, fixture, runner, and `results.json` are ignored under `.playwright-mcp/spec077-agent-controls/` and must never be staged.
- Diff/architecture/public safety: `git diff --check` and cached check passed (only an existing CRLF-to-LF warning for `apps/web/src/api/generated.ts`); the final architecture/generated/API/public-safety/Spec Kit gate passed `64 passed, 1 warning` in 15.13s. The candidate scanner covered 1,408 tracked plus non-ignored untracked paths and found 0 secret/private-address/absolute-user-path violations, 0 raw `openspec/**`, and 0 staged paths. Final inventory was 87 unstaged tracked, 105 untracked, 0 staged, including 24 protected `.superpowers/**`; those protected/local paths remain excluded. All nine 076/080/081 hashes exactly match section 1. Those nine prior-unit artifacts are themselves Git-untracked in this mixed worktree, so the hashes prove preservation against the recorded local baseline, not immutable committed history; they remain explicitly excluded from the 077 delivery candidate.
- Post-tasks Spec Kit analysis: 44 functional requirements + 10 success criteria map semantically across all 81 tasks with no constitution or architecture blocker. The post-implementation audit identified stale focused-test filenames, stale human-gate wording, a checklist-count label reversal, incomplete Chromium evidence, documentation drift, and the untracked-frozen-history nuance. The filenames, gate wording, labels, browser evidence, and public docs were corrected; the untracked-history limitation is preserved explicitly rather than overstated. The fresh Spec Kit audit is included in the 64-pass boundary gate.
- Documentation/status convergence: `docs/api-reference.md`, `docs/capabilities.md`, `docs/web-frontend.md`, `docs/gap-analysis.md`, and `CHANGELOG.md` now describe 077 accurately. Final status/pointer convergence is performed transactionally by T081 only after T073–T080 remain green. No stage, commit, branch, push, pull request, tag, version, release, or deployment action occurred.
- Final transition: T081 is retained with all 81 tasks checked, the Agent Board recording 077 `Verified` and 078 `Not started`, and `.specify/feature.json` pointing at the reserved (not yet created) `specs/078-desktop-cowork-parity` directory. Immediate post-write checks passed diff/cached-diff validation, exact frozen hashes, `42 passed, 1 warning` documentation/API/public-safety/Spec Kit contracts, a 1,408-candidate / 1,406-text-file scan with 0 violations, 87 unstaged tracked / 105 untracked / 0 staged inventory, ignored `.playwright-mcp/**` evidence, and 24 protected `.superpowers/**` paths with 0 staged. Two ad hoc helper invocations were corrected before the authoritative rerun: one had PowerShell/Python quoting damage, and one incorrectly required the `.superpowers` directory itself to be ignored rather than excluded and unstaged; neither represented a product or repository-state failure.

### Requirement and completion coverage

- **US1 / execution posture**: FR-001–FR-011 plus FR-042–FR-043 and SC-001–SC-003 are covered by T009–T032, the 109-test focused suite, owner/non-owner integration, mutable plan-exit regression, and the Chromium permission/posture matrix.
- **US2 / cost and budget**: FR-012–FR-017 and SC-004 are covered by T033–T044, budget/monthly unit tests, owner-scoped integration, exact-decimal Web tests, and Chromium partial/unpriced posture assertions.
- **US3 / context and references**: FR-018–FR-024 plus FR-044 and SC-005 are covered by T045–T057, the bounded handoff/ownership suites, context stale/non-disclosure tests, and Chromium context/upload/artifact assertions.
- **US4 / deterministic suggestions**: FR-025–FR-028 and SC-006 are covered by T058–T066, pure derivation/interaction/request-spy tests, and Chromium zero-request selection.
- **Cross-cutting delivery**: FR-029–FR-041 and SC-007–SC-010 are covered by T067–T081, full Python/Web/Desktop builds, 79-assertion six-viewport Chromium evidence, architecture/public-safety/frozen-baseline scans, rollback text, documentation convergence, and the transaction-style final transition.
- Both requirements-quality checklists were re-evaluated against final behavior and documentation: `requirements.md` remains 43/43 checked and `agent-controls-readiness.md` remains 16/16 checked.
- Pre-transition record: authorized scope is limited to the approved owner-scoped route, optional one-run input, bounded upload handoff/rejection, generated Web artifacts, safe cost/context/reference UI, and deterministic suggestions. Verification is literal above; rollback remains section 11. The index is empty and no publication action is authorized or performed.

## 11. Rollback

- **Specification/design**: revert only 077 artifacts and restore the prior active-plan pointer through the managed agent-context workflow; never modify frozen 076/080/081 artifacts.
- **Projection/per-run posture**: disable the default-empty browser mode allow-list and remove the approved route/request field; omission returns existing behavior. No persisted migration exists.
- **Cost/budget presentation**: remove the new client reads/projection view and retain existing enforcement/accounting; do not replace unknown data with local estimates.
- **Context/references**: remove only 077 Settings/composer/reference presentation; existing context/store/upload/artifact state remains unchanged.
- **Suggestions**: remove the pure derivation/view component; ordinary composer/send behavior remains unchanged.
- **Final transition**: restore 077 in-progress, 077 pointer, and incomplete transition task before exit if any post-write check fails.
