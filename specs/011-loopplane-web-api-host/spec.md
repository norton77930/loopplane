# Feature Specification: LoopPlane Web / API Host

**Feature Branch**: `011-loopplane-web-api-host`

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Expose LoopPlane through a web/API host on top of the completed
Phase-1 runtime foundation (001) and the Host Application Interface (002), composing ONLY the
public Host surface: a network API host with request/response endpoints, a live event-stream
channel, an authentication boundary, and session APIs, plus host-level integration tests. It is an
ADDITIVE host layer — it embeds the public host, drives no runtime internals, executes no tool
itself, and re-emits no live event bus; it consumes the normalized event stream as a host consumer
exactly as Constitution VI prescribes. Public-safe, metadata-only, offline-testable, English."

## User Scenarios & Testing *(mandatory)*

The web/API host turns the embedded Host Application Interface (unit 002) into something a remote or
local client can drive over a network API: start a run, watch its normalized events stream by,
conduct an interactive session (answering approvals and questions), inspect sessions and artifacts,
and do all of it behind an authentication boundary. Every story is a thin, public-safe seam over the
**public** host surface — it adds no runtime behavior of its own.

### User Story 1 - Start and observe a run over the API (Priority: P1)

A client sends a prompt to a run endpoint and receives the run's outcome — the terminal reason, the
number of turns taken, and a metadata-only history snapshot — without ever touching runtime
internals. This is the minimum viable product: the ability to drive a LoopPlane run across a network
boundary.

**Why this priority**: Driving a run over the API is the reason this layer exists. Everything else
(streaming, interactivity, inspection, auth) decorates this core capability; without it there is no
web/API host.

**Independent Test**: Using an in-process test client, POST a prompt to the run endpoint and assert
the response carries the expected terminal reason, turn count, and a public-safe history snapshot —
with no runtime internals invoked directly.

**Acceptance Scenarios**:

1. **Given** a configured web/API host embedding a LoopPlane host, **When** a client submits a prompt
   to the run endpoint, **Then** the host starts exactly one run through the public host surface and
   returns its public-safe outcome.
2. **Given** a run is already active on the embedded host, **When** a second concurrent run request
   arrives, **Then** the host returns an explicit, public-safe conflict response instead of
   corrupting state or hanging.
3. **Given** a request whose body is malformed or missing the prompt, **When** it reaches the run
   endpoint, **Then** the host returns an explicit, public-safe client-error response with no stack
   trace, path, or internal name leaked.

---

### User Story 2 - Stream run events to a connected client (Priority: P2)

A client subscribes to a live event-stream channel and receives the run's normalized events, in
their recorded order, serialized public-safe, as the run progresses.

**Why this priority**: Observability over the wire is what makes a remote run usable; a run you
cannot watch is opaque. It builds directly on US1 and is the second-most valuable capability.

**Independent Test**: Connect an in-process client to the event-stream channel, drive a run, and
assert the received events match the recorded normalized order and contain only public-safe fields.

**Acceptance Scenarios**:

1. **Given** a client subscribed to the event stream, **When** a run produces normalized events,
   **Then** the client receives them in the exact recorded order with no reordering by wall-clock.
2. **Given** an event carrying offloaded or sensitive runtime detail, **When** it is streamed,
   **Then** only the normalized event's public-safe fields are serialized — no secrets, internal
   references, or content beyond what the normalized event already exposes.
3. **Given** a stream client that is slow, fails, or disconnects mid-run, **When** the run continues,
   **Then** the run still terminates and the host records the consumer failure rather than crashing
   or hanging.

---

### User Story 3 - Conduct an interactive session over the API (Priority: P3)

A client opens an interactive session, submits input, answers a pending approval request and a
pending question, and can cancel — mapping the embedded session round-trip onto the network API.

**Why this priority**: Interactivity (approvals, questions, multi-turn submit) is the human-in-the-
loop capability that separates a real host from a fire-and-forget endpoint. It depends on US1/US2
being in place.

