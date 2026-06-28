# Quickstart: Web Parity Foundation

## Prerequisites

- Work from the repository root on `main`.
- Do not modify or commit raw `openspec/`.
- Use existing configured model providers and model catalog; do not add browser-side provider secret entry.

## Backend Validation

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest --basetemp "$env:TEMP\loopplane-pytest-074"
```

Expected outcome: backend unit, integration, contract, replay, principal-scoping, and compatibility tests pass.

## Web Validation

```powershell
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected outcome: transport boundary, live reconnect, approval/question response, abort, session management, and type-artifact tests pass with a successful production build.

## Desktop Compatibility

```powershell
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop test
```

Expected outcome: desktop remains compatible with existing web state/components until unit 077.

## Manual Smoke Scenario

1. Start the web/API host and web app using the existing project workflow.
2. Log in with an existing test token.
3. Start a draft chat, select a model, and submit the first prompt.
4. Confirm the session streams over the selected transport.
5. Trigger an approval or question flow and answer it.
6. Abort an in-flight turn.
7. Simulate a browser reconnect and verify the conversation is restored without duplicate visible entries.
8. Star, fork, search, and bulk-delete owned sessions.
9. Confirm existing REST/SSE history and session event flows still work.

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

## Rollback Guidance

- Keep REST/SSE as the compatibility baseline.
- If live transport causes issues, disable live-channel selection and route web chat through the existing REST/SSE transport.
- Additive session metadata can be ignored by older clients.
- Type-artifact workflow can be reverted with its generated/validated artifacts because backend runtime event semantics remain unchanged.
