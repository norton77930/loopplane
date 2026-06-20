# Data Model: MCP SSE + WebSocket Transports

Additive; inside `loopplane.adapters.mcp`. No event/content/runtime change.

## MCPServerConfig.transport (modified — additive)

| Member | Requires | Notes |
| ------ | -------- | ----- |
| `stdio` | `command` | existing — unchanged |
| `http` | `url` | existing — unchanged |
| `sse` | `url` | NEW — connect via `mcp.client.sse.sse_client` |
| `websocket` | `url` | NEW — connect via `mcp.client.websocket.websocket_client` |

`_check_transport_fields` gains: `sse`/`websocket` without a `url` → a clear validation error
(mirroring the `http` check).

## _connect_one branches (modified — additive)

| transport | connect | yields |
| --------- | ------- | ------ |
| `sse` | `sse_client(config.url)` | `(read, write)` → the shared `ClientSession` |
| `websocket` | `websocket_client(config.url)` | `(read, write)` → the shared `ClientSession` |

Everything after `(read, write)` — `ClientSession`, discover, translate, call — is the existing
transport-agnostic pipeline (unchanged).

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| transport Literal += sse, websocket (additive) | FR-001 |
| sse/websocket require a url (like http) | FR-002 |
| _connect_one branches via the SDK sse_client / websocket_client → shared ClientSession | FR-003 |
| No new dependency; transport imports inside the branch | FR-004 |
| stdio/http byte-identical; no Gateway/event/content/runtime change | FR-005 |
| Offline-tested (SDK transport stubbed) | FR-006 |
