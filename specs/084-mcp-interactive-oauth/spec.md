# Feature Specification: MCP Interactive OAuth

**Feature Branch**: `084-mcp-interactive-oauth`

**Created**: 2026-08-22

**Status**: Draft — **R2 (credentials / OAuth)**. The three scope decisions are **answered**
(see [Clarifications](#clarifications)). **ADR 0019 MUST be authored at plan and approved by the
maintainer before any implementation begins.**

**Depends on**: 057-mcp-transports (Verified), 059-mcp-resources (Verified). Reference only (opposite
direction, no dependency): 056 OAuth/JWT *verification* for the web/API host.

**Input**: User description: "Close the last segment of gap **G12**: the MCP OAuth 2.1
authorization-code flow. Unit 059 shipped host-injected bearer tokens and recorded on the board that
the *interactive browser flow* was deferred; 084 takes over that explicitly-deferred item. Hosted MCP
servers that authorize over OAuth are, today, entirely unreachable from LoopPlane. Token storage and
refresh are design content, not implementation detail: where material lives, who can read it, what
happens after a process restart, and how principals are isolated must be settled in the spec."

---

## ⚠️ Boundary note (read first)

**This is an R2 unit.** It introduces a credential-acquisition path where none exists. The gates are
non-negotiable:

- **ADR 0019 at plan, approved before implementation** — not written retroactively.
- **`tests/contract/test_public_safety.py`** rejects credential-shaped strings in tracked files. Note
  the known failure mode recorded for units 051/082: that scan only covers **tracked** files, so an
  untracked fixture can produce a false green. Any test fixture carrying a token-shaped literal must
  be git-tracked before the scan is trusted.
- **Final review requires `code-reviewer` and `architecture-reviewer`.** Both, not one: the answer
  to Q2 extends the managed-MCP capability surface, which is an exposed interface.

**The seam this grows from** (395 lines total in `src/loopplane/adapters/mcp/`):

| Location | Today |
| -------- | ----- |
| `config.py:22` | `auth_token: str \| None` — the 059 host-supplied static bearer |
| `adapter.py:43` | `_auth_headers(config)` — builds the `Authorization` header |
| `adapter.py:135,145` | the header is applied on the `http` and `sse` transports only |
| `adapter.py:156` | `websocket_client` accepts no headers → auth not applied there (ADR 0007 D3) |

**Two facts established during specification** (they bound the design and are load-bearing for the
gate answers below):

1. **The MCP SDK already carries the flow.** `mcp>=1` (1.27.2 installed) ships `mcp.client.auth` with
   `OAuthClientProvider`, `PKCEParameters`, and a `TokenStorage` protocol; `streamablehttp_client`
   and `sse_client` each accept an `auth` handler. The SDK's own shape is
   `redirect_handler(url) -> None` / `callback_handler() -> (code, state)` / `storage: TokenStorage`
   — which maps one-to-one onto "who opens the browser", "who receives the callback", and "where do
   tokens live". The unit therefore composes an existing SDK capability rather than implementing
   OAuth.
2. **No new dependency is required.** `mcp` already requires `httpx` and `pyjwt[crypto]`
   transitively, so `loopplane[mcp]` covers the flow. PKCE, state, and any local listener are
   stdlib-reachable. **If implementation discovers a genuinely new dependency or extra is needed,
   that is a GATE-§E stop** (see FR-018).

**What this unit must never do**: open a browser, spawn a process, bind a network listener, ship an
identity provider, persist a credential inside the runtime by default, or let a credential reach the
model. Every one of those is a host responsibility or a non-goal.

---

## Why this exists

LoopPlane can connect to an MCP server that accepts a bearer token the embedder already holds. It
cannot connect to one that requires a person to authorize it — which is how essentially every hosted
MCP server works. The 059 path assumes the embedder has already obtained a credential by some means
outside LoopPlane; for an OAuth-protected server, no such means exists short of the user
hand-extracting a token from another tool.

The board records this precisely on the 059 row: *"host-injected-token OAuth (interactive browser
flow deferred)"*. This unit takes over that deferral, and only that.

The distinction from unit 056 matters and is easy to get backwards. **056 verifies a token somebody
else issued** — it is the web/API host acting as a resource server. **084 obtains a token on the
user's behalf** — LoopPlane acting as an OAuth *client*. They share vocabulary and share nothing
else; 056 is a reference for the import-guarded, fail-closed, host-supplied-configuration style, not
for the mechanism.

---

## Clarifications

### Session 2026-08-22

- **Q1 — Is the callback strictly host-owned, or does this unit also ship an opt-in loopback
  listener?** → **A: strictly host-owned.** Nothing in `src/loopplane` binds a socket. Desktop's
  Electron main process already is a host and can run a loopback listener itself, so the one-click
  experience is delivered without the runtime ever listening. The CLI's story this unit is
  "open this URL, then paste the redirect back"; a CLI convenience listener is a follow-on unit if
  wanted.
- **Q2 — Does this reach the managed-MCP capability surface, or embedders only?** → **B: runtime +
  Desktop.** Web is unchanged, preserving ADR 0016's recorded divergence (Desktop collects
  credentials; Web does not). Reaching Desktop is what makes the capability usable by the person
  who actually pays for the tokens.
