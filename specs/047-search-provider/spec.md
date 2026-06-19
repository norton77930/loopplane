# Feature Specification: Reference Search Provider

**Feature Branch**: `047-search-provider`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "A reference SearchProvider implementation behind an optional extra so the `web_search` tool (034) works out of the box — host-configurable, with no bundled API key required at import. Unit 047, Tier-1 (final unit); closes gap G4. Additive; reuses the 034 web-tool seam + network governance."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `web_search` works without writing a provider (Priority: P1)

A host enables network egress and the bundled reference search provider; the agent calls
`web_search` and gets ranked results — without the host having to write its own
`SearchProvider`. Previously `web_search` returned "not configured" unless the host supplied
one (unit 034); now LoopPlane ships a usable provider.

**Why this priority**: This is the gap (G4) and the unit's whole point — `web_search` is
unusable out of the box today because LoopPlane ships no provider; a reference provider makes
it work.

**Independent Test**: Construct the web tool adapter with the reference provider (using a
mocked HTTP transport), call `web_search`, and confirm it returns parsed `SearchResult`s in
the existing result shape.

**Acceptance Scenarios**:

1. **Given** the reference provider is configured and network egress is enabled, **When** the
   agent runs `web_search`, **Then** it returns ranked results (title / url / snippet) in the
   existing `web_search` output format.
2. **Given** the reference provider's default keyless backend, **When** a host enables it,
   **Then** no API key is required for `web_search` to return results.

---

### User Story 2 - Configurable and credential-safe (Priority: P2)

The provider is host-configurable (which backend / endpoint, and an injected API key for
backends that need one); it bundles no API key, imports without the network dependency, and
never leaks a key or transport internal in its output or errors.

**Why this priority**: Public-safety and flexibility — LoopPlane must not bundle a credential
(VII) and a host should be able to point the provider at a different backend or supply a key.

**Independent Test**: Import the provider package without the optional network extra installed
(no import error); construct it with an injected key and confirm the key never appears in
results or normalized errors.

**Acceptance Scenarios**:

1. **Given** the optional network extra is not installed, **When** the provider package is
   imported, **Then** the import succeeds (the network dependency is loaded lazily, only on a
   real search).
2. **Given** a backend failure (timeout / transport error / unexpected response), **When**
   `web_search` runs, **Then** the existing normalized error path is used — no key, header, or
   raw transport object is leaked (consistent with unit 034).

---

### User Story 3 - Bounded, governed, reuse-first (Priority: P3)

The provider returns at most the requested number of results, runs only when network egress
is enabled (unchanged unit-034 governance), and reuses the existing `SearchProvider` /
`SearchResult` seam and the optional network extra — no new dependency, no new tool, no
change to `web_search` itself.

**Why this priority**: Consistency — the provider plugs into the existing seam and governance
rather than introducing a parallel path.

**Independent Test**: Request `limit=N`; confirm at most N results. Confirm `web_search`'s
descriptor, the network policy, and the `SearchProvider`/`SearchResult` shapes are unchanged.

**Acceptance Scenarios**:

1. **Given** a `limit`, **When** `web_search` runs through the reference provider, **Then** at
   most `limit` results are returned.
2. **Given** network egress is disabled, **When** the agent calls `web_search`, **Then** it is
   denied by the existing network policy (the provider does not bypass governance).

---

### Edge Cases

- **Network extra not installed**: importing the provider still works; an actual search yields
  the existing normalized "requires the optional 'net' extra" error.
- **No results**: the existing "no results" path is used.
- **Backend returns malformed/unexpected data**: parsed defensively; a fault becomes the
  existing normalized search-failure error (no crash, no leak).
- **Backend needs a key but none is configured**: a clear normalized error (no bundled key).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: LoopPlane MUST ship a concrete reference `SearchProvider` implementing the
  existing unit-034 seam (`async search(query, *, limit) -> Sequence[SearchResult]`), usable
  by a host without writing its own provider.
- **FR-002**: The reference provider MUST have a keyless default backend so `web_search`
  returns results out of the box once network egress and the provider are enabled, with no
  bundled or required API key.
- **FR-003**: The provider MUST be host-configurable — the backend/endpoint is selectable and,
  for a backend that requires one, an API key is injected by the host (never bundled).
- **FR-004**: The provider MUST reuse the optional network extra (`net`, from unit 034),
  imported lazily, so the provider package imports without the extra installed.
- **FR-005**: The provider's HTTP access MUST be injectable (a transport/fetcher seam) so it is
  fully tested offline with a mocked transport (no real network in tests).
- **FR-006**: Results MUST be parsed defensively into `SearchResult` (title / url / snippet),
  bounded by the requested `limit`; a malformed or failing backend MUST surface through the
  existing normalized `web_search` error path with no leaked key/header/transport internal.
- **FR-007**: The provider MUST NOT bypass governance — `web_search` remains network-gated by
  the unit-034 network policy and unchanged in descriptor/behavior; this unit only supplies a
  provider the host can inject.
- **FR-008**: Adding the provider MUST be additive: no change to the `SearchProvider` /
  `SearchResult` seam, the `web_search` tool, the event schema, or the content model; no new
  required dependency.

### Key Entities *(include if feature involves data)*

- **Reference search provider**: a concrete `SearchProvider` that queries a web-search backend
  over HTTP and maps responses to `SearchResult`s.
- **Search backend**: the upstream service the provider queries — a keyless default, or a
  host-selected endpoint (with an injected key when required).
- **Transport seam**: an injectable async HTTP callable so the provider is offline-testable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the reference provider enabled (mocked transport in tests), `web_search`
  returns parsed results in the existing format — proving `web_search` is usable without a
  host-written provider.
- **SC-002**: The provider package imports with the optional network extra absent (no import
  error); a search without the extra yields the existing normalized extra-required error.
- **SC-003**: No API key, header, or transport internal appears in any result or error in any
  scenario.
- **SC-004**: Existing behavior is unaffected — the full test suite passes unchanged and no
  event-schema, content-model, or `web_search`-tool change is introduced.

## Assumptions

- "Works out of the box" uses a keyless web-search backend (e.g., a no-key public endpoint);
  the exact backend is a planning/implementation choice and is offline-tested via a mocked
  transport. Host-configurable alternatives (including keyed backends) are supported by
  injection.
- The provider reuses the unit-034 `SearchProvider`/`SearchResult` seam and the optional `net`
  extra (`httpx`), imported lazily; no new dependency is added.
- The provider is opt-in: a host constructs the web tool adapter with it (and enables network
  egress). It does not change `web_search` or its default "not configured" behavior when a host
  does not use it.
- Out of scope: result ranking/scoring beyond what the backend returns; multiple simultaneous
  backends; caching of search results; a search UI.
- Per Constitution IX, the concept (a default search provider, as the reference harnesses ship)
  is re-derived; VII forbids bundling any credential.
