# Contract: MCP SSE + WebSocket Transports

Additive extension of `MCPServerConfig.transport` + `adapter._connect_one`. Reuses the MCP SDK's
client transports; no new dependency; stdio/http unchanged.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `MCPServerConfig.transport` | `Literal["stdio","http","sse","websocket"]` | += `sse`, `websocket` (additive). |

## Behavior

| Case | Result |
| ---- | ------ |
| `transport: "sse"` + `url` | Connects via `mcp.client.sse.sse_client`; tools discovered + callable through the existing pipeline. |
| `transport: "websocket"` + `url` | Connects via `mcp.client.websocket.websocket_client`; tools discovered + callable. |
| `sse`/`websocket` without `url` | Clear config validation error (mirroring `http`). |
| `stdio` / `http` configs | Byte-identical to today (unchanged). |
| SDK transport absent (older SDK) | Surfaced as a per-server connect error (contained; other servers unaffected) — the import is branch-local. |

## Invariants

- Additive: two new Literal members + a validation arm + two `_connect_one` branches; everything
  after `(read, write)` (ClientSession, discover, translate, call) is the existing shared pipeline.
- No new dependency (the MCP SDK ships both clients); transport imports are branch-local.
- stdio/http byte-identical; MCP tools still reach the runtime only via the Gateway-registered
  adapter (V); no event/schema/content change (VI).
- Offline-testable (the SDK transport client stubbed; no network).
- Out of scope: MCP resources + OAuth (unit 059); interactive auth flows.
