# Implementation Plan: MCP Interactive OAuth

**Branch**: `084-mcp-interactive-oauth` (main-only autopilot convention) | **Date**: 2026-08-22 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/084-mcp-interactive-oauth/spec.md`

**Boundary**: settled by **[ADR 0019](../../docs/adr/0019-mcp-interactive-oauth.md)** — authored at
this plan step and **`Proposed`**. This is an **R2** unit (credentials / OAuth): **implementation
MUST NOT begin until the maintainer accepts ADR 0019** (spec FR-017). Clarifications are closed:
Q1 = A (callback strictly host-owned), Q2 = B (runtime + Desktop, Web untouched), Q3 = B (interface
plus in-memory default; Desktop persists through the ADR 0016 keystore path).

## Summary

Give the MCP adapter an interactive authorization path and make it reachable from the Desktop app.

The runtime composes the MCP SDK's `OAuthClientProvider` (PKCE, discovery, dynamic client
registration, token exchange, refresh) and injects two host-supplied Protocols into
`MCPToolAdapter`: an **authorization handler** (present a URL; return the result) and a **token
store** (get / set / discard, keyed by principal and server). `MCPServerConfig` gains an
authorization *mode* mutually exclusive with the ADR 0007 `auth_token`, valid on `http` and `sse`
only. Nothing under `src/loopplane` binds a socket, opens a browser, or writes credential material to
disk; the shipped store is in-memory. With no handler configured the server fails closed and alone —
no unauthenticated retry, no fallback to the static token — while renewal of already-authorized
material runs unattended.

The managed-capability surface, which today can express neither authorization mode nor token, gains a
mode plus a status (`authorized` / `needs_authorization` / `failed`) and stores no material. Desktop
implements both Protocols in the sidecar by delegating to Electron main, which owns the browser, the
loopback listener, and `safeStorage` persistence under `app.getPath("userData")` — outside the
profile root, so a backup cannot contain it by construction. Web is unchanged.

Default-unused is byte-identical; no new dependency (`mcp>=1` already pulls `httpx` and
`pyjwt[crypto]`).

## Technical Context

**Language/Version**: Python 3.12+ (runtime, sidecar); TypeScript (Electron main, renderer).

**Primary Dependencies**: none new. `mcp.client.auth.OAuthClientProvider` / `TokenStorage` and the
`auth: httpx.Auth | None` parameter on `streamablehttp_client` / `sse_client` are already present
(verified against `mcp` 1.27.2). Electron `safeStorage` is already in use for ADR 0016.

**Storage**: none in the runtime — in-memory only, by decision (ADR 0019 D3). On Desktop, an
encrypted blob under `app.getPath("userData")`, alongside and separate from the ADR 0016 provider
credential. The profile-resident capability record holds status only (ADR 0019 D8).

**Testing**: pytest, fully offline. The MCP `ClientSession`, the transports, and the authorization /
token endpoints are stubbed; a fake authorization handler returns canned results; a fake token store
records calls. No test may open a browser, bind a port, or reach the network. Desktop: Vitest for
Electron main and renderer; the existing sidecar contract and public-safety routing tests extend to
the new methods.

**Target Platform**: cross-platform library; Desktop on Windows / macOS / Linux.

**Constraints**: additive; default-unused byte-identical; authorization never reaches the model and
is never a tool (Constitution V/VI untouched); credentials never in events, tool output, errors,
logs, capability records, checkpoints, or archives (VII); per-`(principal, server)` isolation; no
new dependency or extra (GATE-§E if that changes); no socket bound and no credential written to disk
by `src/loopplane`; Web unchanged.

**Scale/Scope**: runtime ~3 files touched plus 2 new modules; host capability surface 2 files;
Desktop sidecar 2 files plus method registries; Electron main 2 new modules; renderer settings panel.

## Constitution Check

*GATE: evaluated before Phase 0 research and re-checked after Phase 1 design.*

- **I. Spec-First**: traces to `spec.md` FR-001…FR-023 and ADR 0019. ✅
- **IV. Runtime Boundary Clarity**: the OAuth mechanism is confined to `loopplane.adapters.mcp`; the
  human-facing and durable halves are host responsibilities declared as Protocols. The change does
  blur one existing boundary — ADR 0016 D4 kept credentials out of sidecar RPC parameters — and ADR
  0019 D6 **updates that boundary definition explicitly** rather than routing around it, which is
  what this principle requires. ✅
- **V. Tool Gateway Ownership**: authorization is not a tool, is not registered as one, and is not
  reachable by the model. Tools from an authorized server flow through the unchanged adapter SPI. ✅
- **VI. Runtime Event Bus Ownership**: no event-schema change, no `SCHEMA_VERSION` bump, no
  content-model change. Authorization state is never an event payload carrying material. ✅
- **VII. Public-Safe Documentation**: no credential in any committed file, and none in any runtime or
  Desktop output. Note the tracked-files-only limit of the public-safety contract test. ✅
- **VIII. No SDK Replacement**: the unit composes the MCP SDK's OAuth client rather than
  re-implementing OAuth 2.1. ✅
- **X. Testable Evolution**: additive, default-unused byte-identical, offline-testable, reversible by
  removing the two seams. ✅

**Result**: **PASS, conditional on the R2 gate.** The Constitution check itself has no violation, but
the unit is `Proposed`-blocked: implementation may not begin until ADR 0019 is accepted. Complexity
Tracking below records the one accepted boundary narrowing.

## Project Structure

### Documentation (this feature)

```text
specs/084-mcp-interactive-oauth/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md
├── contracts/mcp-interactive-oauth.md
├── checklists/requirements.md
└── tasks.md                      # /speckit-tasks output
docs/adr/0019-mcp-interactive-oauth.md   # the R2 boundary decision (Proposed)
```

### Source Code (repository root)

```text
src/loopplane/adapters/mcp/oauth.py       # NEW: the two host Protocols (authorization handler,
                                          #   token store), the in-memory default store, the SDK
                                          #   OAuthClientProvider composition, and the state check
