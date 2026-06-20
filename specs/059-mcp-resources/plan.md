# Implementation Plan: MCP Resources + Host-Token Auth

**Branch**: `059-mcp-resources` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/059-mcp-resources/spec.md`

**Boundary**: settled by **[ADR 0007](../../docs/adr/0007-mcp-resources.md)** (small, maintainer-
pre-approved; authored at this plan step, no consult). Resources reach the model ONLY via the Gateway
(as synthetic per-server tools); resource contents are the existing tool-result block types (no
content/event-schema change). Additive + default-unused byte-identical.

## Summary

Extend the MCP adapter with resources + host-token auth. (1) **Resources**: at connect, if a server
supports resources, register two synthetic per-server Gateway tools — `{server}:list_resources`
(no input) and `{server}:read_resource` (`{uri}`) — alongside the discovered tools; dispatch them
to `session.list_resources()` / `session.read_resource(uri)` and translate the result to existing
`TextBlock`/`ImageBlock` outputs (the listing as text; `ReadResourceResult.contents` text→TextBlock,
image blob→ImageBlock). A `list_resources` probe failure is contained (per-server isolation) → a
resource-less server registers no resource tools. (2) **Auth**: an optional config token; when set,
send `Authorization: Bearer <token>` via the transport `headers` for http + sse (the SDK transports
that accept `headers`; websocket_client has none — documented limitation; stdio needs none). Token
public-safe (never echoed). Default-unused (no resources + no token) is byte-identical; no new
dependency. Confined to `loopplane.adapters.mcp`.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: none new — `ClientSession.list_resources()/read_resource()` + the
`headers` arg on `streamablehttp_client`/`sse_client` are already in the installed MCP SDK (verified).

**Storage**: N/A.

**Testing**: pytest, offline — the MCP `ClientSession` + transports stubbed/monkeypatched (no
network): a resource-supporting stub exposes `list_resources`/`read_resource` Gateway tools returning
the listing + a resource's text/image; a token config passes the `Authorization` header to the
stubbed transport; a resource-less stub registers no resource tools (contained); the token is never
in output.

**Target Platform**: cross-platform library.

**Constraints**: additive; resources reach the model only via the Gateway (V); no content-model/
event-schema change (VI — existing block types); default-unused byte-identical; token public-safe
(VII); per-server isolation; no new dependency. ADR 0007. Interactive OAuth flow deferred.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007 + ADR 0007. ✅
- **IV. Boundary**: Confined to `loopplane.adapters.mcp`; the runtime/event core untouched. ✅
- **V. Tool Gateway**: Resources reach the model ONLY as Gateway-registered synthetic tools; every
  call goes through the existing adapter SPI + Gateway pipeline. ✅
- **VI. Event Bus / content**: No event-schema/SCHEMA_VERSION/content change — resource contents are
  the existing `TextBlock`/`ImageBlock` tool-result types (ADR 0007). ✅
- **VII. Public-safe**: The host token is never echoed in output/errors/logs. ✅
- **IX. Reference-not-clone**: Uses the SDK's own resource APIs. ✅
- **X. Testable Evolution**: Additive; default-unused byte-identical; reversible; offline-tested. ✅

**Result**: PASS — additive, a small maintainer-pre-approved ADR (0007); no breaking 012/001 contract
change; no content/event change. (If the resource surface had needed a new content type, that would
be a 2nd boundary → STOP; it does not.) Complexity Tracking n/a.

## Project Structure

### Documentation (this feature)

```text
specs/059-mcp-resources/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/mcp-resources.md
└── checklists/requirements.md
docs/adr/0007-mcp-resources.md   # the small boundary decision
```

### Source Code (repository root)

```text
src/loopplane/adapters/mcp/config.py    # MODIFIED: MCPServerConfig + optional auth_token (or headers)
src/loopplane/adapters/mcp/adapter.py   # MODIFIED: pass Authorization header to http/sse transports;
                                        #   probe + register {server}:list_resources / :read_resource
                                        #   synthetic tools (contained); dispatch them in invoke();
                                        #   translate ReadResourceResult/ListResourcesResult -> blocks
src/loopplane/adapters/mcp/schema.py    # (maybe) resource-tool input schema for read_resource {uri}
tests/<mcp resources tests>             # NEW: offline resources + token-header + isolation + no-echo
```

**Structure Decision**: A per-adapter resource dispatch (e.g. `self._resources: dict[qualified ->
(session, kind)]` or a marker on `self._tools`) distinct from the real-tool dispatch, so `invoke`
routes `:list_resources`/`:read_resource` to the session resource APIs and everything else to
`call_tool` (unchanged). Resource results reuse the existing `TextBlock`/`ImageBlock` translation.
The token is read from the config + passed as `headers={"Authorization": f"Bearer {token}"}` to the
http/sse transport branches (websocket: no SDK headers param — skip + a one-line note). Default-unused
(no resources + no token) → byte-identical. Confined to `loopplane.adapters.mcp`.

## Complexity Tracking

> Additive extension of the existing MCP adapter (resources as synthetic Gateway tools + a config
> token header). A small ADR (0007); no content/event change; default-unused byte-identical. The
> per-server isolation already exists. Not a Constitution violation.
