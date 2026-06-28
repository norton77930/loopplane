# Code Review Report: LoopPlane 001-072

Date: 2026-06-22

Scope: repository state on `main` after `072-platform-fairness`, covering specs/tasks
001-072, Python runtime, web API, web frontend, desktop shell, CI gates, and public-safety
posture.

## 中文摘要與修正優先權

這次 review 的結論是：Python runtime 主線品質目前相對穩定，`ruff`、format
check、`mypy`、完整 `pytest` 都通過；真正需要優先處理的是 CI 安裝鎖檔、桌面端
與 web UI 漂移、CI 覆蓋範圍，以及兩個 model-visible error surface 的資訊外洩風險。

建議修正順序：

1. **P0：更新並提交 `uv.lock`**。目前 `.github/workflows/ci.yml` 會執行
   `uv sync --locked`，但實測失敗，代表主 CI 會在測試前就中斷。
2. **P0：修復 `apps/desktop/src/App.tsx`**。桌面端仍引用舊的 web component 與
   舊版 `ChatState` 欄位，導致 desktop typecheck/test 失敗。
3. **P1：讓 desktop CI 也在 `apps/web/**` 變更時執行**。desktop 透過 `@web/*`
   直接引用 web source，但目前 web 變更不會觸發 desktop gate。
4. **P1：清理 MCP adapter raw exception 輸出**。`call_tool` / `read_resource`
   目前會把例外類型與訊息寫入 `ErrorOutput`，可能把 secret 帶進模型、事件或歷史。
5. **P1：清理 `web_fetch` URL 錯誤輸出**。錯誤訊息目前會回顯完整 URL，query string
   可能包含 signed URL、token、signature 等敏感資料。
6. **P2：限制 `web_fetch` 在 adapter 層的 response 大小**。Gateway 會截斷輸出，
   但目前 response 已經先在 adapter/cache 中完整 materialize。
7. **P2：修正 board 與歷史 `tasks.md` 的一致性**。多個已標 Verified 的 unit
   仍有 unchecked tasks，會降低 Spec-kit/autopilot 的可稽核性。
8. **P2/P3：清掉 React `act(...)` warnings、明確設定 Electron renderer security
   options，並延後處理 Vite chunk size warning**。

## Executive Summary

The Python runtime and contract surface are broadly healthy: lint, format, strict mypy,
full pytest, public API bijection, import-boundary, and public-safety tests pass. The most
serious current issues are outside the Python unit suite:

1. The Python CI install step is currently broken because `uv.lock` is stale relative to
   `pyproject.toml`.
2. The desktop app is currently broken because it imports old web components and an old
   `ChatState` shape.
3. CI does not run the desktop gate when `apps/web/**` changes, even though desktop imports
   web source through `@web/*`.
4. Two adapter surfaces still echo potentially sensitive runtime values in tool outputs:
   MCP raw exceptions and `web_fetch` URLs.

## Verification Evidence

| Gate | Result |
| --- | --- |
| `git status --short --branch` | clean before review edits; `main...origin/main` |
| `uv run ruff check` | passed |
| `uv run ruff format --check src tests` | passed, 424 files already formatted |
| `uv run mypy src` | passed, no issues in 195 source files |
| `uv run pytest` | passed: 1333 passed, 8 skipped, 1 warning |
| `uv sync --locked` | failed: lockfile needs update |
| `npm --prefix apps/web run typecheck` | passed |
| `npm --prefix apps/web test` | passed: 31 files, 101 tests; React `act(...)` warnings present |
| `npm --prefix apps/web run build` | passed; Vite warns one chunk is 508.44 kB |
| `npm --prefix apps/desktop run typecheck` | failed with unresolved `@web/components/*` imports and stale `ChatState` fields |
| `npm --prefix apps/desktop test` | failed in `src/__tests__/App.test.tsx` due unresolved `@web/components/Conversation` |

## Remediation Status (073)

Status: implemented by `specs/073-code-review-remediation` on 2026-06-28.

