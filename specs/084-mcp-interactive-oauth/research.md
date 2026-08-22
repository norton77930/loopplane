# Phase 0 Research: MCP Interactive OAuth

All findings below were verified against this working tree on 2026-08-22. Nothing here is inferred
from documentation alone.

## R1 — The MCP SDK already implements the flow

`mcp` 1.27.2 is installed and `loopplane[mcp]` pins `mcp>=1`.

- `mcp/client/auth/__init__.py` exports `OAuthClientProvider`, `PKCEParameters`, `TokenStorage`,
  `OAuthFlowError`, `OAuthRegistrationError`, `OAuthTokenError`.
- `OAuthClientProvider` is an `httpx.Auth`. Its constructor takes `server_url`, `client_metadata`,
  `storage: TokenStorage`, `redirect_handler: Callable[[str], Awaitable[None]] | None`,
  `callback_handler: Callable[[], Awaitable[tuple[str, str | None]]] | None`, `timeout: float = 300.0`,
  and `client_metadata_url: str | None`.
- `TokenStorage` is a four-method Protocol: `get_tokens` / `set_tokens` / `get_client_info` /
  `set_client_info`.
- It performs PKCE, protected-resource-metadata discovery, RFC 8707 resource validation, dynamic
  client registration, token exchange, and refresh.

**Conclusion**: the unit composes this rather than implementing OAuth. The three injection points map
one-to-one onto the maintainer's three design questions — who opens the browser (`redirect_handler`),
who receives the callback (`callback_handler`), where material lives (`storage`).

**Alternative considered**: implement the flow directly against `httpx`. Rejected — it duplicates a
correct implementation, and Constitution VIII forbids replacing SDK functionality the project does not
own.

## R2 — Which transports can carry it

| Transport | Signature evidence | Interactive auth |
| --------- | ------------------ | ---------------- |
| `http` | `streamablehttp_client(url, headers, timeout, sse_read_timeout, terminate_on_close, httpx_client_factory, auth: httpx.Auth \| None)` | **Yes** |
| `sse` | `sse_client(url, headers, timeout, sse_read_timeout, httpx_client_factory, auth: httpx.Auth \| None, on_session_created)` | **Yes** |
| `websocket` | `websocket_client(url)` — no `headers`, no `auth` | **No** — the ADR 0007 D3 limitation stands |
| `stdio` | local subprocess | **No** — no authorization endpoint exists |

`adapter.py:130-159` already branches per transport and already passes `headers=` conditionally for
`http` and `sse`. Adding `auth=` is a change in the same shape at the same two branch points.

## R3 — No new dependency

`mcp` 1.27.2 `Requires-Dist` includes `httpx<1.0.0,>=0.27.1` and `pyjwt[crypto]>=2.10.1`. The
`loopplane[mcp]` extra therefore already carries everything the flow needs. PKCE inputs, `state`
generation, and constant-time comparison are stdlib (`secrets`, `hashlib`, `base64`, `hmac`).

`pyproject.toml` also has a `net` extra (`httpx`) and an `oauth` extra
(`pyjwt[crypto]`, `httpx`) — the latter belongs to unit 056, which *verifies* tokens. **084 must not
reuse or rename the `oauth` extra**: the two features point in opposite directions and coupling them
would make `loopplane[oauth]` mean two unrelated things.

**Conclusion**: FR-018 is expected to hold. Any deviation is a GATE-§E stop.

## R4 — 056 is a style reference, not a mechanism reference

`src/loopplane/webapi/auth_jwt.py` (232 lines) validates a bearer JWT against a JWKS for the web/API
host — LoopPlane as a *resource server*. 084 is LoopPlane as an OAuth *client*. What transfers is the
style, and it transfers well:

- heavy dependencies import-guarded so importing the package does not require the extra;
- host-supplied configuration, with the project shipping no identity provider and no key material;
- every failure path denies, returning a fixed response that never echoes the credential.

What does not transfer is any code.

## R5 — The managed-capability surface cannot express authentication today

`host/_capability_mcp.py:326-333` constructs `MCPServerConfig(name=mcp_id, transport=transport,
url=endpoint)` — no `auth_token`, no headers. So the ADR 0007 static token is reachable only by an
embedder constructing the config directly in Python; no UI on any surface can reach an authenticated
MCP server at all.

