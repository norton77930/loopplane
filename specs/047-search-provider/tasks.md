# Tasks: Reference Search Provider

**Feature**: 047-search-provider | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: additive. New `src/loopplane/tools/search.py` + export + api-reference + tests.
`web.py` (the `SearchProvider`/`SearchResult` seam + `web_search`) and governance are
UNCHANGED. No new dependency (reuses the optional `net` extra, lazily); no ADR.

**Tests**: requested (TDD-friendly ordering).

## Phase 1: Foundational (blocking prerequisites)

- [ ] T001 Create `src/loopplane/tools/search.py` with the `ReferenceSearchProvider` class importing `SearchProvider`/`SearchResult` (and the `Fetcher` transport shape) from `loopplane.tools.web`; constructor `(*, endpoint=<DuckDuckGo Instant-Answer JSON URL>, api_key: str | None = None, transport: Fetcher | None = None)`; a module-level default lazy-`httpx` transport (mirroring `web._httpx_fetch`).
- [ ] T002 Export `ReferenceSearchProvider` from `src/loopplane/tools/__init__.py`.

## Phase 2: User Story 1 — web_search works without a host-written provider (P1) 🎯 MVP

**Goal**: the bundled provider returns parsed results through `web_search`.

**Independent test**: a stub transport returns canned DuckDuckGo JSON; `web_search` (via `WebToolAdapter(search_provider=ReferenceSearchProvider(transport=stub))`) returns formatted results.

- [ ] T003 [US1] Write `tests/unit/test_search_provider.py` (offline; stub async transport returning canned DuckDuckGo Instant-Answer JSON): `search()` returns parsed `SearchResult`s; through `WebToolAdapter`+`web_search` the formatted output appears; `limit` bounds the count.
- [ ] T004 [US1] Implement `ReferenceSearchProvider.search(query, *, limit)` in `src/loopplane/tools/search.py`: build the endpoint URL (`q`, `format=json`, `no_html=1`, `no_redirect=1`, plus the key if configured), call the transport (default lazy `httpx` GET), require a 2xx status, parse the JSON, map `AbstractText`/`AbstractURL` and flatten `RelatedTopics[]` (incl. nested `Topics[]`) into `SearchResult`s defensively (skip entries without a usable text/url), and return at most `limit`. Make T003 pass.

## Phase 3: User Story 2 — Configurable & credential-safe (P2)

- [ ] T005 [US2] Extend `tests/unit/test_search_provider.py`: the package imports with the `net` extra absent and the default transport's `httpx` import is lazy (a search via the default transport without the extra raises `ImportError`, which `web_search` normalizes to the existing extra-required error); an injected `api_key` never appears in results or in the normalized error; a custom `endpoint` is honored.

## Phase 4: User Story 3 — Bounded, governed, reuse-first (P3)

- [ ] T006 [US3] Extend `tests/unit/test_search_provider.py`: a transport that raises / returns non-2xx surfaces via `web_search`'s existing normalized "web search failed" error (no leak); malformed/unexpected JSON is parsed defensively (unusable entries skipped → remaining or `[]`); confirm `web.py`'s `web_search` descriptor and the `SearchProvider`/`SearchResult` seam are unchanged (reuse, not fork).

## Phase 5: Polish & Cross-Cutting

- [ ] T007 Add `ReferenceSearchProvider` to `docs/api-reference.md` (the `loopplane.tools` section) so the unit-014 api-reference bijection test stays green; mirror how the unit-034 web names are documented.
- [ ] T008 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict), `pytest` (full suite — additive proof). Fix any issue introduced by this unit.

## Dependencies

- T001, T002 → block Phase 2+.
- T003 → T004 (TDD). T004 → T005, T006. T002/T001 → T007. T007 → T008 (gates last).

## Parallel opportunities

- T005/T006 extend the same test file → sequential. T001 (module) and T003 (tests) are
  different files but T003 imports the module, so T001 first.

## Implementation strategy

- **MVP = Phase 1 + Phase 2 (US1)**: a working keyless provider returning results through
  `web_search`, with the core test set (stub transport). US2/US3 add the lazy-import /
  no-leak / fault-normalization / governance-unchanged proofs.
- All changes additive; `web.py` and governance untouched.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
