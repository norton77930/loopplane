# Data Model: MCP Resources + Host-Token Auth

Additive; inside `loopplane.adapters.mcp`. No content-model/event-schema change. Per
[ADR 0007](../../docs/adr/0007-mcp-resources.md).

## MCPServerConfig (modified — additive)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `auth_token` | `str \| None = None` | NEW — host-supplied bearer token; sent as `Authorization: Bearer <token>` on http/sse transports (websocket/stdio: not applied). None = off (byte-identical). |

(Existing: name, transport, command, args, url.) The token is secret-bearing config — never echoed.

## Synthetic resource tools (new — registered per resource-supporting server)

| Tool | Input | Dispatch | Result → blocks |
| ---- | ----- | -------- | --------------- |
| `{server}:list_resources` | (none) | `session.list_resources()` | the resource listing (uri/name/description) as `TextBlock` |
| `{server}:read_resource` | `{ uri: string }` | `session.read_resource(uri)` | `ReadResourceResult.contents` → `TextBlock` (text) / `ImageBlock` (image blob) |

Registered alongside discovered tools (a `ToolDescriptor` each, `source=external-server:{name}`),
dispatched via a resource registry distinct from the real-tool map so `invoke` routes them to the
session resource APIs (everything else → `call_tool`, unchanged).

## Rules (from FRs + ADR 0007)

| Rule | Source |
| ---- | ------ |
| Resources as Gateway-routed synthetic tools (list/read); reach the model only via the Gateway | FR-001, D1 |
| read_resource → existing TextBlock/ImageBlock; no content/event-schema change | FR-002, D1 |
| Reuse the pipeline + per-server isolation; resource-less server registers none (contained) | FR-003, D2 |
| Optional host-token → Authorization header on http/sse (websocket/stdio: not applied) | FR-004, D3 |
| Default-unused byte-identical; no new dependency | FR-005, D4 |
| Token public-safe (never echoed) | FR-006 |
| Small ADR 0007; interactive OAuth flow DEFERRED | FR-007, D5 |
