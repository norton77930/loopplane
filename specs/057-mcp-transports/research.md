# Research: MCP SSE + WebSocket Transports

Small additive unit; no open `NEEDS CLARIFICATION`.

## Decision 1 — Extend the existing transport abstraction (additive)

**Decision**: Add `"sse"` + `"websocket"` to `MCPServerConfig.transport`
(`config.py:18`, `Literal["stdio", "http"]`); require a `url` for both in `_check_transport_fields`
(mirroring `http`); add two `_connect_one` branches yielding `(read, write)` into the existing shared
`ClientSession`.

**Rationale**: The adapter already selects a transport then runs a transport-agnostic
discover/translate/call pipeline (`adapter.py:90-112`); the change is purely "two more options".

**Alternatives considered**: a separate adapter per transport (rejected — needless duplication; the
existing one already abstracts the transport).

## Decision 2 — Reuse the MCP SDK's client transports (no new dependency)

**Decision**: Use `mcp.client.sse.sse_client` + `mcp.client.websocket.websocket_client` (both
verified importable in the installed SDK), imported INSIDE their `_connect_one` branch (mirroring the
existing `from mcp.client.stdio import stdio_client` / `streamablehttp_client` pattern).

**Rationale**: The SDK ships the canonical client transports; reuse-first; no new top-level
dependency. Branch-local imports keep the cost off the stdio/http paths + contain an absent
transport as a per-server connect error.

**Alternatives considered**: hand-rolling SSE/WebSocket clients (rejected — the SDK provides them);
adding a new dependency (unnecessary — already present).

## Decision 3 — Offline testing (stub the SDK client)

**Decision**: Mirror the existing MCP adapter tests — monkeypatch/stub the SDK transport client so a
config connects without network; assert tools are discovered + the `url` validation arm.

**Rationale**: Deterministic, offline (the suite's NFR); the new branches are exercised like the
existing transports.

## Out of scope

MCP resources (list/read) + OAuth (unit 059); interactive auth flows; any transport-specific tool
behavior beyond connection.
