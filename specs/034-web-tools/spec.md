# Feature Specification: Web Tools (web_fetch + web_search) with Network-Egress Governance

**Feature Branch**: `034-web-tools` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "LoopPlane web tools. Add two NETWORK tools through the Tool Gateway — web_fetch (fetch an http(s) URL to readable text, with a small per-session in-memory cache) and web_search (run a query via a host-pluggable search provider injected by config, no bundled API key) — plus the governance seam gating network egress: a ToolDescriptor.network flag (additive, default False) and a network_policy decider that denies network-flagged tools unless the host explicitly enables egress (default-deny / opt-in), composed through the existing decide-stage combinators (deny-wins + fail-closed). Promote httpx to a declared optional extra; core install must not require it. Additive backend change, no frontend, no ADR."

## Overview

The baseline tool set lets an agent read, write, edit, glob, grep, and run
commands inside the run working scope — all **offline**, all dependency-light.
An agent doing real work also needs to reach the network: to fetch a page it was
pointed at, or to look something up. LoopPlane has no built-in way to do either,
and — just as important — **no governed seam to decide whether a run is even
allowed to touch the network at all**.

This unit closes that gap with **two additive NETWORK tools on a new Web Tool
Adapter** — `web_fetch` and `web_search` — each reachable **only through the
Tool Gateway** (Constitution V) and **gated by an opt-in network-egress policy**:

1. **`web_fetch`** retrieves an `http(s)` URL and returns its body as readable
   text, with a small **per-session in-memory cache** so a repeated fetch within
   a session does not re-hit the network. A bad URL, a non-`http(s)` scheme, a
   timeout, or a transport error becomes a **normalized `ErrorOutput`**, never a
   raw exception or a leaked transport internal (Constitution V, VII).
2. **`web_search`** runs a query against a **host-pluggable search provider**
   injected by configuration. LoopPlane ships **no API key and no bundled
   provider**; when none is configured, `web_search` returns a clear normalized
   error ("web search is not configured"), never a crash.
3. A new additive **`ToolDescriptor.network` flag** (default `False`) marks a
   tool as requiring network egress; the two web tools set it, every existing
   descriptor keeps the default.
4. A **`network_policy` decider** denies any network-flagged tool **unless the
   host explicitly enables network egress** (default-deny / opt-in), composed
   through the **existing decide-stage combinators** (deny-wins + fail-closed) —
   **no new gateway stage**.

`httpx` is promoted from a dev-only dependency to a **declared optional extra**;
the core install does not require it, and it is imported only when present and
enabled. The change is purely additive: the gateway pipeline, the event bus, the
loop contract, and every existing tool are untouched (Constitution IV, X).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Network egress is denied by default and opt-in (Priority: P1)

A host that does nothing special gets a runtime where the agent **cannot** reach
the network: a call to a network-flagged tool is denied at the Gateway's decide
stage with a normalized policy-denial, and the run stays alive. A host that
**explicitly enables network egress** gets those same tools allowed. The policy
fails **closed** — if it ever raises, the call is denied, never silently
allowed.

**Why this priority**: The governance seam is the foundation. The web tools are
only safe to ship because the runtime can refuse network egress by default; this
is the highest-value, must-exist-first behavior.

**Independent Test**: Build the decider for a config with egress off and assert a
network-flagged descriptor is denied while a non-network descriptor is allowed;
build it with egress on and assert the network descriptor is allowed; make the
inner policy raise and assert the verdict is still deny (fail-closed).

**Acceptance Scenarios**:

1. **Given** a runtime with network egress **disabled** (the default), **When** a network-flagged tool is decided at the Gateway, **Then** it is denied with a normalized policy-denial and the run continues.
2. **Given** a runtime with network egress **enabled**, **When** a network-flagged tool is decided, **Then** it is allowed (subject to any other policy, deny-wins).
3. **Given** any non-network tool, **When** it is decided, **Then** the network policy never denies it (behavior unchanged).
4. **Given** a policy in the composed chain raises, **When** a call is decided, **Then** the verdict is deny (fail-closed), never a silent allow.

### User Story 2 - Fetch a URL to readable text, cached per session (Priority: P2)

With network egress enabled, an agent fetches an `http(s)` URL with one
`web_fetch` call and gets the page body back as readable text. Fetching the same
URL again in the same session is served from an in-memory cache without a second
network round-trip. A malformed URL, a non-`http(s)` scheme, a timeout, or a
transport failure returns a normalized error and never crashes the run.

**Why this priority**: Fetching a known URL is the most common network primitive
an agent needs and the simplest to make deterministic and safe.

