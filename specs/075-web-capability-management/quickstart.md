# Quickstart: Web Capability Management

## Prerequisites

- Work from the repository root on `main`.
- Do not modify or commit raw `openspec/`.
- Use host-configured providers and the host model catalog only.
- Do not add browser-side provider credential entry.
- Preserve 074 REST/SSE, live transport, session-management, and desktop compatibility behavior.

## Backend Validation

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest --basetemp "$env:TEMP\loopplane-pytest-075"
```

Expected outcome: backend unit, integration, contract, principal-scoping, public-safe error, and compatibility tests pass.

## Focused Contract Validation

```powershell
uv run pytest tests/contract --basetemp "$env:TEMP\loopplane-pytest-075-contract"
uv run pytest tests/integration --basetemp "$env:TEMP\loopplane-pytest-075-integration"
```

Expected outcome: capability management contracts cover memory, skills, MCP configuration, project/workspace context, schedules, model defaults, owner scoping, and public-safe failure states.

## Web Validation

```powershell
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected outcome: capability management UI flows, existing inspection behavior, 074 live/session behavior, generated type wrappers, and production build all pass.

## Desktop Compatibility

```powershell
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop test
```

Expected outcome: desktop remains compatible with shared web state/components until 077.

## Manual Smoke Scenario

1. Start the web/API host and web app using the existing project workflow.
2. Sign in with an existing development credential.
3. Open capability management from the inspection/settings surface.
4. List memory entries, open one owned entry, save an edit, then delete an owned test entry.
5. List skills, import a valid skill fixture, verify status, and delete the imported test skill.
6. Add or update an MCP configuration, request reconnect, verify public-safe status, and delete the test configuration.
7. Create or select a project/workspace context and bind it to a draft or existing session.
8. Create a schedule, disable/enable it, run it now, and delete it.
9. Select a default model from the host catalog and confirm no provider credential fields are rendered.
10. Run a 074 chat/session flow after settings changes and confirm REST/SSE or live behavior still works.

## Final Safety Gates

```powershell
git diff --check
git diff --name-only | Select-String "^openspec/"
```

Also run the public-safety scans defined in `docs/loopplane-agent-board.md`.

Expected outcome: no whitespace errors, no raw `openspec/` changes, and no public-safety findings.

## Rollback Guidance

- Keep existing read-only inspection as the compatibility baseline.
- If a mutation surface causes issues, disable that surface and keep list/read endpoints available.
- If model defaults cause issues, ignore the saved default and continue using per-session model selection from 074.
- If schedule management causes issues, disable schedule mutations while preserving existing scheduler behavior.
- Capability management is additive; reverting the web/API settings routes and UI restores the prior 074 web behavior.