- **Q3 — Does a reference durable token store ship, and who owns it?** → **B: the runtime defines
  the interface and ships only an in-memory default; Desktop persists through the ADR 0016
  keystore path.** `src/loopplane` writes no credential to disk under any configuration.

**Consequences of B + B**: this unit changes an exposed interface (the managed-MCP capability
surface must be able to carry an authorization mode, which today it cannot — it passes only
`name`/`transport`/`url`). Per FR-019 that pulls `architecture-reviewer` into the final review
alongside `code-reviewer`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-time authorization of a protected MCP server (Priority: P1)

A person configures a hosted MCP server that authorizes over OAuth. The runtime does not have a
credential and cannot invent one. It produces an authorization URL and hands it to the surface the
person is actually using; the surface shows or opens it. The person approves in their browser; the
surface returns the result to the runtime; the server's tools appear in the tool set.

**Why this priority**: This is the entire gap. Without it, an OAuth-protected server is unreachable.

**Independent Test** (offline, no browser, no network): a stubbed authorization endpoint plus a test
host handler that returns a canned authorization result. Assert the runtime never launched anything,
that the authorization URL was handed to the host handler, and that the server's tools became
available afterwards.

**Acceptance Scenarios**:

1. **Given** a server configured for interactive authorization and a host that supplies an
   authorization handler, **When** the adapter connects, **Then** the runtime produces an
   authorization URL, passes it to the host, waits for the host's result, and — on success —
   registers the server's tools exactly as an unauthenticated server's tools are registered today.
2. **Given** the same setup, **When** the flow completes, **Then** no browser was opened by the
   runtime, no process was spawned by the runtime, and no socket was bound by the runtime.
3. **Given** the host returns an authorization result whose `state` does not match the value the
   runtime issued, **When** the runtime validates it, **Then** the connection fails, the server is
   unavailable, and no automatic retry occurs.

---

### User Story 2 - A previously authorized server reconnects with no person present (Priority: P1)

A long-running or scheduled process restarts, or a token simply expires mid-run. Where the host
supplied a durable store, the server reconnects on its own. Renewal never asks for a browser.

**Why this priority**: Without this, interactive OAuth is unusable for anything unattended — every
restart and every token expiry would stall the run. It is also the single requirement that makes the
headless story coherent rather than a contradiction.

**Independent Test**: seed a token store with an expired access token plus a valid refresh token,
connect, and assert the server becomes available while the host's authorization handler is never
invoked.

**Acceptance Scenarios**:

1. **Given** stored material containing a valid refresh token, **When** the access token is expired
   or expires mid-session, **Then** the runtime renews it without invoking the host's authorization
   handler and the session continues.
