# Feature Specification: MCP Resources + Host-Token Auth

**Feature Branch**: `059-mcp-resources`

**Created**: 2026-06-20

**Status**: Draft — **plan authors a small ADR (0007); no maintainer consult**

**Input**: User description: "MCP resources (list/read) surfaced Gateway-routed + host-injected-token authentication for the http/sse/websocket MCP transports (gap G12 C/D). Resources reach the model only through the Tool Gateway — as synthetic per-server resource tools whose results are normal tool-result blocks (no content-model change). Auth is a config-supplied bearer/token passed to the transport (NOT an interactive browser authorization-code flow — that is DEFERRED). Unit 059, Tier-4. Additive; a small ADR."

## ⚠️ Boundary note (read first)

**Additive — a small ADR (0007), no consult.** The MCP adapter already discovers a server's *tools*
(`session.list_tools()`) and routes calls through the Gateway adapter SPI, translating results to
normal `TextBlock`/`ImageBlock` outputs (adapter.py:130-181). This unit adds two things, both
additive: (1) **resources** — `list_resources`/`read_resource` surfaced as **synthetic per-server
Gateway tools** so a resource reaches the model only via the Gateway (V), as a normal tool result
(no content-model/event-schema change); (2) **host-token auth** — an optional config-supplied
token/header passed to the http/sse/websocket transport so the adapter can connect to an
authenticated MCP server. A small **ADR (0007)** records the resource-as-Gateway-tool ingress. The
interactive browser authorization-code flow is **out of scope (deferred)**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The model can list + read MCP resources (Priority: P1)

An embedder configures an MCP server that exposes resources; the model can list the server's
resources and read a resource's contents — through the Tool Gateway, like any other tool.

**Why this priority**: This is gap G12 (C/D) — the adapter today exposes only MCP *tools*, so a
server's *resources* (files/docs/data the server publishes) are unreachable.

**Independent Test** (offline, the MCP `ClientSession` stubbed — no network): a configured server
with resources exposes `{server}:list_resources` + `{server}:read_resource` Gateway tools; calling
them returns the resource list / a resource's content as tool-result text (+ image when applicable).

**Acceptance Scenarios**:

1. **Given** a server that supports resources, **When** the adapter connects, **Then** synthetic
   `{server}:list_resources` and `{server}:read_resource` tools appear in the Gateway tool set.
2. **Given** `{server}:read_resource` called with a resource `uri`, **When** it runs, **Then** the
   resource's contents are returned as normal tool-result blocks (text/image) — reachable by the
   model only via the Gateway.

---

### User Story 2 - The adapter authenticates to a protected MCP server (Priority: P1)

An embedder points the adapter at an MCP server that requires a bearer token; a config-supplied
token is sent on the http/sse/websocket transport so the connection authenticates.

**Why this priority**: A real MCP server is often behind auth; without a way to supply a token the
adapter can't connect to it.

**Independent Test**: a server config carrying an `auth_token` (or headers) passes an
`Authorization: Bearer <token>` header to the transport client (asserted via the stubbed transport);
stdio (local) ignores it.

**Acceptance Scenarios**:

1. **Given** a config with a token for an http/sse/websocket server, **When** the adapter connects,
   **Then** the transport receives the `Authorization` header (config-supplied; host-injected).
2. **Given** no token, **When** the adapter connects, **Then** behavior is unchanged (byte-identical).

---

### User Story 3 - Contained, additive, no content change (Priority: P2)

A server that does NOT support resources is unaffected (the resource tools are simply not
registered; a resource probe failure is contained per the existing per-server isolation). Resource
contents reach the model as the existing tool-result block types — no content-model/event-schema
change. The token is never echoed/logged.

**Why this priority**: Must not break resource-less servers, must not change the content model, and
must keep the token public-safe.

**Independent Test**: a resource-less server registers only its tools (no resource tools, no crash);
a resource read returns existing block types; the token never appears in output/logs.

