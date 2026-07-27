# Quickstart: Web Capability Delivery Remediation

This guide defines fresh validation for 081. Record literal results only after running each command; do not reuse 076/080 historical counts.

## 1. Prerequisites and inventory

From the repository root:

```powershell
git status --short
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
  "specs/080-web-frontend-visual-refactor/tasks.md"
)
$frozen | ForEach-Object { Get-FileHash $_ -Algorithm SHA256 }
```

Capture the six frozen hashes before implementation and compare them again during final review. This hash baseline also protects untracked historical artifacts that have no useful `git diff` against `HEAD`.

Classify every staged, unstaged, and untracked candidate file/hunk as 076, 080, 081, or local/unknown. Keep two separate records: the complete working-tree inventory and the narrower reviewed delivery candidate set. An inventory entry is not staging authorization. `.superpowers/**`, raw `openspec/**`, QA artifacts, and unclassified changes remain outside the delivery candidate set.

### Baseline inventory — 2026-07-27

- Complete working tree: 139 paths (0 staged, 62 unstaged tracked, 77 untracked).
- Protected untracked groups: `.superpowers/**` 24 paths; `specs/076-*` 10 paths; `specs/080-*` 8 paths; `specs/081-*` 11 paths.
- Frozen SHA-256 baseline:
  - 076 `spec.md`: `54CA8323095D829DFF60FB1B9C5CB9F2F62A701FCF52B06637B797FA32296EF3`
  - 076 `plan.md`: `C5EDEF92B5EADF0A57B45F45EF922F3999433C952422184567C43470358A2A61`
  - 076 `tasks.md`: `DE617104BEE79B972FBCF935A3C23DC8466EA5A293862B81BD66AA3C360E7434`
  - 080 `spec.md`: `49EE166CF8E8DB436550FA8AA605E2BF821ABF89501850653A88344C9B450D5B`
  - 080 `plan.md`: `8A8DFC514E531B3DFE10BC2241E83B740E5B03113F4B80BCE7450A84FB698566`
  - 080 `tasks.md`: `214D9FA17C936DE21EE641AD2D32A2C9507349BBCE7256B9B3B5FD898EC20F3A`
- Delivery candidate ownership remains hunk-reviewed and unstaged; these counts are inventory evidence, not authorization to include every path.

## 2. Focused backend validation

```powershell
uv run pytest -q `
  tests/unit/test_capability_management.py `
  tests/unit/test_capability_settings_store.py `
  tests/unit/test_tool_gateway.py `
  tests/unit/test_controller_capability_seams.py `
  tests/integration/test_capability_runtime_activation.py `
  tests/integration/test_webapi_capability_management.py `
  tests/integration/test_webapi_context_management.py `
  tests/integration/test_webapi_schedule_model_management.py `
  tests/contract/test_web_capability_management_contract.py `
  --basetemp "$env:TEMP\loopplane-pytest-081-focused"
```

Required scenarios:

- safe HTTP/SSE/WebSocket endpoints;
- userinfo/query/fragment/missing-host/scheme mismatch/stdio refusal at manager and store boundaries;
- public-safe failures with no submitted unsafe value;
- update/delete/failed reconnect immediate resolution removal;
- in-flight completion and exactly-once shutdown;
- two-principal MCP isolation;
- provider absent, allowed context, provider failure, duplicate ID, owner/provider collision, and non-owner session matrix;
- shared memory/skill/MCP/context safe detail projections;
- unchanged default-off behavior.

## 3. Full Python gates

Run without concurrent multi-agent load:

```powershell
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q --basetemp "$env:TEMP\loopplane-pytest-081-full"
uv build
```

If a known intermittent test fails, record the original failure and isolated rerun; do not silently replace the full-suite outcome.

## 4. Web and Desktop gates

```powershell
npm --prefix apps/web ci
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build

npm --prefix apps/desktop ci
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop test
```

## 5. Browser and accessibility matrix

Use fresh Chromium evidence at:

| Viewport | Coverage |
|---|---|
| 1440 × 900 | wide desktop, inline inspection, all shared details |
| 1024 × 768 | overlay inspection/detail, Escape and focus return |
| 768 × 1024 | tablet Settings navigation and bound context |
| 375 × 812 | mobile drawers/details/actions, no overflow |
| 640 × 900 | 200% reflow equivalent |
| 320 × 800 | 400% reflow equivalent |