Consequences for this unit:

- FR-020's surface change is not incidental scope creep; it is the only way a UI-reachable
  authenticated server can exist.
- `tests/contract/fixtures/capability_surface.json` pins the signatures of `upsert_mcp`,
  `reconnect_mcp`, `upsert_managed_mcp`, `reconnect_managed_mcp` and their siblings. It must be
  regenerated deliberately and reviewed as a contract change.
- The record persisted by `CapabilitySettingsStore` lives inside the LoopPlane profile root, which is
  inside the backup whitelist. It must therefore carry **status only** (ADR 0019 D8).

## R6 — The Desktop credential precedent, and where it stops working

`apps/desktop/electron/provider-credentials.ts` (238 lines) is the ADR 0016 implementation:
`safeStorage` encryption behind a narrow `CredentialVault` interface, a `CredentialFileIo` seam that
keeps the module unit-testable without Electron, a versioned blob under `app.getPath("userData")`,
and a `PublicProviderView` projection that is the only thing allowed to cross to the renderer.

Directly reusable: the vault/IO seam shape, the placement outside the profile root, the refusal to
store anything when `isEncryptionAvailable()` is false, and the public-projection discipline.

**Where it stops**: ADR 0016 D4 delivers the credential as spawn environment specifically to avoid a
new sidecar method. That works for one static credential known at launch. OAuth material is acquired
mid-session and rotates on refresh, so a launch-time channel cannot carry it. ADR 0019 D6 records the
narrowing and its reasoning.

## R7 — The Desktop method surface, and everything a new method touches

`mcp.list` / `mcp.get` / `mcp.upsert` / `mcp.reconnect` / `mcp.delete` exist today. Adding a method
touches six registries plus their pins — the same list unit 083 worked through:

1. `apps/desktop/sidecar/methods/capability.py` — handler plus its dispatch table
2. `apps/desktop/sidecar/bridge.py:442-446` — `_DESKTOP_METHOD_NAMES`
3. `apps/desktop/electron/sidecar-rpc.ts`
4. `apps/desktop/electron/ipc-channels.ts` + `ipc-handlers.ts`
5. `apps/desktop/src/services/capability-services.ts`
6. `packages/cowork-presentation/src/components/settings/McpSettings.tsx` + `i18n`

Pinned by `tests/contract/test_desktop_public_safety_routing.py`,
`tests/integration/test_desktop_sidecar.py`, `apps/desktop/electron/__tests__/helpers.ts`, and
`apps/desktop/src/__tests__/sidecar-rpc.test.ts`.

## R8 — Where the reverse direction already exists

`apps/desktop/sidecar/interaction.py` already carries an `EventEmitter` — `Callable[[dict], Awaitable
| None]` — pushing events from sidecar to main. So the sidecar→main direction exists as
**notifications**, and main→sidecar exists as **requests**. "Please open this URL" fits the existing
notification direction; delivering the authorization result and loading stored material fit the
existing request direction. No new transport direction is required, only new messages within the two
that exist.

## R9 — Test strategy: how to prove a negative

Three of this unit's most important requirements are negatives — nothing binds a socket, nothing
writes a credential to disk, nothing echoes a credential. Assertions must be constructive, not
incidental:

- **No socket**: an AST scan over `src/loopplane` for socket-binding and browser/process-launch
  constructs, in the shape of the existing boundary guards in `tests/contract/`. A behavioural test
  alone would pass by accident.
- **No disk write**: run the full offline flow with a temporary working directory and assert the set
  of files the runtime created is empty, plus an AST/import guard on the OAuth module.
- **No echo**: collect every event, tool result, error, log record, capability record, and checkpoint
  produced by a full flow, and assert a sentinel credential value appears in none of them. The
  sentinel must be a token-*shaped* literal, which means the fixture carrying it **must be
  git-tracked** before `tests/contract/test_public_safety.py` counts as evidence — the false green
  that units 051 and 082 hit.

Every negative check needs a **negative self-check**: deliberately break the property once and
confirm the guard goes red, before trusting it. This repository has been bitten by AST guards that
passed because they matched nothing.