**Independent Test**: Open a session over the API, submit input that triggers an approval, answer the
approval, and assert the session reaches the expected outcome — all in-process.

**Acceptance Scenarios**:

1. **Given** an open session, **When** the client submits input, **Then** the host drives the
   embedded session and returns the resulting public-safe outcome.
2. **Given** a session parked on a pending approval or question, **When** the client answers it by
   request id, **Then** the embedded session resolves and the run proceeds; an unknown or stale
   request id yields an explicit negative result, never a crash.
3. **Given** an open session, **When** the client cancels it, **Then** the session is cancelled and
   never hangs on a pending approval or question.

---

### User Story 4 - Inspect sessions, history, and artifacts over the API (Priority: P4)

A client lists known sessions, fetches a session's metadata history snapshot, resumes a session, and
retrieves an offloaded artifact by its stable reference — all read-only, metadata-only endpoints.

**Why this priority**: After-the-fact inspection rounds out the host but is not required to drive a
run; it is valuable yet strictly additive to US1–US3.

**Independent Test**: After a run, call the list/history/artifact endpoints over the in-process client
and assert each returns the expected public-safe metadata, with unknown ids/references returning an
explicit not-found result.

**Acceptance Scenarios**:

1. **Given** one or more sessions on the host, **When** the client lists sessions, **Then** it
   receives their public-safe summaries.
2. **Given** a known session, **When** the client fetches its history snapshot, **Then** it receives a
   point-in-time metadata snapshot; an unknown session id yields an explicit not-found result.
3. **Given** an offloaded artifact reference, **When** the client retrieves it, **Then** it receives
   the artifact content, or an explicit not-found result when no artifact backend is configured or the
   reference is unknown — never a crash.

---

### User Story 5 - Guard every request behind an authentication boundary (Priority: P5)

Every request passes through an authentication/authorization boundary before reaching the embedded
host. The boundary is fail-safe default-deny, injectable by the embedder, and never echoes the
supplied credential.

**Why this priority**: A network host without an auth boundary is unsafe to expose, but the boundary
is a guard around the other stories rather than a capability a client consumes directly — so it is
specified last while remaining mandatory.

**Independent Test**: Issue requests with no credential, a malformed credential, and a valid
credential against an injected verifier, and assert default-deny for the first two and pass-through
for the third — with no credential echoed in any response.

**Acceptance Scenarios**:

1. **Given** a request with no credential or a malformed one, **When** it reaches the boundary,
   **Then** it is denied by default with an explicit, public-safe response.
2. **Given** an injected authenticator that verifies a credential, **When** a valid request arrives,
   **Then** it is admitted to the embedded host; **and** when the authenticator raises, the request is
   denied rather than crashing the host.
3. **Given** any denial, **When** the response is produced, **Then** it never echoes the supplied
   credential and never reveals resource existence beyond what an authorized caller could observe.

---

### Edge Cases

- **Concurrent run**: a run request arriving while a run is active → explicit, public-safe conflict
  response; no state corruption, no indefinite block (the embedded host is sequential per instance).
- **Client disconnects mid-stream**: the run still terminates and the consumer failure is recorded.
- **Stale / unknown ids**: answering an approval/question for a closed or unknown session or request
  id, fetching history for an unknown session, resuming an unknown session, or retrieving an unknown
  artifact reference → an explicit not-found / negative result, never a crash.
- **Malformed request**: missing fields or unparseable body → explicit client-error response with no
  internal stack trace, file path, internal type name, or secret leaked.
- **Raising injected callable**: a raising authenticator, approval handler, or event consumer is
  contained — the host denies / records and stays up (fail-safe posture inherited from unit 002).
- **Empty event stream**: a run that produces no events yields an empty, well-formed stream that
  closes cleanly, not an error.

## Requirements *(mandatory)*

### Functional Requirements

**Run execution (US1)**