| Finding | Remediation |
| --- | --- |
| P0-1 stale `uv.lock` | `uv.lock` regenerated; `psycopg[binary]>=3` added to the dev group so the default locked dev sync supports the strict mypy gate over optional Postgres modules. |
| P0-2 desktop/web drift | Desktop renderer updated to current web state/components; desktop typecheck and tests pass. |
| P1-1 desktop CI coverage | `.github/workflows/desktop.yml` now runs on `apps/web/**` changes. |
| P1-2 MCP raw exception output | MCP call/resource exception paths return fixed public-safe messages, covered by secret-injection regression tests. |
| P1-3 `web_fetch` raw URL errors | URL-bearing validation/timeout/transport/status errors use query-free labels, covered by token/key/password/signature regression tests. |
| P2-1 `web_fetch` response retention | Fetch output is capped before return/cache reuse, with oversized and within-limit regressions. |
| P2-2 Spec Kit task drift | Added `tests/contract/test_spec_task_audit.py` plus `docs/spec-task-audit-exceptions.md`; docs index now links both new 073 artifacts. |
| P2-3 React `act(...)` warnings | `AppRoot` tests now await settled authenticated UI state; web test output no longer emits the reviewed warnings. |
| P3-1 Electron security options | Renderer preferences now explicitly set `contextIsolation: true`, `nodeIntegration: false`, and `sandbox: true`. |
| P3-2 Vite chunk-size warning | Web build now emits a smaller app chunk plus `vendor` chunk without the prior Vite warning. |

Final verification evidence:

| Gate | Result |
| --- | --- |
| `uv sync --locked` | passed; 68 packages checked |
| `uv run ruff check` | passed |
| `uv run ruff format --check src tests` | passed; 425 files already formatted |
| `uv run mypy src` | passed; no issues in 195 source files |
| `uv run pytest --basetemp "$env:TEMP\loopplane-pytest-final"` | passed: 1343 passed, 8 skipped, 1 existing Starlette/httpx deprecation warning |
| `npm --prefix apps/web run typecheck` | passed |
| `npm --prefix apps/web test` | passed: 31 files, 101 tests; no reviewed `act(...)` warnings |
| `npm --prefix apps/web run build` | passed; app chunk 32.02 kB, vendor chunk 476.40 kB, no Vite chunk-size warning |
| `npm --prefix apps/desktop run typecheck` | passed |
| `npm --prefix apps/desktop test` | passed: 3 files, 8 tests |

## Findings

### P0-1: `uv.lock` is stale, so the main CI workflow fails before tests run

Evidence:

- `pyproject.toml` declares `oauth` and `postgres` extras at lines 40 and 43.
- `uv.lock` package metadata still lists extras only as
  `["anthropic", "gemini", "mcp", "net", "openai", "otel", "web"]` at line 677.
- `.github/workflows/ci.yml` runs `uv sync --locked` at line 21.
- Fresh command result: `uv sync --locked` failed with:
  `The lockfile at uv.lock needs to be updated, but --locked was provided.`

Impact: every CI run using the checked-in workflow fails before lint/type/test/build. This
also explains why `uv run ...` repeatedly tries to rewrite `uv.lock` locally.

Recommended fix:

- Run `uv lock` and commit the resulting `uv.lock`.
- Add `uv sync --locked` to the local pre-commit/final-review checklist when dependency
  metadata changes.

Priority: fix first. This blocks reliable CI validation.

### P0-2: Desktop app is currently broken by web UI drift

Evidence:

- `apps/desktop/src/App.tsx:3-5` imports `@web/components/Conversation`,
  `@web/components/Prompts`, and `@web/components/Timeline`.
- Those files no longer exist under `apps/web/src/components/`; the current web components
  are `MessageList`, dialogs, `Composer`, `Sidebar`, etc.
- `apps/desktop/src/App.tsx:34-35` reads `state.turns` and `state.timeline`, but current
  `apps/web/src/state/chat.ts` defines `ChatState.entries`, `pendingApproval`,
  `pendingQuestion`, `usage`, and `status`.
- Fresh `npm --prefix apps/desktop run typecheck` fails with TS2307 and TS2339 errors.
- Fresh `npm --prefix apps/desktop test` fails resolving
  `@web/components/Conversation`.

Impact: unit 019 is marked Verified, but the desktop renderer cannot currently typecheck or
run its test suite. Any desktop package or launch path depending on `apps/desktop/src/App.tsx`
is broken.

