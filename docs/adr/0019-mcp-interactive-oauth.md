# ADR 0019: MCP interactive OAuth — who authorizes, who stores, who never touches a credential

- **Status**: **Accepted** (2026-08-22) — authored at the unit 084 plan step and accepted by the
  maintainer before implementation began, as spec 084 FR-017 requires for the R2 credential trigger.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. It **discharges ADR 0007 D5's deferral** of the
  interactive browser authorization-code flow, and **narrows ADR 0016 D4** for this one case (see D6).
- **Related**: **ADR 0007** (MCP resources + host-token transport auth; D3 host bearer, D5 deferral),
  **ADR 0016** (Desktop collects and stores a model-provider credential), **ADR 0015** (Desktop cowork
  process/protocol boundary), Constitution **IV** (a change blurring a boundary updates the boundary
  definition), **V** (the Tool Gateway is the only tool ingress), **VII** (public-safe committed
  files), **X** (default-preserving, testable, reversible). Nineteenth ADR.

## Context

`loopplane.adapters.mcp` can connect to an MCP server that accepts a bearer token the embedder
already holds (ADR 0007 D3): `MCPServerConfig.auth_token` becomes an `Authorization` header on the
`http` and `sse` transports. ADR 0007 D5 explicitly deferred the interactive
authorization-code-with-PKCE flow.

The consequence is that every hosted MCP server which authorizes a *person* — rather than accepting
a long-lived secret an operator can paste — is unreachable. There is no supported way to obtain such
a credential from inside LoopPlane, and for most such servers there is no supported way to obtain one
outside it either.

Three properties of the existing code shape the decision:

1. **The MCP SDK already implements the protocol.** `mcp.client.auth` (present in `mcp>=1`; 1.27.2 in
   this tree) provides `OAuthClientProvider` with PKCE, authorization-server discovery, dynamic
   client registration, and refresh. It is an `httpx.Auth`, and both `streamablehttp_client` and
   `sse_client` accept `auth: httpx.Auth | None`. Its three injection points —
   `redirect_handler(url)`, `callback_handler() -> (code, state)`, and `storage: TokenStorage` — are
   exactly the three questions this ADR must answer.
2. **The managed-capability surface cannot express authentication at all.**
   `host/_capability_mcp.py:326-333` constructs `MCPServerConfig(name=…, transport=…, url=…)`. It
   cannot carry even the ADR 0007 static token, so no UI-reachable path to an authenticated MCP server
   exists on any surface today.
3. **Desktop already has an accepted credential-storage decision.** ADR 0016 put the provider API key
   in Electron `safeStorage` under `app.getPath("userData")`, deliberately outside the LoopPlane
   profile root so the backup whitelist in `sidecar/archive.py` cannot sweep it into an archive.

The unit-084 clarification session settled the scope: the callback is strictly host-owned (Q1 = A),
the capability reaches the runtime **and Desktop** but not Web (Q2 = B), and durability is the host's
with Desktop reusing the ADR 0016 keystore path (Q3 = B).

## Decision

- **D1 — The runtime owns the OAuth *mechanism*; the host owns every human-facing and durable half.**
  The adapter composes the SDK's `OAuthClientProvider`: PKCE, discovery, client registration, token
  exchange, and refresh all happen inside `loopplane.adapters.mcp`. Presenting the authorization URL,
  receiving the redirect, and persisting anything are the host's, without exception.

  *Rejected alternative*: let each host implement OAuth and hand the runtime a finished bearer token
  (which would need only the ADR 0007 D3 path plumbed through). Rejected because it re-implements, in
  TypeScript, a protocol the Python SDK already implements correctly, and because it would close the
  gap for Desktop alone — an embedder or the CLI would still have nothing. The reachability gap this
  unit exists to close is a *library* gap.

- **D2 — Two host-supplied seams, injected as adapter constructor parameters.** An authorization
  handler (present a URL; return the authorization result) and a token store (get / set / discard,
  keyed by principal and server). Both are Protocols declared by the runtime and implemented by the
  host. They are constructor parameters of the adapter, following the unit-053 precedent for
  adapter-scoped injection, **not** `RuntimeConfig` knobs: they are host capabilities, not run policy,
  and `RuntimeConfig` must not become a place credentials pass through.

- **D3 — Two absolute prohibitions on `src/loopplane`.** No module under `src/loopplane` may
  (a) bind a listening socket, open a browser, or spawn a process for authorization, or
  (b) write authorization material to disk under any configuration. The shipped token store is
  in-memory and process-lifetime only. Both are stated as testable requirements (spec FR-001, FR-005,
  FR-007) and both are enforced by tests rather than by convention.

- **D4 — Authorization mode is configuration; a credential never is.** `MCPServerConfig` gains an
  authorization *mode* that is **mutually exclusive** with ADR 0007's `auth_token`. Declaring both is
  invalid and disables **that entry alone**, matching `merge_layers`'s existing "a malformed entry
  disables only itself" behaviour. Interactive authorization applies to `http` and `sse` only:
  `stdio` is a local subprocess with no authorization endpoint, and `websocket_client` accepts neither
  `headers` nor `auth` (the ADR 0007 D3 limitation stands, undisturbed).

- **D5 — The isolation unit is `(principal, server)`.** Every store operation is keyed by both. No
  principal may read another's material; no server inherits another's, even behind the same
  authorization server. This reuses the existing principal model (061/063) and introduces no new
  identity concept.