2. **Given** no host-supplied durable store, **When** the process restarts, **Then** the server
   requires authorization again — and the spec's promise about restart behaviour is what the host
   configured, never a silent fallback to something weaker.
3. **Given** a refresh that fails because the grant was revoked or expired, **When** renewal is
   attempted, **Then** the server disconnects, is reported as requiring re-authorization, and no
   unauthenticated or static-token connection is attempted in its place.

---

### User Story 3 - Headless and CI environments fail closed (Priority: P1)

A test run, a CI job, or a container has no browser and no person. A server that needs interactive
authorization must not connect, must not degrade, and must not take anything else down with it.

**Why this priority**: This is the security boundary. A "helpful" fallback here — trying the
connection unauthenticated, or reaching for the 059 static token — would turn a missing credential
into a silent misconfiguration.

**Independent Test**: configure an interactive server with no host handler alongside a working
ordinary server; assert the interactive one is reported unavailable with a public-safe reason and the
ordinary one's tools are unaffected.

**Acceptance Scenarios**:

1. **Given** a server declaring interactive authorization and **no** host authorization handler,
   **When** the adapter connects, **Then** that server does not connect, no connection attempt is
   made without a credential, and its failure is reported as a public-safe problem string.
2. **Given** that same configuration alongside other healthy servers, **When** the adapter connects,
   **Then** the healthy servers connect normally and their tools are available — per-server isolation
   is preserved exactly as in 057/059.
3. **Given** a server configured with **both** a 059 static token and interactive authorization,
   **When** configuration is resolved, **Then** the entry is rejected as invalid and **only that
   entry** is disabled, following the existing "a malformed entry disables only itself" behaviour.

---

### User Story 4 - Credentials stay invisible and stay separated (Priority: P1)

Nothing the runtime emits, stores, or shows ever contains authorization material, and one principal's
material is never reachable by another.

**Why this priority**: This repository is public and has a contract test that blocks credential-shaped
strings in tracked files. Beyond that, the runtime already carries a per-principal model (061/063) and
a durable event/checkpoint/archive surface — every one of those is a place a token could leak into
permanently.

**Independent Test**: run a full authorization + tool call against stubs, then assert that the
recorded events, tool descriptors, tool results, gateway errors, capability status records, and
checkpoint contents contain no part of any token, code, client secret, or PKCE verifier.

**Acceptance Scenarios**:

1. **Given** a completed authorization, **When** any event, tool result, error, log line, capability
   status record, checkpoint, or exported archive is inspected, **Then** it contains no access token,
   refresh token, authorization code, client secret, or PKCE verifier — failures carry a fixed
   public-safe message instead.
2. **Given** two principals each with their own authorized instance of the same server, **When**
   either connects, **Then** neither can read or reuse the other's stored material.
3. **Given** the model is running, **When** it inspects the available tools, **Then** authorization is
   not among them: it cannot start, observe, redirect, or influence a flow, and no credential is ever
   a tool argument or a tool result.

---

### User Story 5 - Sign-out (Priority: P2)

A person disconnects a server they previously authorized. The stored material for that server is
discarded, and reconnecting requires authorizing again.

**Why this priority**: Acquiring a credential without a way to discard it is an incomplete credential
lifecycle. It is P2 only because the acquisition path has to exist first.

**Independent Test**: authorize against stubs, discard, reconnect; assert the host's authorization
handler is invoked again.

**Acceptance Scenarios**:

1. **Given** stored material for a (principal, server), **When** the host requests that it be
   discarded, **Then** it is removed and the next connection requires authorization again.
2. **Given** a discard request for material that does not exist, **When** it runs, **Then** it
   succeeds without error and without revealing whether anything was stored.

---

### User Story 6 - The Desktop operator connects a protected server from Settings (Priority: P1)

The person running the Desktop app adds an OAuth-protected MCP server in the MCP settings panel,
clicks connect, approves in the browser that opens, and the server's tools become available. Closing
and reopening the app does not ask them to approve again.

