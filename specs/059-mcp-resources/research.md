# Research: MCP Resources + Host-Token Auth

Settled by **[ADR 0007](../../docs/adr/0007-mcp-resources.md)** (small, maintainer-pre-approved). No
open `NEEDS CLARIFICATION`.

## Decision 1 — Resources as Gateway-routed synthetic tools (ADR 0007 D1)

**Decision**: Register `{server}:list_resources` (no input) + `{server}:read_resource` (`{uri}`) as
synthetic per-server Gateway tools when the server supports resources; dispatch to
`session.list_resources()` / `session.read_resource(uri)`; translate to existing
`TextBlock`/`ImageBlock` (the listing as text; `ReadResourceResult.contents` text→TextBlock, image
blob→ImageBlock).

**Rationale**: Resources reach the model ONLY via the Gateway (V) as normal tool results — no new
content type, no event-schema change. Reuses the existing discover/translate/invoke pipeline.

**Alternatives considered**: a new content-model `ResourceBlock` / a new event (rejected — would
change the content model/Event Bus, VI; resources-as-tool-results is sufficient + additive); a host
REST endpoint to fetch resources (rejected — would bypass the Gateway, V).

## Decision 2 — Per-server isolation / contained probe (ADR 0007 D2)

**Decision**: Probe `list_resources` at connect; register the resource tools only on success; a
failure (server without resource support) is contained (the existing per-server isolation) → no
resource tools, the server's tools unaffected.

**Rationale**: Resource support is optional in MCP; a resource-less server must not break.

## Decision 3 — Host-token transport auth (ADR 0007 D3)

**Decision**: An optional config token; when set, pass `headers={"Authorization": f"Bearer
{token}"}` to `streamablehttp_client` / `sse_client` (the SDK transports that accept `headers`).
`websocket_client` accepts only `url` (SDK limitation) → token-header auth is NOT applied to
websocket (documented); stdio needs none. The token is never echoed (VII).

**Rationale**: Real MCP servers are often token-protected; config-supplied (host-injected) auth is
the additive, non-interactive way to connect. The websocket gap is an SDK constraint, recorded.

**Alternatives considered**: the interactive browser authorization-code/PKCE flow (DEFERRED — a
larger unit; needs a redirect/callback surface); url-embedded credentials (left to the embedder).

## Decision 4 — Default-unused byte-identity (ADR 0007 D4)

**Decision**: A server with no resources + no token behaves exactly as today; no new dependency.

**Rationale**: Impose nothing on existing MCP configs; reuse-first.

## Out of scope (ADR 0007 D5)

The interactive browser OAuth authorization-code (+ PKCE) flow; resource subscriptions/notifications;
MCP prompts. Later units if needed.