Recommended fix:

- Update the desktop app to consume the current web UI primitives (`MessageList`,
  `ApprovalDialog`, `QuestionDialog`, `Composer`, `ChatState.entries`) or move shared UI
  contracts into a stable shared package.
- Add a regression test proving the desktop renderer compiles against the current web state
  model.

Priority: fix before any further UI work.

### P1-1: Desktop CI does not run when web changes break desktop

Evidence:

- `apps/desktop/tsconfig.json` maps `@web/*` to `../web/src/*`.
- `apps/desktop/vite.config.ts` aliases `@web` to `../web/src`.
- `.github/workflows/desktop.yml:7-13` triggers only on `apps/desktop/**` and the workflow
  file itself.
- `.github/workflows/web.yml:7-13` triggers on `apps/web/**`, but only runs the web gate.

Impact: a change under `apps/web/**` can break desktop imports without running the desktop
workflow. That is the current failure mode.

Recommended fix:

- Add `apps/web/**` to `desktop.yml` trigger paths, or stop importing web source directly
  from desktop.
- Longer term: move shared renderer components/state into a versioned shared workspace
  package with one gate that tests all dependents.

Priority: fix immediately after P0-2, otherwise the same drift will recur.

### P1-2: MCP adapter leaks raw exception type/message into tool output

Evidence:

- `src/loopplane/adapters/mcp/adapter.py:226-230` returns
  `external server call failed: {type(exc).__name__}: {exc}`.
- `src/loopplane/adapters/mcp/adapter.py:286-291` does the same for resource calls.
- Existing tests cover MCP success, validation, server-side error normalization, transport
  headers, and token non-echo for connection setup, but no test asserts that a `call_tool`
  or `read_resource` exception containing a secret is sanitized.

Impact: an MCP server, transport layer, SDK exception, or resource error can put raw
exception text into `ErrorOutput`, which flows through the Gateway to the model, events,
UI, and checkpoint/history surfaces. This conflicts with the repository's repeated
public-safe/no-raw-exception posture.

Recommended fix:

- Replace raw exception formatting with fixed messages such as
  `external server call failed` and `external server resource call failed`.
- Add tests where `call_tool` and `read_resource` raise
  `RuntimeError("token=...")`; assert the token and traceback do not appear.
- If diagnostics are needed, keep them behind host-private logging, not model-visible
  tool output.

Priority: high; fix before exposing untrusted/remote MCP servers.

### P1-3: `web_fetch` echoes raw URLs in error output

Evidence:

- `src/loopplane/tools/web.py:151` echoes invalid URL input.
- `src/loopplane/tools/web.py:176` echoes URL on timeout.
- `src/loopplane/tools/web.py:182` echoes URL on transport failure.
- `src/loopplane/tools/web.py:189` echoes URL on non-2xx status.
- Existing `tests/unit/test_web_tools.py` checks that raw transport exception text does not
  leak, but does not cover secret-bearing URLs such as signed URLs or query tokens.

Impact: a URL like `https://host/path?token=...` can be copied into tool output and then
persisted or rendered. This is a concrete secret-leak path even when the transport
exception itself is sanitized.

Recommended fix:

- Normalize URL display in errors to scheme + host + path, or use a fixed phrase without
  echoing the URL.
- Add regression tests for query parameters named `token`, `api_key`, `signature`,
  `password`, etc.

Priority: high; fix with the MCP sanitization pass.

### P2-1: `web_fetch` buffers and caches the whole response before Gateway size management

Evidence:

- `src/loopplane/tools/web.py:163` awaits a fetcher returning the full response text.
- `src/loopplane/tools/web.py:193` caches the full text.
- Gateway output size management starts later at `src/loopplane/gateway/gateway.py:313-324`,
  after the adapter has already materialized the whole body.

Impact: the Gateway can truncate model-visible output, but it cannot prevent memory pressure
from a very large HTTP response. The cache amplifies that by retaining the full body per
session/URL.

Recommended fix:

- Add a fetch-level byte cap and stream/abort once the cap is exceeded.
- Cache only capped content or disable caching for capped/oversized responses.
- Add tests with an injected fetcher returning a very large body and assert bounded memory
  behavior at the adapter boundary.

