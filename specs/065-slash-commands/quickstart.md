# Quickstart / Validation: Backend-Semantic Slash Commands

See [contracts/slash-commands.md](contracts/slash-commands.md), [data-model.md](data-model.md). A host
command surface (`loopplane.commands`) over existing seams, on the CLI + web/API. Additive; routes
only through existing seams; runtime core byte-identical; no schema/reason/dependency/ADR.

## Run the tests

```powershell
pytest tests/ -k "command or slash or compact" -q
pytest -q   # full suite (additive proof)
```

Expected: green; non-command input byte-identical; SCHEMA_VERSION unchanged; the existing CLI/webapi
suites pass.

## Validation scenarios (mirror the acceptance scenarios)

1. **/cost** — an owned budget-tracked session → the registry/`POST /commands`/CLI returns the
   accumulated USD + monthly spend (064). (FR-002, SC-001)
2. **/model** — returns the available models (read-only list). (FR-002)
3. **/memory** — returns the memory entries (`host.inspect_memory`), caller-scoped. (FR-002)
4. **/compact** — a compactable session → compacted via `compact_history` (same as the loop); a
   nothing-to-compact session → a clean result. (FR-003, SC-002)
5. **unknown command** — `/bogus` → `CommandResult(kind="unknown")`; never crashes, never sent to the
   model. (FR-001)
6. **non-command input** — ordinary text is unchanged (byte-identical). (FR-005, SC-003)
7. **owner-scoping / public-safe** — `/cost`/`/compact` on a non-owned session → 404; results carry
   no DSN/secret/other-principal. (FR-006)

## Manual gate checks (autopilot)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway` — commands call host seams,
not the gateway; `test_public_safety`) + the events serialize/`SCHEMA_VERSION` tests (UNCHANGED) + the
api-reference bijection (the NEW `loopplane.commands` package must be registered in
`docs/api-reference.md`). NOTE: run the full pytest + any verify Workflow at DIFFERENT times
(CPU-contention flake); scan new test files for forbidden tokens before committing.