Cover en and zh-TW, light and dark, keyboard-only navigation, visible focus, reduced motion, forced colors, document language, shared read-only details, allowed-context bind, and public-safe MCP refusal. Evidence is Chromium-only unless another browser is explicitly run.

### Reproducible Chromium procedure

1. Start the Web development server without changing manifests or lockfiles:

   ```powershell
   npm --prefix apps/web run dev -- --host 127.0.0.1 --port 4173
   ```

2. Use the already available Playwright/Chromium runtime and deterministic frontend HTTP interception, following the established 080 presentation-test pattern. Do not add a project dependency. Intercepted data must define:
   - principal A with one owned resource of each type plus one allowed context;
   - principal B with distinct owned resources and no visibility into principal A's context/session;
   - shared memory text longer than 160 Unicode code points;
   - shared skill instructions and MCP URL/error fields that must be returned only as safe empty/absent values;
   - one structurally invalid userinfo endpoint using synthetic `example.test` data, whose submitted value must not appear in the displayed failure.
3. Run every viewport row for both locales. Run the complete light-theme matrix; additionally cover dark theme and reduced motion at 1440 and 375. Exercise forced colors, keyboard-only Open/Bind, Escape dismissal where modal, focus return, document language, and body/document horizontal overflow.
4. Save ignored screenshots and a machine-readable result under `.playwright-mcp/spec081-capability/` using names of the form `<viewport>-<locale>-<theme>-<scenario>`. Record Chromium version, fixture identity, assertion count, failure count, console errors, and network/public-safety outcome below; never stage the artifact directory.
5. Stop the development server and report any embedded-browser/SSE environment limitation separately from deterministic standalone Chromium results.

## 6. Diff and public-safety gates

```powershell
git diff --check
git diff --cached --check
git status --short
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
```

Review tracked, staged, and untracked candidates for raw `openspec/`, credentials/tokens, private hostnames/IPs, absolute personal paths, local logs, screenshots, and `.superpowers/**`. Run repository public-safety and Spec Kit contract tests as part of the full suite and separately when diagnosing failures.

## 7. Documentation convergence

Only after all required gates pass:

- add 076, 080, and 081 entries to CHANGELOG `[Unreleased]`;
- update `docs/api-reference.md` for the approved async managed-MCP host mutations and allowed-context provider;
- complete the pre-transition documentation/API/public-safety checks;
- transactionally mark 081 Verified in `docs/loopplane-agent-board.md`, make 077 the next unit, and synchronize `.specify/feature.json` plus active-feature text;
- immediately re-run final diff, ownership, public-safety, Spec Kit, and documentation-consistency checks over those transition hunks; restore 081 in-progress and keep 077 blocked on any failure;
- retain the Verified state and record literal results below only when every post-write check is green.

## 8. Validation record

Populate during implementation:

