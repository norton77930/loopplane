# Quickstart: Code Review Remediation Validation

Run from the repository root in PowerShell.

## P0 Gate Restoration

```powershell
uv sync --locked
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop test
```

Expected result: all commands exit successfully. Web test output should not
include the current `act(...)` warnings after the P3 cleanup task is complete.

## Focused Public-Safety Regression

```powershell
uv run pytest tests/unit/test_mcp_adapter.py tests/unit/test_web_tools.py
```

Expected result: tests prove injected token/key/signature/password values do
not appear in MCP adapter or web-fetch model-visible errors.

## Spec Task Audit

```powershell
uv run pytest tests/contract/test_spec_task_audit.py
```

Expected result: historical verified-unit drift is either absent or listed in
`docs/spec-task-audit-exceptions.md`; new unapproved drift fails the test.

## Repository Safety

```powershell
git diff --check
git diff --name-only | Select-String "^openspec/"
git diff --name-only | Select-String "^[A-Za-z]:\\|sk-|ghp_|api_key|secret|password|token"
if (Test-Path sensitive-scan.txt) {
    git diff | Select-String -Pattern (Get-Content sensitive-scan.txt)
}
```

Expected result: whitespace check passes; no `openspec/` changes; public-safety
scans have no matches.

## Rollback Guidance

- CI/lockfile changes: revert `uv.lock` or workflow edits as a small isolated
  rollback.
- Desktop/web alignment: revert `apps/desktop` changes and keep desktop gate
  failing visibly until a replacement fix is applied.
- Error sanitization and web-fetch bounding: revert adapter/tool files and
  associated tests together.
- Spec audit: revert `tests/contract/test_spec_task_audit.py` and
  `docs/spec-task-audit-exceptions.md` together.