Priority: medium; fix before enabling broad network access in long-running hosts.

### P2-2: Spec task tracking is inconsistent with the board for many verified units

Evidence:

- Board has 72 Verified units.
- Several `tasks.md` files still contain unchecked tasks while their board rows are
  Verified, including:
  - 015: 32 unchecked
  - 016: 20 unchecked
  - 018: 22 unchecked
  - 019: 12 unchecked
  - 030: 33 unchecked
  - 043: 27 unchecked
- A full scan found 27 units with at least one unchecked task, while their board rows are
  still Verified.

Impact: this weakens Spec Kit/autopilot auditability. An agent reading only `tasks.md`
would conclude major units are unfinished, while the board says they are done. It also
makes review scope harder to prove from artifacts.

Recommended fix:

- Reconcile historical tasks files: either mark completed tasks based on commits/tests, or
  add an explicit "legacy task checklist not backfilled; board is authoritative" note per
  affected spec.
- Add a small audit script/test that fails when a Verified board row has unchecked tasks
  unless the spec is explicitly exempted.

Priority: medium; fix to improve future autopilot reliability.

### P2-3: Web tests pass with React `act(...)` warnings

Evidence:

- Fresh `npm --prefix apps/web test` passed, but emitted `act(...)` warnings in
  `src/__tests__/AppRoot.test.tsx` for `ModelSelector` and `App` updates.

Impact: warnings can hide real async-state bugs and make frontend regression output noisy.
They are not currently failing tests, but they reduce signal in CI.

Recommended fix:

- Update the tests to await user-visible settled states with Testing Library async helpers.
- Consider failing CI on React test warnings once the current warnings are cleared.

Priority: medium-low.

### P3-1: Electron security options are not explicitly pinned

Evidence:

- `apps/desktop/electron/main.ts` creates `BrowserWindow` with `preload`, but does not
  explicitly set `contextIsolation`, `nodeIntegration`, or `sandbox`.

Impact: current Electron defaults are safer than older versions, but security posture is
implicit. A dependency/default change could weaken renderer isolation without a code diff
making that intent visible.

Recommended fix:

- Set `contextIsolation: true`, `nodeIntegration: false`, and evaluate whether
  `sandbox: true` is compatible with the preload bridge.

Priority: low hardening, after the desktop app is compiling again.

### P3-2: Web production bundle has a single large chunk

Evidence:

- Fresh `npm --prefix apps/web run build` passed, but Vite warned that
  `assets/index-DP5pB824.js` is 508.44 kB after minification.

Impact: not a correctness bug, but initial load cost will grow as the UI expands.

Recommended fix:

- Defer until after functional fixes; then consider route/component-level dynamic imports
  or manual chunks for markdown/highlight dependencies.

Priority: low performance follow-up.

## Suggested Fix Order

1. Regenerate and commit `uv.lock`; verify `uv sync --locked`.
2. Repair `apps/desktop/src/App.tsx` against the current web UI/state contract.
3. Update desktop CI triggers to include `apps/web/**`, or extract a shared UI package.
4. Sanitize MCP adapter exception outputs and add regression tests.
5. Sanitize `web_fetch` URL-bearing errors and add regression tests.
6. Add fetch-level byte limits before caching/output.
7. Reconcile historical tasks.md checkboxes or add explicit audit exemptions.
8. Clean React `act(...)` warnings.
9. Pin Electron renderer security options.
10. Address Vite chunk-size warning.

## Noted Positive Evidence

- Python core gates are strong: ruff, format check, strict mypy, full pytest all pass.
- Contract tests cover API reference bijection, import boundaries, public safety, runtime
  event serialization, webapi metadata-only behavior, and many default-off regressions.
- Recent 068-072 work follows a tighter task/checklist pattern than several older units;
  068-072 task checklists are fully checked.

## Review Limits

- No live model tests were executed; live suites remain skipped without credentials.
- No dependency vulnerability audit was run.
- No manual browser/Electron UI smoke was performed.
- No sub-agents were used because the user did not explicitly request delegated or
  parallel agent work.
