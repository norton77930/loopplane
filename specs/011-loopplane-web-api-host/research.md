# Phase 0 Research: Web / API Host

All decisions resolve the spec's NEEDS-nothing-CLARIFICATION context into concrete, public-safe,
offline-testable choices. The layer is an **additive transport** over the public Host Application
Interface (unit 002); it adds no runtime behavior.

## D1 — Web framework: FastAPI (on Starlette)

**Decision**: Use **FastAPI** (which bundles **Starlette**) as the web transport, packaged as an
optional `web` extra and added to the `dev` group (with `httpx`) for CI.

**Rationale**:
- **Reuses existing dependencies**: the project already depends on `pydantic>=2` and `anyio>=4`.
  Starlette's async core is `anyio`; FastAPI's request/response validation is `pydantic`. The net new
  surface is small and aligned with what is already vendored.
- **Error hygiene for free (FR-016)**: pydantic request models turn malformed input into a clean,
  fixed validation error rather than an unhandled exception — no stack trace, path, or internal type
  leaks. This directly serves the public-safe error requirement.
- **Injectable auth seam (FR-013–FR-015)**: FastAPI dependency injection models the
  embedder-injected authenticator cleanly and runs it before any handler — the natural home for a
  default-deny boundary.
- **Offline, in-process testing (NFR-006/NFR-007)**: Starlette's `TestClient` (httpx-based) drives
  the full app **in-process with no real socket bound** and supports streaming responses — exactly
  what the integration + contract suites need.
- **Board-sanctioned**: the roadmap names "FastAPI or equivalent" for unit 011.

**Alternatives considered**:
- **Starlette alone** — lighter, but drops FastAPI's pydantic-based request validation and typed
  responses, pushing validation/error hygiene into hand-written code (more leak surface for FR-016).
  Rejected: the validation layer reuses a dep we already have and removes boilerplate.
- **stdlib `http.server` / hand-rolled ASGI** — no new dependency, but reinvents routing, validation,
  SSE framing, and an in-process test client; large, error-prone, and a poor fit for FR-016/NFR-007.
  Rejected.
- **Flask / Django** — sync-first (Flask) or heavy/batteries-included (Django); neither reuses
  `anyio`/`pydantic`, and async streaming is a weaker fit. Rejected.

**Constitution VIII note**: Principle VIII forbids replacing the **runtime core** (Agent Loop,
Controller, Dispatcher, Tool Gateway, Event Bus) with an **agent** framework. FastAPI/Starlette is a
**web transport** for an additive host layer; it is not the runtime core and replaces no runtime
component. The runtime is reached only through the public `loopplane.host` seam. This is outside the
prohibition. Recorded in the plan's Complexity Tracking for the review gate.

## D2 — Event stream transport: Server-Sent Events (SSE)

**Decision**: Stream the run's normalized events to clients over **SSE** — a plain streaming response
with media type `text/event-stream`, each frame `data: <json>\n\n`, where `<json>` is
`serialize_event(event)`. No extra dependency (no `sse-starlette`); a plain async generator suffices.

**Rationale**: The event stream is **single-direction server→client** push — the client receives
normalized events as the run progresses. Client commands (submit, answer, cancel) travel over the
ordinary request/response endpoints, so the bidirectionality of WebSockets is unnecessary. SSE is
simpler, needs no extra dependency, and is trivially testable in-process.

**Alternatives considered**:
- **WebSocket** — bidirectional, heavier; would duplicate command paths that already exist as REST
  endpoints. Rejected as unnecessary complexity (kept as a reserved extension point).
- **Long-poll / chunked JSON** — clumsier framing and ordering guarantees than SSE. Rejected.

## D3 — Content discipline: metadata-only responses, verbatim-normalized stream

**Decision**: Draw a hard line between two surfaces:
- **JSON response bodies** (RunResult, history snapshot, session summary, errors) are **metadata-only
  projections**: history is `{role, block_count}` per entry; never the `ContentBlock` text or tool
  input/output. ids, counts, termination reasons, and lifecycle state only (FR-016, NFR-006).
- **The SSE event stream** carries each normalized event exactly as `serialize_event` exposes it —
  which legitimately includes the run's own content (assistant output, user input, tool metadata),
  because that is what a streaming consumer needs (FR-005).

**Rationale**: `HistoryEntry.blocks` carries conversation content, so echoing a history snapshot raw
would leak content into a summary response — disallowed. The event stream is different: Constitution
VI defines streaming/observability consumers as recipients of the **normalized event stream**, which
includes content by design; an authenticated client receiving the run's own output is the intended
behavior, not a leak. Principle VII (public-safe **committed artifacts**) is satisfied independently:
the committed code, tests, example, and doc use only public-safe fixtures, and the host's own framing
(errors, envelopes) never leaks secrets, internal types, or paths (SC-003).

