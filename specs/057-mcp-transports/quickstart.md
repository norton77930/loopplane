# Quickstart / Validation: MCP SSE + WebSocket Transports

See [contracts/mcp-transports.md](contracts/mcp-transports.md) + [data-model.md](data-model.md).
Additive — two new MCP transports (`sse`, `websocket`) reusing the SDK's vendored client transports;
no ADR, no new dependency; stdio/http byte-identical.

## Run the MCP adapter tests

```powershell
pytest tests/ -k mcp -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the existing stdio/http MCP tests pass unchanged + the new sse/websocket tests pass.

## Validation scenarios

1. **SSE connect** — `transport: "sse"` + a `url` → connects via the (stubbed) SDK `sse_client`;
   tools discovered + callable. (FR-001/003, SC-001)
2. **WebSocket connect** — `transport: "websocket"` + a `url` → connects via the (stubbed) SDK
   `websocket_client`; tools discovered. (FR-001/003, SC-001)
3. **url validation** — `sse`/`websocket` without a `url` → a clear validation error. (FR-002, SC-002)
4. **stdio/http unchanged** — existing transport configs + tests behave identically. (FR-005, SC-002)
5. **No new dependency** — the four gates + the existing MCP suite pass; the SDK transports are
   already present. (FR-004, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`).