src/loopplane/adapters/mcp/config.py      # MODIFIED: authorization mode on MCPServerConfig, mutually
                                          #   exclusive with auth_token; http/sse only
src/loopplane/adapters/mcp/adapter.py     # MODIFIED: accept the two seams as constructor params;
                                          #   pass auth= to the http/sse transports; fail closed and
                                          #   alone when no handler is configured
src/loopplane/adapters/mcp/__init__.py    # MODIFIED: export the Protocols and the default store

src/loopplane/host/capabilities.py        # MODIFIED: authorization mode + status on the managed
                                          #   MCP configuration record (status only, never material)
src/loopplane/host/_capability_mcp.py     # MODIFIED: carry the mode into MCPServerConfig; surface
                                          #   needs_authorization; wire host-supplied seams
src/loopplane/host/host.py                # MODIFIED: the managed-MCP methods carry the mode

apps/desktop/sidecar/methods/capability.py  # MODIFIED: mcpauth.* methods; status projection only
apps/desktop/sidecar/bridge.py              # MODIFIED: method-name registry
apps/desktop/electron/mcp-oauth-vault.ts    # NEW: safeStorage persistence, ADR 0016 placement
apps/desktop/electron/mcp-oauth-flow.ts     # NEW: browser open + loopback listener + state check
apps/desktop/electron/{ipc-channels,ipc-handlers,sidecar-rpc,main}.ts  # MODIFIED: wiring
apps/desktop/src/services/capability-services.ts                      # MODIFIED: renderer service
packages/cowork-presentation/src/components/settings/McpSettings.tsx  # MODIFIED: mode + status UI

tests/unit/test_mcp_oauth.py               # NEW: offline flow, fail-closed, no-echo, isolation
tests/integration/test_mcp_oauth_capability.py  # NEW: managed surface carries mode, not material
tests/contract/fixtures/capability_surface.json # REGENERATED: deliberately, per FR-020
```

**Structure Decision**: the OAuth composition lives in a **new `oauth.py` beside the adapter**, not
inside `adapter.py`. Three reasons: `adapter.py` is already the largest file in a 395-line package and
its connect path is the one place per-server isolation is enforced, so it should gain a call and not a
concern; the two Protocols are the runtime's *public* seam and deserve a module a host can import
without reaching into the adapter; and keeping the SDK's `OAuthClientProvider` construction in one
place makes the "nothing here binds a socket or writes a file" property reviewable by reading one
file. `adapter.py` changes only where it already branches per transport — it passes `auth=` alongside
the existing `headers=` for `http` and `sse`, and gains one fail-closed guard.

The two seams are **constructor parameters of `MCPToolAdapter`**, following the unit-053 precedent for
adapter-scoped injection rather than a `RuntimeConfig` knob (ADR 0019 D2). `RuntimeConfig` stays out
of the credential path entirely.

On Desktop, the sidecar implements both Protocols as thin delegates over the existing stdio JSON-RPC
pipe; the loopback listener, the browser, and `safeStorage` all live in Electron main. The renderer
never receives a value — only `authorized` / `needs_authorization` / `failed`, mirroring ADR 0016's
`PublicProviderView` discipline.

## Complexity Tracking

> The Constitution Check passes. One boundary narrowing is recorded deliberately rather than left
> implicit, per Principle IV.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ADR 0016 D4 said the Desktop credential reaches the sidecar as spawn environment, never as an RPC parameter. OAuth material crosses the stdio RPC pipe in both directions. | OAuth material is acquired mid-session and rotates on refresh, so a launch-time channel cannot carry it. The MCP adapter runs in the sidecar and needs the token to make the request. | Keeping the whole flow in Electron main and handing the sidecar only a short-lived bearer would avoid the pipe — but it re-implements OAuth 2.1 in TypeScript, duplicating what the Python SDK already does, and leaves the library and CLI with no capability at all. The gap this unit closes is a library gap. ADR 0019 D6 narrows the boundary explicitly and bounds the residual risk: same machine, same user, same application, never a network hop, never the renderer, never Web. |