**Independent Test**: Drive the adapter through a mocked transport: assert a
success returns the body text and records a cache entry; assert a second fetch of
the same URL does not call the transport again; assert a bad scheme / a timeout /
a transport error each yields a normalized `ErrorOutput` with no secret in the
message.

**Acceptance Scenarios**:

1. **Given** a reachable `http(s)` URL, **When** `web_fetch` is called, **Then** it returns the response body as readable text and caches it for the session.
2. **Given** a URL already fetched this session, **When** `web_fetch` is called again, **Then** the cached text is returned without a second network call.
3. **Given** a non-`http(s)` URL (e.g. `file://`, `ftp://`) or a malformed URL, **When** `web_fetch` is called, **Then** it returns a normalized validation error and performs no fetch.
4. **Given** a timeout or transport error, **When** `web_fetch` is called, **Then** it returns a normalized error (no raw exception, no leaked internals) and the run continues.

### User Story 3 - Search via a host-pluggable provider, clear error when unconfigured (Priority: P3)

With a search provider configured, an agent runs a query with one `web_search`
call and gets back a readable, ranked list of results (title + URL + snippet).
With **no** provider configured, `web_search` returns a clear normalized error
telling the host that search is not configured — it never crashes and never
embeds a bundled key.

**Why this priority**: Search is valuable but inherently host-dependent (every
provider needs the host's own credential); the must-have behavior is that the
unconfigured path degrades cleanly.

**Independent Test**: Inject a stub provider and assert a query returns the
provider's results rendered as text; construct the adapter with no provider and
assert `web_search` returns a normalized "not configured" error; make the
provider raise and assert a normalized error (no leaked internals).

**Acceptance Scenarios**:

1. **Given** a configured search provider, **When** `web_search` is called with a query, **Then** it returns the provider's results rendered as readable text.
2. **Given** no search provider configured, **When** `web_search` is called, **Then** it returns a normalized error ("web search is not configured") and does not crash.
3. **Given** a provider that raises, **When** `web_search` is called, **Then** it returns a normalized error with no leaked transport internals.

### Edge Cases

- **Network egress disabled** → both web tools are denied at the decide stage (policy-denial); they never reach execution.
- **`httpx` not installed** while egress is enabled → `web_fetch` returns a normalized error explaining the optional extra is required, never an `ImportError` crossing the boundary.
- **Non-`http(s)` scheme / malformed URL** → normalized validation error; no fetch attempted (an SSRF-narrowing guard, not a full SSRF policy).
- **Timeout / connection error / non-2xx status** → normalized error; the message carries no credential, header, or raw transport object.
- **Search provider absent** → a clear "not configured" validation error, not a crash.
- **Search provider raises / returns nothing** → a normalized error / an explicit "no results" message respectively.
- **Cache scope** → the fetch cache is keyed per `(session_id, url)` and lives only in memory for the adapter's lifetime; it is never persisted and never shared across sessions.
- **Oversized response body** → bounded by the Gateway's existing output size management (no new mechanism); the adapter returns text and the Gateway sizes it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unit MUST add `web_fetch` and `web_search` as tools on a Web Tool Adapter, each reachable **only through the Tool Gateway** with no bypass path (Constitution V), returning outputs as the gateway output union (`TextBlock` / `ErrorOutput`).
- **FR-002**: `web_fetch` MUST retrieve an `http(s)` URL and return its body as readable text; a non-`http(s)` scheme or a malformed URL MUST be rejected with a normalized validation error and perform no fetch.
- **FR-003**: `web_fetch` MUST maintain a **per-session in-memory cache** keyed by `(session_id, url)`; a repeat fetch of the same URL in the same session MUST be served from the cache without a second network call.
- **FR-004**: `web_fetch` MUST normalize a timeout, a connection/transport error, and a non-success HTTP status into an `ErrorOutput` (never a raised exception across the boundary), and the message MUST NOT contain credentials, request headers, or raw transport internals (Constitution VII).
- **FR-005**: `web_search` MUST run a query against a **host-injected search provider**; LoopPlane MUST NOT bundle an API key or a default network provider.
- **FR-006**: When no search provider is configured, `web_search` MUST return a normalized error ("web search is not configured") and MUST NOT crash the run.
- **FR-007**: `web_search` MUST normalize a provider error into an `ErrorOutput` with no leaked internals, and MUST render successful results as readable text (and an explicit "no results" message when empty).
- **FR-008**: `ToolDescriptor` MUST gain an **additive** boolean field `network` defaulting to `False`; `web_fetch` and `web_search` MUST set `network=True`; every existing descriptor MUST keep the default (unchanged behavior).
- **FR-009**: A `network_policy` decider MUST **deny** any descriptor with `network=True` unless the host has explicitly enabled network egress, and MUST never deny a non-network descriptor.
- **FR-010**: The `network_policy` decider MUST be composed into the Gateway's decide stage through the **existing combinators** (`all_of` deny-wins + `safe_failure` fail-closed) in the host's decider builder — **no new gateway stage** is added.
- **FR-011**: Network egress MUST default to **off** (default-deny / opt-in); a host enables it through an additive, public-safe configuration flag carrying **no secret**.
- **FR-012**: `httpx` MUST be declared as an **optional extra** (core install MUST NOT require it); `web_fetch` MUST import it **only when present/enabled** and degrade to a normalized error when it is absent.
- **FR-013**: The unit MUST be **additive only** — no change to the gateway pipeline, the event bus, the loop contract, or any existing tool's behavior (Constitution IV, X). Existing descriptors and policies are unchanged.
- **FR-014**: All new behavior MUST be covered by **deterministic, offline** unit tests (mocked transport, stub provider); any live web test MUST be **opt-in / secret-gated** and excluded from the default gates. The four quality gates MUST stay green.

### Key Entities

- **`web_fetch` tool**: a network baseline tool that fetches an `http(s)` URL to readable text, with a per-session in-memory cache; `network=True`, not `read_only` (it reaches out, though it mutates no scope state — treated as a non-read-only network action for governance clarity).
- **`web_search` tool**: a network baseline tool that runs a query through a host-injected provider; `network=True`.
- **Search provider seam**: a host-supplied object with a single async `search(query, *, limit) -> results` method; LoopPlane ships none.
- **`ToolDescriptor.network`**: the additive descriptor flag (default `False`) that the network policy gates on.
- **`network_policy` decider**: a decide-stage policy that denies network-flagged tools unless egress is enabled, composed deny-wins + fail-closed through the existing combinators.
- **Network-egress toggle**: an additive, public-safe runtime-configuration flag (default off) that enables network-flagged tools.

### Out of Scope

- A full SSRF / allow-list / DNS-rebinding policy (only a minimal `http(s)`-scheme guard ships here; richer host-side network policy is reserved).
- A bundled search provider or any embedded API key — search is host-pluggable only.
- HTML-to-markdown extraction beyond returning the response body as decoded text (a readable-text transform may be a later refinement).
- A persistent or cross-session fetch cache (the cache is per-session, in-memory, ephemeral).
- Streaming / chunked fetch, downloads to disk, authenticated fetch, cookies, or redirects-policy configuration.
- Any frontend change, any change to `search_files` / the existing file tools, the gateway pipeline, the event bus, or the loop contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the default config, an attempt to use a network tool is denied at the Gateway with a policy-denial and the run continues; enabling egress allows the same tool.
- **SC-002**: `web_fetch` returns a URL's body as text on success, serves a repeat fetch from cache with no second network call, and turns a bad scheme / timeout / transport error into a normalized error with **no** secret in the message.
- **SC-003**: `web_search` returns provider results as text when configured and a clear "not configured" normalized error when not — never a crash, never a bundled key.
- **SC-004**: The `network` flag defaults to `False`, every existing descriptor is unchanged, and the network policy never affects a non-network tool.
- **SC-005**: `httpx` is an optional extra; the core install does not require it; the four quality gates (ruff, ruff format, mypy, pytest) stay green with new deterministic offline tests, and any live test is opt-in/secret-gated.

## Assumptions

- **Host owns the credential**: every real search provider needs the host's own API key; LoopPlane only defines the seam and injects the host's object — no secret lives in the repo or in `RuntimeConfig` (Constitution VII).
- **Default-deny network**: a run cannot reach the network unless the host opts in; this mirrors the project's safe-by-default governance posture (deny-wins, fail-closed).
- **Reuse, don't reinvent**: the network policy is built from the existing `governance` combinators (`all_of`, `safe_failure`, `as_decider`) and composed in the existing `_build_decider`; no new gateway stage and no new policy machinery.
- **Dependency-light core**: `httpx` is the single new optional dependency, declared as an extra and imported lazily; the core runtime keeps its current dependency set.
- **Deterministic tests**: the transport and the provider are injected/mocked so every default test is offline and deterministic; a live check is opt-in and secret-gated, excluded from default gates.
- **Additive and reversible**: removing the Web Tool Adapter, the `network` field, the `network_policy`, the egress flag, and the extra leaves the baseline set, the gateway, and all components untouched (Constitution X rollback).
