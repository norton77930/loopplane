# Research: Reference Search Provider

No open `NEEDS CLARIFICATION`. Decisions below.

## Decision 1 — Keyless default backend: DuckDuckGo Instant-Answer JSON

**Decision**: The default backend is the DuckDuckGo Instant-Answer JSON API
(`https://api.duckduckgo.com/?q=<query>&format=json&no_html=1&no_redirect=1`). Parse
`AbstractText`/`AbstractURL` (when present) and `RelatedTopics[]` (`Text`, `FirstURL`) into
`SearchResult`s.

**Rationale**: It is **keyless** (satisfies "out of the box" + no bundled credential, VII),
returns **JSON** (parsed with the standard library — no HTML scraper, no new dependency), and
is a stable public endpoint. The endpoint is configurable so a host can point at an alternative.

**Alternatives considered**: the DuckDuckGo HTML endpoint (rejected — needs an HTML parser /
fragile regex); SerpAPI / Brave (rejected as the *default* — they require an API key, so they
cannot work out of the box; they remain reachable as a host-configured endpoint + injected key).
**Limitation (documented)**: Instant-Answer returns instant answers + related topics, not a
full ranked web result list; it is a reference default, not a production search engine.

## Decision 2 — Injectable async transport (offline-testable)

**Decision**: `ReferenceSearchProvider` takes an optional async transport
`(url) -> (status_code, body_text)` (the same shape as `web.py`'s `Fetcher`); the default
transport lazily imports `httpx` and performs the GET (mirroring `_httpx_fetch`).

**Rationale**: Reuse-first (the unit-034 transport shape) and the only way to test fully
offline (a stub transport returns canned DuckDuckGo JSON; no real network in tests). Lazy
import keeps the package importable without the `net` extra (FR-004).

**Alternatives considered**: hard-coding `httpx` inside `search()` (rejected — not testable
offline, and forces the extra at import).

## Decision 3 — Module placement & export

**Decision**: A new `loopplane.tools.search` module holds `ReferenceSearchProvider`, importing
`SearchProvider`/`SearchResult` from `loopplane.tools.web`. Export `ReferenceSearchProvider`
from `loopplane.tools` and document it in `docs/api-reference.md` (so the unit-014 bijection
stays green), mirroring how the 034 web names are exported.

**Rationale**: Keeps `web.py` focused on the seam + `web_search`; the provider is a separate,
opt-in collaborator a host imports and injects.

**Alternatives considered**: adding it inside `web.py` (rejected — mixes the seam with one
concrete impl); not exporting it (rejected — a host must be able to import and inject it).

## Decision 4 — Defensive parsing, bounding, and failure normalization

**Decision**: Parse results defensively (skip entries without a usable `Text`/`FirstURL`),
return at most `limit` results, and let a transport/parse fault raise — `web_search` already
catches any provider exception and emits the existing normalized "web search failed" error
(no key/header/transport leak). A non-2xx response raises a provider error (→ normalized).

**Rationale**: Reuses the unit-034 normalization at the Gateway boundary (V, VII); the provider
stays simple and never leaks internals.

**Alternatives considered**: the provider swallowing errors and returning `[]` (rejected —
hides failures; the "no results" path should mean genuinely no results, not a transport error).

## Decision 5 — No change to the seam, the tool, or governance

**Decision**: `SearchProvider`/`SearchResult`, `web_search`, the network policy, the event
schema, and the content model are all unchanged; this unit only adds an injectable
implementation + its export.

**Rationale**: Additive, reuse-first (VI, X); the gap (G4) is "ship a provider," not "change
web_search."