**Acceptance Scenarios**:

1. **Given** a server without resource support, **When** the adapter connects, **Then** no resource
   tools are registered and the server's tools work as before (contained probe, no crash).
2. **Given** a resource read, **When** it returns, **Then** the output is the existing
   `TextBlock`/`ImageBlock` types (no new content type); the token is not echoed.

---

### Edge Cases

- **server without resource support**: no resource tools registered; a `list_resources` probe
  failure is contained (per-server isolation), the server's tools still work.
- **read_resource of an unknown uri**: a normalized adapter error (the existing error path), the run
  continues.
- **token on stdio**: ignored (local transport needs none).
- **no token (default)**: byte-identical to today.
- **large/binary resource**: returned via the existing block translation (text/image); the existing
  output-size limits apply (Gateway pipeline unchanged).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a configured MCP server supports resources, the adapter MUST surface
  `{server}:list_resources` and `{server}:read_resource` as **Gateway-routed synthetic tools**
  (registered like discovered tools; reachable only via the Gateway, V).
- **FR-002**: `{server}:read_resource` MUST accept a resource `uri` and return the resource's
  contents as the EXISTING tool-result block types (`TextBlock`/`ImageBlock`) — **no content-model
  or event-schema change**. `{server}:list_resources` returns the resource list as text.
- **FR-003**: Resource access MUST reuse the existing connect/translate/invoke pipeline + per-server
  failure isolation; a server WITHOUT resource support registers no resource tools and is unaffected
  (a probe failure is contained, no crash).
- **FR-004**: The MCP server config MUST support an optional **host-supplied token/headers** sent on
  the http/sse/websocket transport (an `Authorization: Bearer <token>` header); stdio ignores it.
- **FR-005**: The feature MUST be **additive / byte-identical** when unused: a server with no
  resources + no token behaves exactly as today; no new dependency.
- **FR-006**: The token MUST be **public-safe** — never echoed in tool output, errors, or logs (VII).
- **FR-007**: The plan authors a **small ADR (0007)** recording the resource-as-Gateway-tool ingress
  (and the config-token transport auth). The **interactive browser authorization-code flow is
  DEFERRED** (out of scope).

### Key Entities *(include if feature involves data)*

- **Synthetic resource tools**: `{server}:list_resources` (no input) + `{server}:read_resource`
  (`{uri}`), registered alongside discovered tools, dispatched to `session.list_resources()` /
  `session.read_resource(uri)`.
- **MCPServerConfig token/headers**: an optional config field carrying the host-supplied bearer
  token / headers for the http/sse/websocket transport.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A resource-supporting server exposes working `list_resources` + `read_resource` Gateway
  tools returning resource contents as existing block types — in 100% of covered scenarios (offline).
- **SC-002**: A config token is sent as the transport `Authorization` header; no token → unchanged.
- **SC-003**: A resource-less server is unaffected (no resource tools, no crash); the token is never
  echoed; no content-model/event-schema change (SCHEMA_VERSION unchanged); the four gates + existing
  MCP suite pass.

## Assumptions

- The MCP SDK `ClientSession` exposes `list_resources()` + `read_resource(uri)` (standard MCP); the
  transports (streamablehttp/sse/websocket) accept a `headers` argument for the token. The implement
  confirms the exact SDK APIs.
- Resource tools dispatch via a per-adapter registry distinct from the tool registry (or a marker),
  reusing the existing result→block translation. Reuse the Gateway adapter SPI + per-server isolation.
- **Out of scope / DEFERRED**: the interactive browser OAuth authorization-code (+ PKCE) flow;
  resource subscriptions/notifications; prompts (MCP prompts) — only resources + a static token here.
- Additive; default-unused byte-identical; public-safe (no token echo); offline-testable. The plan
  authors ADR 0007. Per Constitution IX the concept is borrowed but re-derived against this adapter.