- **D6 — The Desktop process boundary: Electron main owns browser, redirect, and durability;
  material crosses the sidecar pipe.** Main opens the system browser, runs the loopback listener,
  and encrypts material through `safeStorage` into a blob under `app.getPath("userData")` — the same
  placement ADR 0016 D3 chose, so a profile backup cannot contain it by construction. The sidecar
  implements the runtime's two Protocols by delegating to main.

  This **narrows ADR 0016 D4**, which kept the provider key out of RPC parameters by passing it as
  spawn environment. That worked because one static credential is known at launch. OAuth material is
  acquired mid-session and rotates on refresh, so a launch-time channel cannot carry it. Material
  therefore crosses the existing stdio JSON-RPC pipe between two processes of the same application,
  on the same machine, under the same user. It never crosses a network boundary, never reaches the
  renderer, and never reaches the Web surface. The renderer receives only a status projection —
  `authorized` / `needs_authorization` / `failed` — never a value, mirroring ADR 0016's
  `PublicProviderView` discipline.

- **D7 — Fail closed, and only where a person is genuinely required.** With no authorization handler
  configured (headless, CI, a server deployment), a server declaring interactive authorization does
  not connect and **no unauthenticated attempt is made**; it never silently falls back to the ADR 0007
  static token. Failure is contained to that server, preserving 057/059 per-server isolation.
  Renewal is the deliberate exception: given valid refresh material the runtime renews **without**
  invoking the authorization handler, so unattended and scheduled work keeps running. A failed
  renewal fails closed and reports that re-authorization is needed.

- **D8 — The capability store records status, never material.** The managed-capability record gains
  an authorization *mode* and an authorization *status*. It stores no token, no refresh token, no
  client secret, and no PKCE verifier. This matters because that store lives inside the LoopPlane
  profile root and is therefore inside the backup whitelist — the exact place D6's placement decision
  is designed to keep material out of.

- **D9 — Default-unused is byte-identical, and nothing new is installed.** A configuration with no
  interactive server behaves exactly as the current release, including the ADR 0007 static-token path.
  No new dependency and no new extra: `mcp>=1` already requires `httpx` and `pyjwt[crypto]`
  transitively, so `loopplane[mcp]` covers the flow. If implementation finds a new dependency
  unavoidable, that is a **GATE-§E** stop, not a silent addition.

- **D10 — Web is unchanged.** ADR 0016's recorded divergence stands: Desktop collects credentials,
  Web does not. Nothing in `apps/web` or the web/API host changes, and this ADR does not reopen that
  question.

## Implementation note (added during unit 084 implementation; decisions unchanged)

D7 promises that renewal never needs a person. Implementation found that the SDK does
not, by itself, deliver that across a process restart, and the gap is invisible until you
look at which branch its auth flow takes.

`OAuthClientProvider._initialize()` restores `current_tokens` and `client_info` from
storage but **not** `token_expiry_time`. `is_token_valid()` reads that field, so a
restarted process treats arbitrarily old material as valid, sends it, and receives a 401.
The 401 branch does not consult `can_refresh_token()` — it runs the **full authorization
flow**, which calls the host's handler. In other words: with a durable store, a scheduled
job that restarts would prompt for a browser it does not have, precisely in the case the
refresh token exists to cover.

The fix keeps the boundary intact rather than widening it:

- `StoredAuthorizationMaterial` carries an **absolute** `expires_at`, recorded from the
  token's `expires_in` when the SDK stores it. An unknown expiry stays `None` — a guess
  would expire a working token.
- After constructing the provider, the adapter restores `context.token_expiry_time` from
  that value, so the SDK's own refresh branch becomes reachable across a restart.
- The restore is guarded by `hasattr`: if a future SDK drops the field, behaviour degrades
  to today's optimistic path rather than raising.

This touches one SDK dataclass field, which is why it is recorded here rather than left in
a commit message. It changes no decision above; it is what D7 costs in practice.

## Consequences

- **Closes the G12 tail** recorded on the 059 board row as "interactive browser flow deferred", and
  discharges ADR 0007 D5's first deferral. Resource subscriptions and MCP prompts remain deferred.
- **The library gains the capability, not just an app.** Any embedder that supplies the two Protocols
  gets OAuth-protected MCP servers; the CLI's story this unit is open-the-URL-and-paste-the-redirect,
  because D3 forbids the runtime from listening and no CLI convenience listener is in scope.
- **An exposed interface changes.** The managed-MCP capability surface gains an authorization mode, so
  `tests/contract/fixtures/capability_surface.json` must be regenerated deliberately, and the final
  review requires `architecture-reviewer` alongside `code-reviewer` (spec FR-019).
- **A new class of durable secret exists on Desktop.** It is bounded by D6's placement (outside the
  profile root, encrypted by the OS keystore) and by D8 (the profile-resident record holds status
  only). The residual risk is the material in transit over the local stdio pipe, accepted in D6 with
  its reasoning stated rather than left implicit.
- **Public-safety**: no credential may appear in any event, tool descriptor, tool input or output,
  gateway error, log line, capability record, checkpoint, or archive (Constitution VII; spec FR-012).
  Note that `tests/contract/test_public_safety.py` enumerates files through `git ls-files` and
  therefore sees **tracked files only** — a token-shaped fixture must be tracked before that scan is
  evidence of anything.
- **Reversible**: the feature is inert unless a host supplies both seams and a server declares the
  mode. Reverting is removing the seams; no data migration, no schema change, no `SCHEMA_VERSION`
  bump, and no change to what the model sees (Constitution VI is untouched — authorization is never a
  tool and never a content block).
