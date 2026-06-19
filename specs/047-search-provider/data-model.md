# Data Model: Reference Search Provider

No new content block or event; reuses the unit-034 `SearchResult` shape.

## ReferenceSearchProvider (new)

A concrete `SearchProvider` (unit-034 seam): `async search(query, *, limit) -> Sequence[SearchResult]`.

**Construction (host-configurable, no bundled key):**

| Param | Type | Default | Notes |
| ----- | ---- | ------- | ----- |
| `endpoint` | string | DuckDuckGo Instant-Answer JSON URL | The backend query endpoint; overridable. |
| `api_key` | `str \| None` | `None` | Injected for backends that require one; never bundled, never emitted. |
| `transport` | async `(url) -> (status, body_text)` \| `None` | `None` → lazy `httpx` GET | Injectable for offline tests (unit-034 `Fetcher` shape). |

## SearchResult (reused, unit 034)

`title`, `url`, `snippet` — produced by mapping the backend response.

## Backend response mapping (DuckDuckGo Instant-Answer JSON)

| Source field | → SearchResult |
| ------------ | -------------- |
| `AbstractText` + `AbstractURL` (when present) | a leading result (title from `Heading`, url, snippet=`AbstractText`) |
| `RelatedTopics[]` items with `Text` + `FirstURL` | one result each (title=first line of `Text`, url=`FirstURL`, snippet=`Text`) |
| nested `RelatedTopics[].Topics[]` | flattened defensively |

## Rules (from FRs)

| Rule | Source |
| ---- | ------ |
| Implements the unit-034 `SearchProvider` seam | FR-001 |
| Keyless default backend; no bundled/required key | FR-002, FR-003 |
| Endpoint/key host-configurable; key injected, never emitted | FR-003, SC-003 |
| Transport injectable; default lazy `httpx` (`net` extra) | FR-004, FR-005 |
| Parse defensively; bound to `limit` | FR-006 |
| Faults surface via the existing `web_search` normalized error (no leak) | FR-006 |
| No change to the seam / `web_search` / governance | FR-007, FR-008 |

## State transitions

None — stateless per query (no result caching in v1).
