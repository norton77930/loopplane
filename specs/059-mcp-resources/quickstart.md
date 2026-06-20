# Quickstart / Validation: MCP Resources + Host-Token Auth

See [contracts/mcp-resources.md](contracts/mcp-resources.md), [data-model.md](data-model.md), and
[ADR 0007](../../docs/adr/0007-mcp-resources.md). MCP resources as Gateway-routed synthetic tools +
a config-supplied transport token; additive, no content/event change.

## Run the MCP tests

```powershell
pytest tests/ -k mcp -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the existing MCP tests pass unchanged + the new resource/token tests pass.

## Validation scenarios (mirror the acceptance scenarios)

1. **List + read resources** — a resource-supporting (stubbed) server exposes
   `{server}:list_resources` + `{server}:read_resource`; calling them returns the listing + a
   resource's contents as `TextBlock`/`ImageBlock`. (FR-001/002, SC-001)
2. **Token header** — a config `auth_token` on an http/sse server → the stubbed transport receives
   `Authorization: Bearer <token>`; no token → unchanged. (FR-004, SC-002)
3. **Resource-less server** — registers no resource tools (contained probe), its tools work; no
   crash. (FR-003, SC-003)
4. **No content change** — resource reads return existing block types; SCHEMA_VERSION unchanged.
   (FR-002, SC-003)
5. **Public-safe** — the token never appears in tool output/errors/logs. (FR-006, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the events serialize/`SCHEMA_VERSION` tests (unchanged — no event/content change).