- Focused Python: the complete section-2 command passed — `91 passed, 1 warning in 20.15s`; earlier implementation slices also passed (`81 passed`, lifecycle file `14 passed`, store file `14 passed`, context matrix `12 passed`, shared capability API `3 passed`). The warning is Starlette's existing TestClient/httpx deprecation notice.
- Python dependency/static gates: `uv sync --locked` resolved and checked 68 packages; repository-wide Ruff format reported `470 files already formatted`; repository-wide Ruff lint reported `All checks passed!`; full strict mypy reported `Success: no issues found in 200 source files`.
- Full pytest: passed — `1467 passed, 8 skipped, 1 warning in 93.03s`. The warning is the existing Starlette TestClient/httpx deprecation notice; no intermittent retry replaced the full-suite result.
- Build: `uv build` produced `dist/loopplane-0.4.0.tar.gz` and `dist/loopplane-0.4.0-py3-none-any.whl` without changing the package version.
- Web typecheck/test/build: fresh `npm --prefix apps/web ci` installed 278 packages; npm reported 6 audit findings (`3 moderate`, `2 high`, `1 critical`) and the existing `esbuild@0.21.5` install-script approval warning, so no `npm audit fix`, `--force`, dependency, allowScripts, or build-step change was made. Typecheck passed; focused Settings structure/detail passed `18/18`; focused Settings+i18n passed `19/19`; after exact-target approval removed the two legacy files, full Vitest passed `166/166` across `49/49` files; production build passed (`536 modules transformed`). The earlier expected red full run was `171 passed, 1 failed` while the legacy component still existed.
- Desktop typecheck/test: the first ordinary `npm ci` attempt was blocked because it could download and execute dependency lifecycle code. The adjusted fresh install `npm --prefix apps/desktop ci --ignore-scripts` succeeded (`550 packages`, `551 audited`) without executing Electron/package lifecycle scripts; npm reported 21 audit findings (`3 moderate`, `16 high`, `2 critical`) and no audit/dependency change was made. Fresh typecheck passed and full Vitest passed `12/12` across `3/3` files.
- Chromium matrix: deterministic standalone Chromium/Playwright MCP (`Chrome/150.0.0.0` user agent) completed 34 assertions with 0 failures. The light matrix covered 1440×900, 1024×768, 768×1024, 375×812, 640×900, and 320×800 in both en and zh-TW; dark plus reduced-motion covered 1440×900 and 375×812 in both locales; forced colors covered 375×812. Document language, theme, document/body overflow, keyboard-only Settings/Open activation, visible focus, Escape dismissal/focus return, safe memory/skill/MCP/context details, allowed-context Bind, unsafe userinfo endpoint non-echo, and principal-A/B non-disclosure all passed. The first `page.route` interception procedure timed out before assertions because fetches were not intercepted in this environment; a fresh page using one deterministic `addInitScript` fetch fixture produced the recorded green matrix. The only pre-shutdown console error was the development server's existing `/favicon.ico` 404; no application runtime exception occurred. Local ignored evidence is under `.playwright-mcp/spec081-capability/` (`results.json` plus 1440 en/light and 375 zh-TW/dark screenshots) and is not a delivery candidate.
- Diff/public-safety/Spec Kit scans: `git diff --check` passed with four line-ending normalization warnings for existing Web generated/client files; `git diff --cached --check` passed and the index remained empty. Full `-uall` inventory was 141 paths (`0 staged`, `63 unstaged tracked`, `78 untracked`): 24 protected `.superpowers/**`, 10 frozen 076 artifacts, 8 frozen 080 artifacts, 11 081 artifacts, 19 Web candidates, and 6 Python/test candidates, with 0 unknown paths. Raw `openspec/**` count was 0; all three QA artifacts were confirmed ignored. A changed-candidate scan covered 115 UTF-8 text files outside `.superpowers/**`/QA and found 0 private-key, token, assigned-secret, private-IP, or absolute-user-path violations. Targeted public-safety, Spec Kit audit, Tool Gateway/Web API/host boundary contracts passed `24 passed, 1 warning in 10.74s`. All six frozen 076/080 SHA-256 hashes exactly matched the baseline at lines 37–42.
- Documentation convergence: after synchronizing the async host/provider API reference and `[Unreleased]` entries for 076, 080, and 081, the API-reference, CHANGELOG, public-safety, and Spec Kit task-audit contracts passed `22 passed in 9.66s`.
- Pre-transition ownership review: before the final CHANGELOG/transition hunks, the complete 141-path inventory and narrower 117-path delivery candidate set were reviewed separately. The candidate set consists only of previously classified 076/080 implementation and artifacts plus 081 remediation/tests/docs, including the two approved legacy-file deletions; mixed App/i18n/style/board hunks retain their previously reviewed unit ownership. The 24 `.superpowers/**` paths are protected local artifacts and excluded, raw `openspec/**` remains absent, all `.playwright-mcp/spec081-capability/**` evidence is ignored and excluded, no staged path exists, and no unclassified/unknown path remains. Frozen 076/080 `spec.md`/`plan.md`/`tasks.md` hashes remain unchanged. Section 9 records the retained final inventory after CHANGELOG and transition updates.
- Post-implementation Spec Kit analysis: `/speckit-analyze` resolved the active 081 artifacts with 0 behavior/constitution/coverage blockers, 0 unmapped tasks, and 100% coverage for all 30 functional requirements plus 9 measurable success criteria across 55 tasks. The first T054 candidate transition then exposed one delivery-order inconsistency that static artifact review had missed: the Spec Kit task audit correctly rejected a Verified board row while T054/T055 were still unchecked (`1 failed, 30 passed, 1 warning`). The transaction was immediately rolled back to 081 in-progress and the 081 pointer; the rollback audit passed `1 passed`. T054/T055 were then clarified so the completion record is prepared first and the final transaction atomically marks T054 complete with the board/pointer change. No behavior, public-contract, constitution, or frozen-history requirement changed.

