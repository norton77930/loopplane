# Implementation Plan: Reference Search Provider

**Branch**: `047-search-provider` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/047-search-provider/spec.md`

## Summary

Ship a concrete reference `SearchProvider` so the unit-034 `web_search` tool works out of the
box. A new `loopplane.tools.search` module provides a `ReferenceSearchProvider` implementing
the existing seam (`async search(query, *, limit) -> Sequence[SearchResult]`). Its default
backend is the **keyless** DuckDuckGo Instant-Answer JSON API (no bundled or required API key);
results (`RelatedTopics` / `AbstractText`) are parsed defensively into `SearchResult`s and
bounded by `limit`. HTTP access is an **injectable async transport** (default a lazily-imported
`httpx` GET, reusing the unit-034 `net` extra) so the provider is fully offline-tested with a
mocked transport. A host opts in by constructing `WebToolAdapter(search_provider=...)`;
`web_search`, the `SearchProvider`/`SearchResult` seam, the network policy, the event schema,
and the content model are all unchanged.

## Technical Context

**Language/Version**: Python 3.11+ (`loopplane`)

**Primary Dependencies**: none new — reuses the unit-034 optional `net` extra (`httpx`),
imported lazily; standard-library `json`/`urllib` for the request/parse

**Storage**: N/A (stateless per query; no result caching in v1)

**Testing**: pytest, offline (a stub async transport returns canned DuckDuckGo-shaped JSON;
an import-without-extra test; a no-key-leak test)

**Target Platform**: cross-platform library

**Project Type**: single project (library + tests)

**Constraints**: additive / reuse-first; no bundled API key (VII); the `net` extra imported
lazily so the package imports without it; reachable only via `web_search`'s existing
network-gated path; no event-schema/content-model change; no ADR

**Scale/Scope**: one new module (`loopplane.tools.search`) + an export + tests; no change to
`web.py`'s `web_search`/seam

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-008. ✅
- **IV. Runtime Boundary Clarity**: The provider implements the existing host-injected
  `SearchProvider` seam; it is an injected collaborator, not a new runtime boundary. ✅
- **V. Tool Gateway Ownership**: `web_search` is unchanged and remains the only Gateway tool;
  the provider runs behind it, network-gated by the existing policy. ✅
- **VI. Event Bus Ownership**: No event-schema / content-model change; results flow through the
  existing `web_search` `TextBlock` output. ✅
- **VII. Public-Safe**: No API key is bundled; the keyless default needs none, and an injected
  key (for keyed backends) is never emitted in results or errors. ✅
- **VIII. No SDK Replacement**: A thin HTTP call to a public search backend through the existing
  transport seam; no framework added. ✅
- **IX. Reference, Not Clone**: A default search provider is re-derived; the DuckDuckGo endpoint
  is a public API, not copied harness code. ✅
- **X. Testable Evolution**: Additive and reversible (drop the module + export); offline-tested
  via the injectable transport; default behavior of `web_search` (no provider → "not
  configured") is unchanged unless a host opts in. ✅

**Result**: PASS — no violations; no ADR. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/047-search-provider/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/search-provider.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
src/loopplane/tools/
├── web.py               # UNCHANGED: the SearchProvider/SearchResult seam + web_search
└── search.py            # NEW: ReferenceSearchProvider (default keyless DuckDuckGo backend;
                         #      injectable async transport; lazy httpx; host-configurable)

src/loopplane/tools/__init__.py   # MODIFIED: export ReferenceSearchProvider (api-reference)
docs/api-reference.md             # MODIFIED: document the new exported name (bijection)

tests/unit/test_search_provider.py   # NEW: offline coverage (parse, limit, lazy import,
                                      #      no-key-leak, malformed-response handling)
```

**Structure Decision**: A new `loopplane.tools.search` module beside `web.py`, importing the
existing `SearchProvider`/`SearchResult` from `web.py`. The provider takes an injectable async
transport (mirroring `web.py`'s `Fetcher`/`_httpx_fetch`) so it is offline-testable; the
default transport lazily imports `httpx` (the unit-034 `net` extra). No change to `web.py`,
`web_search`, the seam, or governance.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
