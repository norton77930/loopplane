# ADR 0007: MCP resources & host-token transport auth

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (pre-approved as a *small* ADR for unit 059 at the Tier-4 plan
  step); spec 059 (mcp-resources).
- **Related**: Constitution **V** (resources reach the model ONLY through the Tool Gateway — as
  synthetic per-server tools), **VI** (no event-schema/content change — resource contents are the
  existing `TextBlock`/`ImageBlock` tool results), **IV** (the MCP adapter boundary), **X** (additive,
  default-unused byte-identical, reversible). Seventh ADR (after 0001–0006).

## Context

The MCP adapter (`loopplane.adapters.mcp`) discovers a server's **tools** (`session.list_tools()`)
and routes calls through the Gateway adapter SPI, translating results to `TextBlock`/`ImageBlock`
(adapter.py:130-181). Gap G12 (C/D) wants two more MCP capabilities: **resources** (the data a
server publishes — `list_resources`/`read_resource`) and **auth** (connecting to a protected
server). The MCP SDK `ClientSession` exposes `list_resources(cursor)` + `read_resource(uri)`; the
`streamablehttp_client` and `sse_client` transports accept a `headers` argument; `websocket_client`
accepts only `url`.

## Decision

- **D1 — Resources as Gateway-routed synthetic tools.** When a configured server supports resources,
  the adapter registers two synthetic per-server tools — `{server}:list_resources` (no input) and
  `{server}:read_resource` (`{uri}`) — alongside the discovered tools. They dispatch to
  `session.list_resources()` / `session.read_resource(uri)`; the result is translated to the EXISTING
  tool-result block types (`TextBlock` for text contents + the resource listing; `ImageBlock` for
  image blobs). **The ratified ingress: a resource reaches the model ONLY through the Gateway, as a
  normal tool result — no new content-model or event-schema type, no `SCHEMA_VERSION` bump.**
- **D2 — Per-server isolation.** Resource tools are registered only when the server actually supports
  resources; a `list_resources` probe failure is **contained** (the existing per-server failure
  isolation), so a resource-less server registers no resource tools and its tools work unchanged.
- **D3 — Host-token transport auth (config-supplied).** The MCP server config gains an optional
  host-supplied token; when set, the adapter sends `Authorization: Bearer <token>` via the transport
  `headers` for **http + sse** (the SDK transports that accept `headers`). `websocket_client` takes
  no `headers` (an SDK limitation) → token-header auth is **not applied to websocket** (documented;
  url-embedded credentials remain the embedder's option); **stdio** (local) needs none. The token is
  **public-safe**: never echoed in tool output, errors, or logs (VII).
- **D4 — Default-unused, byte-identical.** A server with no resources + no token behaves exactly as
  today; no new dependency.
- **D5 — Deferred.** The interactive browser OAuth **authorization-code (+ PKCE) flow**, resource
  **subscriptions/notifications**, and MCP **prompts** are out of scope — later units if needed.

## Consequences

- **Enables G12 C/D**: the model can list + read a server's resources (Gateway-routed) and the
  adapter can connect to a token-protected http/sse MCP server. Contained, additive, reversible.
- **No content-model / event-schema change (VI)**: resources are surfaced as existing tool-result
  blocks; the Tool Gateway remains the single ingress (V). The only new surface is two synthetic tool
  names per resource-supporting server + an optional config token field.
- **Documented limitations**: websocket header-auth is unsupported by the SDK transport (token not
  applied there); the interactive OAuth flow + subscriptions + prompts are deferred.
- **Public-safe**: the host token is never surfaced (VII).