**Why this priority**: This is the delivery vehicle for the capability. The Desktop operator is the
person who owns the machine, supplies the key, and pays for every token — and per ADR 0016 is the
one surface that already collects credentials. Without this story the capability exists but nobody
without a Python editor can reach it.

**Independent Test**: with the runtime stubbed, drive the settings panel through adding an
interactive server, assert the browser-open request and the callback delivery both cross the
Desktop host boundary (never the runtime), and assert a restart reuses stored material.

**Acceptance Scenarios**:

1. **Given** the Desktop MCP settings panel, **When** the operator adds a server with interactive
   authorization and connects, **Then** the Desktop host opens the browser and receives the
   redirect, and the runtime does neither.
2. **Given** a successful authorization, **When** the app is closed and reopened, **Then** the
   server reconnects without a new approval, using material the Desktop host persisted through the
   ADR 0016 keystore path.
3. **Given** the operator disconnects the server, **When** they reconnect it, **Then** approval is
   required again and no stale material remains.
4. **Given** any Desktop state — panel, status list, logs, diagnostics, or a profile backup archive
   — **When** it is inspected, **Then** it contains no credential material.

---

### Edge Cases

- **The person never finishes.** Authorization is bounded by a timeout; on expiry the server is
  unconnected, the pending state is discarded, and nothing is retried automatically.
- **The person denies the request.** Treated as a definite failure, not a transient one: no retry
  loop, a public-safe reason, and the rest of the tool set unaffected.
- **The callback arrives twice, or late.** An authorization result is consumed at most once; a
  replayed or stale result is rejected on `state`.
- **The server's authorization metadata is unreachable or malformed.** Contained to that server, like
  any other connect failure.
- **A `websocket` server declares interactive authorization.** Invalid configuration — the transport
  cannot carry it (ADR 0007 D3). Rejected at configuration, that entry alone disabled.
- **A `stdio` server declares interactive authorization.** Invalid configuration — a local subprocess
  has no authorization endpoint.
- **Two servers share an identity provider.** Material is still stored per (principal, server); no
  cross-server reuse is inferred.
- **The token store is unavailable or corrupt.** Fail closed: the server does not connect; the run
  proceeds without it; no plaintext fallback location is invented.
- **A token expires between the tool list and a tool call.** Renewal is attempted transparently; if it
  fails, the call returns a normalized gateway error and the server is marked as needing
  re-authorization.

---

## Requirements *(mandatory)*

### Functional Requirements

**Authorization is initiated by the runtime and performed by the host**

- **FR-001**: The runtime MUST NOT open a browser, spawn a process, or bind a network listener as
  part of authorization. It MUST hand the authorization URL to a host-supplied handler and await the
  host's result.
- **FR-002**: A server configuration MUST be able to declare that it authorizes interactively,
  distinctly from the 059 static token. Declaring both on one server is invalid; that entry alone is
  disabled and reported, following the existing per-entry containment.
- **FR-003**: The flow MUST be the authorization-code flow with PKCE. The `state` returned by the
  host MUST be verified against the value the runtime issued; a missing or mismatched `state` MUST
  fail the connection with no automatic retry.
- **FR-004**: Interactive authorization MUST apply to the `http` and `sse` transports only. `stdio`
  needs none and `websocket` cannot carry it (ADR 0007 D3); declaring it on either is invalid
  configuration.
- **FR-005**: Receiving the redirect MUST be the host's responsibility. The runtime MUST NOT assume a
  loopback redirect URI, a bound port, an available browser, or any particular surface, and **no
  component under `src/loopplane` may bind a listening socket** for this purpose.
- **FR-006**: Authorization MUST be bounded by a timeout. On expiry the pending state is discarded
  and the server is left unconnected with a public-safe reason.

**Token storage and lifecycle**

- **FR-007**: The runtime MUST define a token-store interface and MUST ship only an in-memory
  default. **No code under `src/loopplane` may write credential material to disk under any
  configuration.** Absent a host-supplied store, material lives only for the process lifetime and a
  restart requires re-authorization.
