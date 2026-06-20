# Feature Specification: MCP SSE + WebSocket Transports

**Feature Branch**: `057-mcp-transports`

**Created**: 2026-06-20

**Status**: Draft — additive, **no ADR, no maintainer consult**

**Input**: User description: "Add SSE and WebSocket client transports to the MCP tool adapter alongside the existing stdio + http transports (gap G12 A/B). The MCP SDK already ships both client transports; this is two new `transport` Literal members + two `_connect_one` branches reusing the existing connect/translate pipeline. Unit 057, Tier-4. Additive, no ADR, no new dependency."

## ⚠️ Boundary note (read first)

**Additive — no ADR, no consult.** The MCP adapter already abstracts transports: `MCPServerConfig.
transport` is a `Literal["stdio", "http"]` (config.py:18) and `adapter._connect_one`
(adapter.py:90-112) selects the transport, yielding `(read, write)` streams that feed a single
transport-agnostic `ClientSession`. This unit adds two more transport options (`sse`, `websocket`)
using the MCP SDK's already-vendored `sse_client` / `websocket_client`; everything after the streams
is unchanged. No new dependency; no Gateway/event/content/runtime change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect to an SSE or WebSocket MCP server (Priority: P1)

An embedder configures an MCP server that speaks the SSE or WebSocket transport (instead of stdio or
streamable-http) and its tools are discovered + callable exactly like any other MCP server's.

**Why this priority**: This is gap G12 (A/B) — the adapter today only does stdio + http, so MCP
servers exposed over SSE/WebSocket can't be used; both are standard MCP transports the SDK ships.

**Independent Test** (offline, the SDK transport stubbed/monkeypatched — no network): a config with
`transport: "sse"` (or `"websocket"`) + a `url` connects via the corresponding SDK client and the
existing discover/translate/call pipeline yields the server's tools.

**Acceptance Scenarios**:

1. **Given** an MCP server config with `transport: "sse"` + a `url`, **When** the adapter connects,
   **Then** it uses the SDK SSE client and the server's tools are discovered + callable.
2. **Given** `transport: "websocket"` + a `url`, **When** the adapter connects, **Then** it uses the
   SDK WebSocket client and the tools are discovered + callable.

---

### User Story 2 - Config validation + existing transports unchanged (Priority: P2)

The `sse`/`websocket` transports require a `url` (validated like `http`); the existing `stdio` +
`http` transports behave exactly as before.

**Why this priority**: The new options must validate consistently and impose nothing on existing
configs (additive, byte-identical for stdio/http).

**Independent Test**: `sse`/`websocket` without a `url` → a clear config validation error; `stdio` +
`http` configs + their tests are unchanged.

**Acceptance Scenarios**:

1. **Given** `transport: "sse"` (or `"websocket"`) with no `url`, **When** the config is validated,
   **Then** it raises a clear "requires a url" error (mirroring `http`).
2. **Given** existing `stdio`/`http` configs, **When** they connect, **Then** behavior is unchanged.

---

### Edge Cases

- **sse/websocket without a url**: clear validation error (like `http`).
- **transport-agnostic pipeline**: after `(read, write)`, the `ClientSession` + discover/translate/
  call path is shared — the new transports add no special-casing downstream.
- **SDK transport absent/old**: the import lives in the branch (like the existing stdio/http
  imports), surfaced as a connect error for that server (contained; other servers unaffected).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Add `"sse"` and `"websocket"` to the `MCPServerConfig.transport` Literal (additive;
  `"stdio"` + `"http"` remain).
- **FR-002**: Validate that `sse`/`websocket` configs carry a `url` (mirror the existing `http`
  check); a missing `url` → a clear validation error.
- **FR-003**: Add an `_connect_one` branch for each new transport using the MCP SDK's `sse_client`
  (`mcp.client.sse`) / `websocket_client` (`mcp.client.websocket`), yielding `(read, write)` into
  the EXISTING transport-agnostic `ClientSession` + discover/translate/call pipeline (unchanged).
- **FR-004**: **No new dependency** (the MCP SDK already ships both client transports); the
  transport-specific imports live inside their `_connect_one` branch (mirroring stdio/http).
- **FR-005**: **Additive / byte-identical for existing transports** — `stdio` + `http` configs +
  their tests behave exactly as before; no Gateway/event/content/runtime change (V/VI intact).
- **FR-006**: Offline-testable — the SDK transports stubbed/monkeypatched (no network); the new
  branches covered like the existing transport tests.

### Key Entities *(include if feature involves data)*

- **MCPServerConfig.transport**: the transport selector Literal, gaining `sse` + `websocket`.
- **`_connect_one` branch**: per-transport connect that yields `(read, write)` for the shared
  `ClientSession`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An `sse` and a `websocket` MCP server config each connect (via the SDK client) and
  their tools are discovered + callable, in 100% of covered scenarios (offline-tested).
- **SC-002**: `sse`/`websocket` without a `url` raises a clear validation error; `stdio`/`http`
  behavior + the existing MCP tests are unchanged.
- **SC-003**: No new dependency; no Gateway/event/content/runtime change; the four gates + the
  existing MCP adapter suite pass.

## Assumptions

- The MCP SDK (already a dependency / vendored) ships `mcp.client.sse.sse_client` +
  `mcp.client.websocket.websocket_client` returning `(read, write)` streams compatible with the
  existing `ClientSession` usage (mirroring `stdio_client` / `streamablehttp_client`). The implement
  confirms the exact SDK import paths + return shapes (websocket may need an SDK extra — if so, note
  it; do NOT add a hard dependency).
- Reuse the existing connect/translate/call pipeline + the MCP adapter test harness (offline,
  transports stubbed). Additive, no ADR, no consult.
- Out of scope: MCP resources (list/read) + OAuth (unit 059); interactive auth flows; any
  transport-specific tool behavior beyond connection.
