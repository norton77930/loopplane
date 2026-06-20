# Quickstart / Validation: Named Permission Modes

See [contracts/permission-modes.md](contracts/permission-modes.md), [data-model.md](data-model.md).
Named permission-mode presets over the existing 039 DSL, selected by `RuntimeConfig.permission_mode`.
Additive; composes the existing decider; default-off byte-identical; no schema/dependency/ADR.

## Run the tests

```powershell
pytest tests/ -k "permission or mode or governance" -q
pytest -q   # full suite (additive proof)
```

Expected: green; `permission_mode=None` byte-identical; SCHEMA_VERSION unchanged; the existing
governance suite passes.

## Validation scenarios (mirror the acceptance scenarios)

1. **acceptEdits** — a file-edit tool is allowed without a prompt; another tool follows `default=ask`.
   (FR-001/003, SC-001)
2. **bypassPermissions** — every tool is allowed (allow-all). (FR-003, SC-001)
3. **dontAsk** — a decision that would be `ask` is auto-resolved to `allow` (no prompt); a `deny`
   rule still denies. (FR-003)
4. **plan** — behaves as the 038 plan mode (read-only until approved). (FR-003)
5. **default None byte-identity** — no preset built; the decider/permission suite passes unchanged.
   (FR-004, SC-002)
6. **precedence / validation** — `acceptEdits` + explicit `permission_rules` → `ConfigError`; an
   unknown mode → `ConfigError`. (FR-005, SC-002)

## Manual gate checks (autopilot)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the
events serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the api-reference bijection (if a new public
name is exported). NOTE: run the full pytest + any verify Workflow at DIFFERENT times (CPU-contention
flake); scan new test files for forbidden tokens before committing.
