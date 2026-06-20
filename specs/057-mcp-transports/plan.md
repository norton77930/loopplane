# Implementation Plan: MCP SSE + WebSocket Transports

**Branch**: `057-mcp-transports` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/057-mcp-transports/spec.md`

**Boundary**: additive, **no ADR, no maintainer consult**. The MCP adapter already abstracts
transports; this adds two members + two branches reusing the SDK's vendored clients.

## Summary

Add `"sse"` + `"websocket"` to `MCPServerConfig.transport` (`config.py:18`, currently
`Literal["stdio", "http"]`), extend `_check_transport_fields` to require a `url` for both (mirroring
`http`), and add two branches to `adapter._connect_one` (`adapter.py:90-112`) using the MCP SDK's
`mcp.client.sse.sse_client` + `mcp.client.websocket.websocket_client` (both confirmed importable in
the installed SDK — no new dependency). Each branch yields `(read, write)` into the EXISTING
transport-agnostic `ClientSession` + discover/translate/call pipeline (unchanged). `stdio` + `http`
are byte-identical; no Gateway/event/content/runtime change.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: none new — `mcp.client.sse.sse_client` + `mcp.client.websocket.
websocket_client` are already shipped by the installed MCP SDK (verified). The transport-specific
imports live inside their `_connect_one` branch (mirroring the existing stdio/http imports).

**Storage**: N/A.

**Testing**: pytest, offline — the SDK transport clients stubbed/monkeypatched (no network),
mirroring the existing MCP adapter tests: an `sse` + a `websocket` config connect (via the stubbed
client) → tools discovered; `sse`/`websocket` without a `url` → a clear validation error; stdio/http
unchanged.

**Target Platform**: cross-platform library.

**Constraints**: additive (two Literal members + two branches); byte-identical for stdio/http; no new
dependency; no Gateway/event/content/runtime change; offline-tested. No ADR.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-006. ✅
- **IV. Boundary**: Wholly within `loopplane.adapters.mcp`; the transport abstraction already exists;
  no boundary crossed. ✅
- **V. Tool Gateway**: MCP tools still reach the runtime only via the Gateway-registered adapter;
  unchanged. ✅
- **VI. Event Bus**: No event/schema/content change. ✅
- **IX. Reference-not-clone**: Uses the SDK's own client transports (the canonical way). ✅
- **X. Testable Evolution**: Additive; byte-identical for existing transports; reversible;
  offline-tested. ✅

**Result**: PASS — additive, no ADR, no new dependency, no breaking contract.

## Project Structure

### Documentation (this feature)

```text
specs/057-mcp-transports/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/mcp-transports.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/adapters/mcp/config.py    # MODIFIED: transport Literal += "sse","websocket";
                                        #   _check_transport_fields requires url for both
src/loopplane/adapters/mcp/adapter.py   # MODIFIED: _connect_one += an sse branch (sse_client) +
                                        #   a websocket branch (websocket_client); shared ClientSession
tests/<mcp adapter tests>               # MODIFIED/NEW: offline sse + websocket connect + url validation
```

**Structure Decision**: Two Literal members + a validation arm + two `_connect_one` branches. Each
branch does the transport-specific connect (imported inside the branch) and yields `(read, write)`
for the shared `ClientSession` — everything downstream (discover/translate/call) is unchanged. Tests
stub the SDK client (no network), mirroring the existing transport tests.

## Complexity Tracking

> Trivial additive extension of an existing abstraction. No new dependency, no ADR, no boundary
> crossing. Not a Constitution concern.