- **FR-008**: Renewal MUST NOT require a person. Given valid refresh material, the runtime MUST renew
  without invoking the host's authorization handler.
- **FR-009**: A failed renewal MUST fail closed: the server disconnects and is reported as requiring
  re-authorization. The runtime MUST NOT retry unauthenticated and MUST NOT fall back to a static
  token.
- **FR-010**: Stored material MUST be scoped to a (principal, server) pair. No principal may read
  another principal's material, and no server may reuse another server's.
- **FR-011**: The runtime MUST support discarding all stored material for a (principal, server) so a
  host can implement sign-out. Discarding material that does not exist MUST succeed silently.

**Non-leakage**

- **FR-012**: No access token, refresh token, authorization code, client secret, or PKCE verifier may
  appear in any runtime event, tool descriptor, tool input or output, gateway error, log line,
  capability status record, checkpoint, or exported archive. Failures MUST carry a fixed public-safe
  message.
- **FR-013**: The model MUST NOT be able to start, observe, redirect, or influence authorization.
  Authorization MUST NOT be exposed as a tool, and no credential may be a tool argument or a tool
  result.

**Containment and additivity**

- **FR-014**: An authorization failure MUST be contained to its own server. Other servers and the
  rest of the tool set stay available, preserving the 057/059 per-server isolation.
- **FR-015**: With no host handler configured, a server declaring interactive authorization MUST NOT
  connect and MUST NOT attempt an unauthenticated connection.
- **FR-016**: The feature MUST be default-unused and byte-identical when unused: a configuration
  containing no interactive server MUST behave exactly as it does today, including the 059 static
  token path.

**Desktop reach (Q2 = B, Q3 = B)**

- **FR-020**: The managed-MCP capability surface MUST be able to carry an authorization mode. Today
  it passes only name, transport, and URL, so it can express neither interactive authorization nor
  the 059 static token; that gap is closed for the authorization mode. The surface MUST NOT carry
  credential material itself — only which mode a server uses and whether it is currently authorized.
- **FR-021**: The Desktop host MUST own the browser, the redirect, and durable storage of
  authorization material, persisting it through the ADR 0016 keystore path — outside the LoopPlane
  profile root, so a profile backup cannot contain it by construction.
- **FR-022**: The Desktop operator MUST be able to see, from the MCP settings surface, whether a
  server is authorized, needs authorization, or failed — without any credential value appearing in
  that surface, in Desktop logs or diagnostics, or in a profile archive.
- **FR-023**: The Web surface MUST be unchanged. ADR 0016's recorded divergence stands: Web does not
  collect credentials, and this unit does not revisit that.

**Gates**

- **FR-017**: The plan MUST author **ADR 0019** covering, at minimum: the host-owned browser and
  callback boundary, the token-store ownership and default, the per-(principal, server) isolation
  rule, the fail-closed stance, and the Desktop process boundary for material in transit.
  Implementation MUST NOT begin before the maintainer approves it.
- **FR-018**: The unit MUST introduce no new runtime dependency and no new extra. If implementation
  finds one unavoidable, it MUST STOP for maintainer approval (GATE-§E) rather than adding it.
- **FR-019**: Final review MUST include **both** `code-reviewer` and `architecture-reviewer` — Q2 = B
  changes an exposed interface (FR-020), which makes the architectural review mandatory rather than
  conditional.

### Key Entities

- **Interactive server configuration**: a server declaring that it authorizes interactively, replacing
  rather than accompanying the 059 static token. Carries no credential itself.
- **Authorization request**: transient — an authorization URL plus the `state` the runtime issued.
  Never persisted, never emitted.
- **Authorization result**: transient — the code and `state` the host returns. Consumed at most once.
- **Stored authorization material**: per (principal, server) — access token, refresh material, expiry,
  and any registered client identity. The one thing in this unit that is durable, and the reason the
  unit is R2.
