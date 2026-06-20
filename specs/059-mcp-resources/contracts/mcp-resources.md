# Contract: MCP Resources + Host-Token Auth

Additive extension of the MCP adapter: resources surfaced as Gateway-routed synthetic tools + an
optional config-supplied transport token. Per [ADR 0007](../../docs/adr/0007-mcp-resources.md). No
content-model/event-schema change; default-unused byte-identical.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `MCPServerConfig.auth_token` | `str \| None = None` | host-supplied bearer; `Authorization: Bearer` on http/sse (websocket/stdio: not applied). |
| `{server}:list_resources` | tool, no input | lists the server's resources (when supported). |
| `{server}:read_resource` | tool, `{uri: string}` | reads a resource's contents. |

## Behavior

| Case | Result |
| ---- | ------ |
| Server supports resources | `{server}:list_resources` + `{server}:read_resource` appear in the Gateway tool set. |
| `{server}:list_resources` called | The resource listing (uri/name/description) returned as a `TextBlock`. |
| `{server}:read_resource` with a `uri` | The resource contents returned as existing tool-result blocks (`TextBlock` text / `ImageBlock` image blob) — model-reachable only via the Gateway. |
| `read_resource` of an unknown uri / a failure | A normalized adapter error (existing path); the run continues. |
| Server WITHOUT resource support | No resource tools registered (a contained probe failure); the server's tools work unchanged. |
| Config `auth_token` on an http/sse server | `Authorization: Bearer <token>` sent on the transport. |
| `auth_token` on websocket | Not applied (SDK transport has no `headers`); documented limitation. |
| No `auth_token` (default) | Byte-identical to today. |

## Invariants

- Resources reach the model ONLY through the Gateway, as synthetic tools whose results are the
  EXISTING `TextBlock`/`ImageBlock` types — no new content type, no event-schema/SCHEMA_VERSION change
  (V/VI intact; recorded in ADR 0007).
- Reuses the existing discover/translate/invoke pipeline + per-server failure isolation; a
  resource-less server is unaffected (contained probe).
- The host token is public-safe — never echoed in tool output, errors, or logs (VII).
- Additive; default-unused byte-identical; no new dependency; confined to `loopplane.adapters.mcp`.
- Out of scope (deferred): the interactive browser OAuth authorization-code/PKCE flow; resource
  subscriptions/notifications; MCP prompts.
