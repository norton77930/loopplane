# Tasks: MCP SSE + WebSocket Transports

**Feature**: 057-mcp-transports | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: small + additive, no ADR — two new `transport` Literal members + a url-validation arm +
two `_connect_one` branches reusing the MCP SDK's already-shipped `sse_client` / `websocket_client`;
stdio/http byte-identical; no new dependency.

**Tests**: requested.

## Phase 1: Config (Foundational)

- [ ] T001 In `src/loopplane/adapters/mcp/config.py`: extend `MCPServerConfig.transport` to
  `Literal["stdio", "http", "sse", "websocket"]`; in `_check_transport_fields` require a `url` for
  `sse` + `websocket` (mirror the `http` arm — a clear "requires a url" error). stdio/http unchanged.

## Phase 2: Adapter branches (P1) 🎯

- [ ] T002 In `src/loopplane/adapters/mcp/adapter.py` `_connect_one`: add an `sse` branch
  (`from mcp.client.sse import sse_client`; `read, write = await server_stack.enter_async_context(
  sse_client(config.url))`) and a `websocket` branch (`from mcp.client.websocket import
  websocket_client`; same shape) — branch-local imports mirroring the existing stdio/http branches;
  each yields `(read, write)` into the EXISTING `ClientSession(read, write)` + discover/translate/
  call pipeline (unchanged). Handle the SDK return shape (sse_client yields `(read, write)`;
  websocket_client likewise — confirm the exact tuple arity like the streamablehttp 3-tuple if
  needed).

## Phase 3: Tests (P1/P2)

- [ ] T003 Add MCP adapter tests (offline, the SDK transport client stubbed/monkeypatched — NO
  network, mirroring the existing transport tests): (a) an `sse` config + a `url` connects via the
  stubbed `sse_client` and tools are discovered; (b) a `websocket` config likewise; (c) `sse` /
  `websocket` without a `url` → a clear validation error; (d) confirm stdio/http tests still pass
  unchanged. Mirror the existing MCP adapter test harness/fixtures.

## Phase 4: Gates

- [ ] T004 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + stdio/http byte-identity). Confirm the structural audits
  (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the existing MCP suite pass.
  No new public name expected (no api-reference change unless a name is exported).

## Dependencies

- T001 → T002 → T003 → T004 (gates last).

## Implementation strategy

- Small additive change (config Literal + two adapter branches + tests). May be done inline or via a
  fork; then the four gates + the structural audits + an adversarial verify (additive byte-identity
  for stdio/http, correct branch wiring, the url validation, no new dependency) before commit —
  Workflow if available, else MANUAL. Commit only on a clean review / GO.
- Additive; no ADR; no Gateway/event/content/runtime change.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