- **FR-001**: The host MUST expose a request/response endpoint that accepts a prompt and starts a
  single LoopPlane run on an embedded host, returning the run's public-safe outcome (terminal reason,
  turns taken, and a metadata history snapshot).
- **FR-002**: The host MUST drive runs only through the public Host Application Interface and MUST NOT
  reach runtime internals, execute a tool itself, or re-implement the loop.
- **FR-003**: The host MUST preserve the embedded host's sequential-run guarantee: while a run is
  active, a second concurrent run request MUST receive an explicit, public-safe conflict response
  rather than corrupting state or blocking indefinitely.

**Event streaming (US2)**

- **FR-004**: The host MUST expose a live event-stream channel that delivers a run's normalized events
  to a connected client in their recorded order (ordered by the events' monotonic sequence, never by
  wall-clock).
- **FR-005**: Streamed events MUST be serialized public-safe using the established Phase-1 event
  serialization, carrying only the normalized event's public fields — no secrets, internal references,
  or content beyond what the normalized event already exposes.
- **FR-006**: A slow, failing, or disconnecting stream client MUST NOT crash or hang the underlying
  run; the run MUST still terminate, and the host MUST surface any consumer failure in the outcome.

**Interactive session (US3)**

- **FR-007**: The host MUST expose endpoints to open an interactive session, submit input to it, and
  obtain the resulting public-safe outcome.
- **FR-008**: The host MUST expose endpoints to answer a pending approval request and a pending
  question for an open session, mapping to the embedded session's answer operations; an unknown or
  stale request id MUST yield an explicit negative result, never a crash.
- **FR-009**: The host MUST expose an endpoint to cancel an open session such that a cancelled session
  never hangs on a pending approval or question.
- **FR-010**: Sessions exposed over the API MUST be addressed by their public session id only and MUST
  NOT leak internal handles or cross-session state.

**Inspection (US4)**

- **FR-011**: The host MUST expose read-only endpoints to list known sessions, fetch a session's
  metadata history snapshot, and resume a session; an unknown session id MUST yield an explicit
  not-found result.
- **FR-012**: The host MUST expose an endpoint to retrieve an offloaded artifact by its stable
  reference for a session, returning an explicit not-found result when no artifact backend is
  configured or the reference is unknown — never a crash.

**Authentication boundary (US5)**

- **FR-013**: Every request MUST pass through an authentication/authorization boundary before reaching
  the embedded host.
- **FR-014**: The boundary MUST be fail-safe default-deny — a missing, malformed, or unverifiable
  credential, or a raising authenticator, MUST result in denial — and the authenticator MUST be
  injectable by the embedder, with no built-in credential or identity store.
- **FR-015**: A denial MUST return an explicit, public-safe response that never echoes the supplied
  credential and never reveals resource existence beyond what an authorized caller could observe.

**Error handling (cross-cutting)**

- **FR-016**: A malformed or invalid request MUST receive an explicit, public-safe client-error
  response; the host MUST NOT return internal stack traces, file system paths, internal type names, or
  secrets in any response or stream message.
- **FR-017**: The host MUST originate no outbound network egress of its own; it serves an embedded
  host and makes no external calls.

### Non-Functional Requirements

- **NFR-001 (Boundary)**: The layer MUST compose only the public `loopplane.host` surface and the
  public Phase-1 event serialization; it MUST NOT import the controller, gateway, or any runtime
  internal. An import-boundary audit MUST enforce this (0 violations).
- **NFR-002 (Constitution V — Tool Gateway Ownership)**: The layer MUST execute no tool itself; tool
  execution remains the gateway's, reached only through the embedded host.
- **NFR-003 (Constitution VI — Runtime Event Bus Ownership)**: The layer MUST consume the normalized
  event stream as a host consumer and MUST NOT re-emit, wrap, or compete with the live event bus.
- **NFR-004 (Determinism)**: Given a recorded run, the streamed event order and serialization MUST be
  identical every time; authentication and request-validation verdicts MUST be a pure function of the
  request and the injected policy.