- **Token store**: the host-supplied interface through which all durable material passes. The runtime
  defines the shape and owns no default location.
- **Host authorization handler**: the host-supplied pair of responsibilities — present the
  authorization URL, and return the authorization result. The only path by which a person enters the
  flow.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can connect an OAuth-protected MCP server and use its tools without obtaining
  a token by hand from another application — the capability that is impossible today.
- **SC-002**: In every automated test, the number of browsers opened, processes spawned, and sockets
  bound **by the runtime** during authorization is zero.
- **SC-003**: A server authorized once continues to work across token expiry, and across a process
  restart when the host supplied a durable store, with zero further human interactions.
- **SC-004**: In an environment with no authorization handler, an interactive server connects zero
  times, attempts zero unauthenticated connections, and reduces the availability of other configured
  servers by zero tools.
- **SC-005**: An automated scan of every event, tool result, error, log line, status record,
  checkpoint, and archive produced by a full authorization run finds zero occurrences of any
  credential value.
- **SC-006**: A principal can read zero bytes of another principal's stored material.
- **SC-007**: A configuration containing no interactive server produces behaviour identical to the
  current release, verified by the existing suites passing unchanged.
- **SC-008**: The number of new runtime dependencies and new extras is zero, or the unit is stopped
  for approval before any are added.
- **SC-009**: After sign-out, reconnecting requires exactly one new authorization.
- **SC-010**: A Desktop operator can connect an OAuth-protected MCP server using only the app's
  settings surface — zero configuration files edited, zero environment variables set, zero Python
  written.
- **SC-011**: The number of credential values found in the Desktop settings surface, Desktop logs and
  diagnostics, the LoopPlane profile directory, and a profile backup archive is zero.
- **SC-012**: The number of bytes written to disk by `src/loopplane` containing authorization
  material is zero, under every configuration.

---

## Assumptions

- The MCP SDK's `mcp.client.auth` provider is the mechanism; this unit composes it rather than
  implementing OAuth. Its `redirect_handler` / `callback_handler` / `TokenStorage` shape is what makes
  the host-owned boundary expressible without inventing a new one.
- `loopplane[mcp]` already brings everything the flow needs (`httpx`, `pyjwt[crypto]` arrive
  transitively with `mcp>=1`), so FR-018 is expected to hold rather than merely hoped for.
- The 059 static-token path stays exactly as it is. This unit adds an alternative, not a replacement,
  and does not revisit ADR 0007 D3's websocket limitation.
- Authorization is per (principal, server). The runtime's existing principal model (061/063) is the
  isolation unit; no new identity concept is introduced.
- Tests run offline against stubbed authorization and token endpoints. No test may require a browser,
  a live identity provider, or network access.
- The repository's four gates plus the public-safety contract test are the verification baseline;
  current values are pytest 2236 passed / 33 skipped and 482 passed / 13 skipped for
  `tests/contract`.

---

## Non-Goals

- Shipping an identity provider, an authorization server, or any credential-issuing component.
- A loopback callback listener inside `src/loopplane`, and any CLI convenience listener (Q1 = A). The
  CLI's story this unit is open-the-URL-and-paste-the-redirect; a one-command CLI flow is a follow-on.
- Any change to the Web surface or to ADR 0016's Web stance (Q2 = B).
- A durable token store inside `src/loopplane` (Q3 = B). Durability is the host's, and on Desktop it
  is the existing keystore path.
- Changing the 059 static-token path, or extending auth to the `websocket` transport.
- Any content-model or event-schema change. Nothing here touches what the model sees.
- MCP resource subscriptions/notifications and MCP prompts — still deferred from ADR 0007 D5.
- Device-code or client-credentials grants. Only the interactive authorization-code flow with PKCE is
  in scope; other grant types are follow-on work if wanted.
- Provider-specific integrations. Nothing in this unit names a particular hosted MCP server.
- Storing or proxying credentials for anything other than MCP servers.
