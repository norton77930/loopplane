# Tasks: MCP Resources + Host-Token Auth

**Feature**: 059-mcp-resources | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0007](../../docs/adr/0007-mcp-resources.md)

**Scope**: additive, a small ADR (0007) — MCP resources surfaced as Gateway-routed synthetic tools
({server}:list_resources / :read_resource) returning existing TextBlock/ImageBlock + an optional
config auth_token (Authorization header on http/sse). Confined to loopplane.adapters.mcp;
default-unused byte-identical; no content/event-schema change.

**Tests**: requested.

## Phase 1: Config token (Foundational)

- [ ] T001 In `src/loopplane/adapters/mcp/config.py`: add `auth_token: str | None = None` to
  `MCPServerConfig`. No validation change beyond the existing transport checks; default None = off.

## Phase 2: Transport auth (P1)

- [ ] T002 In `src/loopplane/adapters/mcp/adapter.py` `_connect_one`: when `config.auth_token` is
  set, pass `headers={"Authorization": f"Bearer {config.auth_token}"}` to the `streamablehttp_client`
  (http) and `sse_client` (sse) branches. `websocket_client` takes no `headers` (SDK limitation) —
  leave it as-is with a one-line comment; stdio needs none. Never log/echo the token.

## Phase 3: Resources as synthetic Gateway tools (P1) 🎯

- [ ] T003 In `_connect_one`, after the tool discovery loop: PROBE resources with
  `await session.list_resources()` inside a contained try/except (a server without resource support →
  no resource tools, no crash; reuse the per-server isolation posture). On success, register two
  synthetic `ToolDescriptor`s — `{config.name}:list_resources` (empty/object input schema) and
  `{config.name}:read_resource` (input schema `{type: object, properties: {uri: {type: string}},
  required: [uri]}`) — with `source=f"external-server:{config.name}"`, and record them in a resource
  dispatch map (e.g. `self._resource_tools: dict[str, tuple[session, kind]]`) distinct from
  `self._tools`.
- [ ] T004 In `invoke`: route `{server}:list_resources` → `session.list_resources()` (return the
  listing — uri/name/description per resource — as a `TextBlock`) and `{server}:read_resource` (read
  `uri` from call_input; `session.read_resource(AnyUrl(uri))`) → translate `ReadResourceResult.
  contents` (text → `TextBlock`; blob+mimeType image → `ImageBlock`) — mirroring the existing
  `call_tool` result translation; on failure yield the existing normalized `ErrorOutput`. Real tools
  still dispatch via `self._tools` → `call_tool` (unchanged).

## Phase 4: Tests (P1/P2)

- [ ] T005 Add MCP resources tests (offline, the `ClientSession` + transports stubbed/monkeypatched —
  NO network, mirroring the existing MCP adapter tests): (a) a resource-supporting stub →
  `{server}:list_resources` + `{server}:read_resource` registered; calling them returns the listing
  + a resource's text/image as the existing block types; (b) a config `auth_token` on an http/sse
  server → the stubbed transport receives the `Authorization: Bearer` header; no token → unchanged;
  (c) a resource-less stub (list_resources raises) → no resource tools, the server's tools work, no
  crash; (d) the token never appears in any tool output/error.

## Phase 5: Gates

- [ ] T006 Run the four gates green: `ruff check`, `ruff format --check src tests`, `mypy src`
  (strict), `pytest` (full — additive + default-unused byte-identity). Confirm the structural audits
  (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) + the events
  serialize/`SCHEMA_VERSION` tests (unchanged — no content/event change) + the existing MCP suite
  pass. No new public name expected (api-reference unchanged unless a name is exported).

## Dependencies

- T001 → T002. T001/T003 → T004. T002/T004 → T005 → T006 (gates last).

## Implementation strategy

- Confined to `loopplane.adapters.mcp` (config + adapter + tests). May be done inline or via a fork;
  then the four gates + the structural audits + the api-reference-bijection/events tests + an
  adversarial verify (resources reach the model only via the Gateway / no content-model change;
  per-server isolation for resource-less servers; token public-safety / no echo; default-unused
  byte-identity) before commit — Workflow if available, else MANUAL. Commit only on a clean review /
  GO; fix + re-verify FRESH otherwise.
- Additive; ADR 0007; interactive OAuth flow deferred.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