**Alternatives considered**:
- **Stream metadata-only events** — would cripple the stream's purpose (a client could not display
  assistant output). Rejected; contradicts Constitution VI.
- **Return full history in responses** — content-leak surface in summaries with no consumer need.
  Rejected.

## D4 — Authentication: pluggable, default-deny boundary

**Decision**: Authentication is an **embedder-injected verifier** —
`Authenticator = Callable[[str | None], Awaitable[bool]]` (or a small protocol returning an opaque
principal) — enforced by a FastAPI dependency on **every** route. The credential is read from a
request header. Semantics: missing credential ⇒ deny; verifier returns falsy ⇒ deny; verifier
**raises** ⇒ deny (fail-safe). If **no** authenticator is injected, the default is **deny-all**, so
an unconfigured host is safe.

**Rationale**: Consistent with LoopPlane's inject-your-policy pattern (`on_approval`, `InputSource`,
adapters). Keeps the layer a **boundary contract**, not a user-management system — no credential
store, token issuer, or login flow (FR-014). Default-deny + deny-on-raise is the fail-safe posture
(NFR-005, SC-004). Denials return a fixed public-safe envelope that never echoes the credential
(FR-015).

**Alternatives considered**:
- **Built-in API-key/user store** — turns a boundary into an identity system; out of scope and a
  persistence/secret surface we do not want. Rejected (reserved extension point).
- **No auth / opt-in auth** — fail-open; unacceptable for a network host. Rejected.

## D5 — Interactive sessions over stateless HTTP

**Decision**: Model an interactive session (US3) with a **session registry** held in the app's
lifespan-scoped state. Opening a session enters `async with host.session(on_event=sse_sink)` inside a
background task (anyio task group) and registers the live `Session` handle by its public `session_id`.
- `submit` drives the run in the background; events flow on the session's SSE stream.
- `answer_approval` / `answer_question` look up the `Session` and call its (synchronous, out-of-band)
  resolve methods — exactly how the Phase-2 interactive model expects a reviewer to answer.
- `cancel` calls `Session.cancel()`, which also resolves anything the loop is parked on, so a
  cancelled session never hangs (FR-009).
Because `LoopPlaneHost` is **sequential per instance**, at most one run/session is active at a time;
opening or running a second while one is active maps the host's `RuntimeError` to a **409 Conflict**
(FR-003).

**Rationale**: The Phase-2 controller already supports **out-of-band** approval/question resolution
(the reviewer answers from outside the driving call). The registry keeps the `Session` reachable
across requests; the background task owns the `async with` lifetime; the SSE stream surfaces the
approval/question requests the client must answer. This is the faithful mapping of the in-process
interactive round-trip onto request/response + stream.

**Alternatives considered**:
- **Synchronous submit that awaits completion** — cannot work for approvals (the answer must arrive
  *during* the parked run, from a different request). Rejected.
- **Multiple concurrent sessions per host** — unsupported by the sequential host; would need a host
  pool (out of scope this phase). Rejected; documented as the sequential-per-instance assumption.

## D6 — Offline testing: in-process TestClient

**Decision**: All integration + contract tests drive the app through Starlette's `TestClient`
(httpx-based) — **no real socket is bound, no external network is used** (NFR-006/NFR-007, FR-017).
Streaming endpoints are exercised via the client's streaming response; concurrent answer requests
during an open stream use the client's thread-portal. A public-safe **fake model** (mirroring prior
units' example/test fakes) drives deterministic runs; event order on the stream is asserted equal to
the recorded `serialize_event` order (SC-002).

**Rationale**: Determinism and offline are mandatory; the `TestClient` gives both with the real ASGI
app (no mocking of the framework). The fake model removes any real LLM/network dependency.

## D7 — Dependency packaging

**Decision**: Add `fastapi` to a new `[project.optional-dependencies] web = ["fastapi>=0.115"]`
extra, and add `fastapi` + `httpx` to the `[dependency-groups] dev` so CI installs and runs the web
suite. The core install (`anyio`, `pydantic`, `jsonschema`) is unchanged.

**Rationale**: Mirrors the existing `mcp` / `otel` pattern (optional runtime extra **and** present in
dev so tests run). Keeps the web host opt-in for embedders who do not need it; keeps CI coverage.

**Validation impact**: the implement step installs the `web` extra + `httpx` locally before running
`pytest`; the integration/contract suites are skipped-or-run based on `fastapi` availability following
the repo's existing optional-import test convention.

## Open questions

None. All choices above are informed defaults documented in the spec's Assumptions; none is
scope-blocking, so no `[NEEDS CLARIFICATION]` markers remain.
