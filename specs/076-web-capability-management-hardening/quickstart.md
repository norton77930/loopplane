# Quickstart: Web Capability Management Hardening

## Prerequisites

- Work from the repository root.
- Do not modify or commit raw `openspec/`.
- Use host-configured model providers and the host model catalog only.
- Do not add browser-side provider credential or MCP token entry.
- Preserve 074 REST/SSE/live chat behavior, 075 read-only inspection behavior, session management, and desktop compatibility.
- Configure `StorageConfig.root` and explicitly enable capability mutations and owner runtime activation for mutable acceptance scenarios.
- Supply a fake allow-only MCP endpoint policy and fake schedule runner in automated tests. Production hosts remain default-deny/default-unavailable until those collaborators are supplied.
- Browser-managed MCP stdio is intentionally unsupported; host-configured shared stdio remains read-only.

## Backend Validation

```powershell
uv run --project . ruff check .
uv run --project . ruff format --check .
uv run --project . mypy src/loopplane
uv run --project . pytest -q --basetemp "$env:TEMP\loopplane-pytest-076"
```

Expected outcome: backend unit, integration, contract, principal-scoping, public-safe error, gateway boundary, runtime activation, mutation-gate, durability, and compatibility tests pass.

## Focused Contract Validation

```powershell
uv run --project . pytest -q tests/contract/test_web_capability_management_contract.py tests/contract/test_web_context_management_contract.py tests/contract/test_web_schedule_model_contract.py --basetemp "$env:TEMP\loopplane-pytest-076-contract"
uv run --project . pytest -q tests/integration/test_webapi_capability_management.py tests/integration/test_webapi_context_management.py tests/integration/test_webapi_schedule_model_management.py --basetemp "$env:TEMP\loopplane-pytest-076-integration"
uv run --project . pytest -q tests/unit/test_capability_management.py tests/unit/test_capability_settings_store.py tests/unit/test_tool_gateway.py tests/unit/test_controller_capability_seams.py tests/integration/test_capability_runtime_activation.py --basetemp "$env:TEMP\loopplane-pytest-076-runtime"
```

Expected outcome: capability settings contracts cover durable storage, owner/shared scoping, runtime activation, MCP reconnect, workspace binding, schedules, model defaults, mutation gate, public-safe failure states, and existing 075 compatibility.

## Web Validation

```powershell
pnpm --dir apps/web run typecheck
pnpm --dir apps/web test
pnpm --dir apps/web run build
```

Expected outcome: independent capability settings UI flows, existing inspection behavior, 074 live/session behavior, generated type wrappers, and production build all pass.

## Desktop Compatibility

```powershell
pnpm --dir apps/desktop run typecheck
pnpm --dir apps/desktop test
```

Expected outcome: desktop remains compatible with shared web state/components.

## Manual Smoke Scenario

1. Start the web/API host and web app using the existing project workflow.
2. Sign in as a development principal.
3. Open the independent capability settings view from the app shell/header.
4. Create, open, update, and delete an owned memory entry.
5. Create or import an owned skill, verify availability status, use it in a later owner session, and verify another principal cannot see or use it.
6. Add an approved HTTP, SSE, or WebSocket MCP configuration, reconnect it, verify public-safe status and owner-visible tools, then delete it. Confirm stdio and a policy-denied URL are refused without a connection attempt.
7. Create a workspace context, bind it to an owned session, and confirm the active context appears before sending a turn.
8. Create a schedule with an instruction, disable it, confirm run-now refusal while disabled, re-enable it, run it through the configured runner, and delete it.
9. Select a default model from the host catalog and confirm invalid free-form model IDs cannot be selected.
10. Confirm no provider credential, API key, secret, token, or MCP authentication token fields are rendered.
11. Disable capability mutations via host policy and confirm lists remain read-only while mutations fail safely.
12. Run a 074 chat/session flow and a 075 read-only inspection flow after settings changes.

## Final Safety Gates

```powershell
git diff --check
git diff --name-only | Select-String "^openspec/"
git diff --name-only | Select-String "^[A-Za-z]:\\|sk-|ghp_|api_key|secret|password|token"
if (Test-Path sensitive-scan.txt) {
    git diff | Select-String -Pattern (Get-Content sensitive-scan.txt)
}
```

Expected outcome: no whitespace errors, no raw `openspec/` changes, and no public-safety findings.

## Validation Record (2026-07-11)

- Backend: Ruff check passed; Ruff format reported 470 files already formatted; mypy reported no issues in 200 source files; full pytest reported 1424 passed and 8 skipped. The only warning was the existing Starlette `httpx` deprecation.
- Web: typecheck passed; Vitest reported 44 files and 141 tests passed; the production build transformed 526 modules successfully.
- Desktop: typecheck passed; Vitest reported 3 files and 10 tests passed.
- Safety: `git diff --check` passed with informational line-ending warnings only; `openspec/` had no changes; the sensitive filename scan returned no matches. The optional local `sensitive-scan.txt` was not present, so that supplementary scan was skipped.

## Rollback Guidance

- Disable the capability mutation gate to preserve read-only inspection and chat/session behavior while blocking mutable settings actions.
- Disable owner runtime activation independently to leave durable settings readable without adding owner memory, skills, or MCP tools to later sessions.
- If durable capability settings cause issues, leave stored records unread and report settings as unavailable; existing 074/075 flows continue.
- If owner-scoped runtime activation causes issues, disable managed runtime activation while keeping settings list/detail surfaces visible.
- If managed MCP reconnect causes issues, mark affected configurations disconnected/failed and keep shared host MCP behavior unchanged.
- If model defaults cause issues, ignore the saved default and continue using existing per-session model selection.
- Reverting the 076 settings view and API hardening should restore the 075 capability management baseline.