- **NFR-005 (Fail-safe)**: Empty or malformed input MUST map to an explicit safe response; a raising
  consumer, authenticator, or handler MUST never crash the host; authentication MUST default-deny.
- **NFR-006 (Public-safe / offline)**: All artifacts and responses MUST be English and public-safe (no
  secrets, private paths, internal names, or IPs); responses MUST be metadata-only; tests MUST run
  in-process with no real socket bound and no external network.
- **NFR-007 (Testability)**: Host-level integration tests MUST drive every endpoint and the event
  stream through an in-process client without binding a real network socket.

### Key Entities *(include if feature involves data)*

- **Run request / run result**: the public-safe request carrying a prompt, and the response carrying
  the run outcome (terminal reason, turns taken, metadata history snapshot). Metadata-only.
- **Event-stream message**: a single serialized normalized event (public fields only), delivered in
  recorded order over the live channel.
- **Session resource**: the network-facing handle onto an embedded interactive session, addressed by
  public session id; carries session id and lifecycle state, never internal handles.
- **Authentication boundary**: the injected verifier and its allow/deny decision over a request's
  credential; opaque, default-deny, never persisted by this layer.
- **Error / denial response**: an explicit, public-safe envelope describing a client error, conflict,
  not-found, or denial without internal detail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A client can start a run and receive its public-safe outcome entirely through the API,
  with zero direct references to runtime internals in the request/response path.
- **SC-002**: For a given recorded run, the streamed event sequence over the API matches the recorded
  normalized order exactly on every run (deterministic, not wall-clock dependent).
- **SC-003**: Across the full test corpus, 0 responses or stream messages leak a secret, private path,
  internal type name, IP, or stack trace.
- **SC-004**: 100% of requests with a missing, malformed, or unverifiable credential are denied by
  default; 0 such requests reach the embedded host.
- **SC-005**: A disconnecting or failing stream client never crashes or hangs the underlying run — the
  run terminates and reports the consumer failure in 100% of such cases.
- **SC-006**: An import-boundary audit confirms the layer composes only the public `loopplane.host`
  surface (+ public event serialization) with 0 violations, executes no tool, and re-emits no live bus
  event.

## Assumptions

- The specific web framework, transport, and event-stream protocol (a single-direction server→client
  push channel suffices, since client commands travel over the request/response endpoints) are chosen
  during planning for a minimal public surface and in-process, offline testability. The specification
  is framework- and protocol-agnostic.
- Authentication is a pluggable boundary — an embedder-injected verifier with default-deny. The host
  ships no user database, key store, token issuer, login flow, or identity UI.
- The host preserves the embedded host's sequential-run-per-instance guarantee. Concurrent multi-run
  execution, horizontal scaling, multi-tenancy, and load balancing are out of scope this phase.
- Transport security (TLS), production deployment and process management, CORS specifics, and rate
  limiting / quota enforcement are deployment- and governance-level concerns out of scope this phase
  (budgets and quotas are unit 009).
- No frontend, dashboard, or UI is built (reserved for unit 012). This unit ships the network API, the
  event-stream channel, the auth boundary, host-level integration tests, a public-safe example, and a
  docs guide only.
- The unit depends on unit 002 (Host Application Interface) for the embedded host surface and on unit
  001 (runtime foundation) for the normalized event serialization; it adds no new public contract to
  either.

### Reserved extension points (named, not built)

- A web UI / frontend / dashboard (unit 012 — desktop / studio host).
- Real cloud deployment, TLS termination, multi-process / worker scaling, and load balancing.
- Multi-tenant user management, a persistent credential / identity store, and OAuth / SSO providers.
- Rate limiting and quota enforcement beyond the auth boundary (governance is unit 009).
- Bidirectional realtime collaboration and distributed session sharing across hosts.
- Persisting API request/response logs or transcripts.