## 9. Pre-transition completion record

- **Changed scope**: 081 closes the managed-MCP endpoint/lifecycle gaps in `src/loopplane/host/` and the existing Web API await path, adds the optional allowed-context projection, sanitizes shared capability details, updates the modular Web Settings/i18n/styles/tests, removes the two approved legacy Settings files, and synchronizes 081 artifacts plus API/CHANGELOG/board evidence. Event Bus, checkpoint schema, Gateway SPI/stage order, dependencies, defaults, HTTP routes, and JSON envelopes are unchanged.
- **Human gates**: the maintainer approved only the public Python managed-MCP upsert/delete sync-to-async change on 2026-07-27, with HTTP contracts unchanged. The maintainer separately approved exact deletion of `apps/web/src/components/CapabilitySettings.tsx` and `apps/web/src/__tests__/CapabilitySettings.test.tsx`.
- **Verification evidence**: section 8 records the fresh focused/full Python, Web, Desktop, Chromium, boundary, public-safety, ownership, frozen-hash, and documentation results. No historical 076/080 count is used as 081 completion evidence.
- **Known limitations**: npm reported existing audit findings (Web: 6; Desktop: 21), and no dependency/audit/allowScripts change was authorized. Desktop dependency synchronization used `npm ci --ignore-scripts` after the ordinary lifecycle-enabled invocation was blocked. Browser evidence is Chromium-only; the development server emitted one unrelated `/favicon.ico` 404. Four existing Web files emitted CRLF-to-LF normalization warnings during `git diff --check`, which otherwise passed.
- **Delivery state**: the first T054 candidate failed the Spec Kit task audit and was fully rolled back. After correcting the T054/T055 ordering, the retained transaction atomically checked T054, marked 081 Verified, and pointed `.specify/feature.json` plus the board's active-feature text to reserved unit 077. Immediate post-write results: `git diff --check` passed with the same four CRLF normalization warnings; `git diff --cached --check` passed; board/pointer/task consistency was `True`; inventory was 142 paths (`0 staged`, `64 unstaged tracked`, `78 untracked`, `24 .superpowers`, `0 raw openspec`, `0 unknown`); all six frozen hashes matched; the changed-candidate scan covered 116 UTF-8 text files with 0 violations; and API/CHANGELOG/public-safety/Spec Kit/Tool Gateway/Web API/host boundary contracts passed `31 passed, 1 warning in 4.85s`. The transition is retained and 077 is now the next specification unit.
- **Publication state**: no file is staged; no commit, push, pull request, tag, version bump, release, deployment, or dependency update has occurred.
- **Rollback**: use section 10; any final-transition failure restores 081 in-progress, the 081 feature pointer, and the unchecked T054 state before exit.

## 10. Rollback

- **Phase 1 — setup/governance**: restore only the 081 feature-pointer and board documentation hunks; preserve all 076/080/local files and the frozen hash baseline.
- **Phase 2 — test seams**: remove only isolated 081 fixtures/helpers if necessary; no runtime or persisted state changes exist.
- **US1 — MCP safety/lifecycle**: disable capability mutations to block managed writes, disable owner runtime activation independently to remove managed owner tools from later sessions, and treat invalid legacy records as non-connectable. Revert only 081 endpoint/lifecycle hunks after both gates are off.
- **US2 — allowed contexts**: set the optional provider to `None`; owner-only contexts and existing session metadata remain authoritative, with no migration.
- **US3 — shared detail UI**: revert presentation-only detail/settings/i18n/style hunks independently; owner detail and durable state require no rollback.
- **US4 — evidence/docs**: if any gate regresses, restore board/CHANGELOG/API/pointer files to the last internally consistent in-progress state and keep 077 blocked.
- **Full-unit fallback**: a full 081 revert restores known endpoint/lifecycle gaps; pair it with disabled mutation and runtime-activation gates until a safe fix is restored.
