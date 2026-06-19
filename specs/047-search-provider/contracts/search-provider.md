# Contract: Reference Search Provider

## `ReferenceSearchProvider` (implements the unit-034 `SearchProvider` seam)

```python
class ReferenceSearchProvider:
    def __init__(
        self,
        *,
        endpoint: str = <DuckDuckGo Instant-Answer JSON URL>,
        api_key: str | None = None,
        transport: Callable[[str], Awaitable[tuple[int, str]]] | None = None,
    ) -> None: ...

    async def search(self, query: str, *, limit: int) -> Sequence[SearchResult]: ...
```

- Satisfies the existing `loopplane.tools.web.SearchProvider` duck type.
- `transport` defaults to a lazily-imported `httpx` GET (the unit-034 `net` extra); inject a
  stub for offline tests.
- Exported from `loopplane.tools` and documented in `docs/api-reference.md`.

## Behavior

| Case | Result |
| ---- | ------ |
| Query with results (default keyless backend) | Up to `limit` `SearchResult`s parsed from the backend JSON. |
| Query with no usable results | `[]` (→ `web_search` emits its existing "no results" text). |
| Network extra absent (default transport) | `search()` raises `ImportError` → `web_search` normalizes (existing "requires the optional 'net' extra"). |
| Transport timeout / error / non-2xx | raises → `web_search` emits its existing normalized "web search failed" error (no leak). |
| Malformed/unexpected backend JSON | parsed defensively; unusable entries skipped; remaining returned (or `[]`). |
| Keyed backend configured without a key | a clear error (raised → normalized); no bundled key. |

## Usage (host opt-in)

```python
from loopplane.tools import ReferenceSearchProvider
from loopplane.tools.web import WebToolAdapter

adapter = WebToolAdapter(search_provider=ReferenceSearchProvider())
# ... plus enabling network egress (RuntimeConfig.allow_network), unchanged unit 034.
```

## Invariants

- `web_search`, the `SearchProvider`/`SearchResult` seam, the network policy, the event schema,
  and the content model are UNCHANGED (additive; VI, X).
- No API key is bundled; an injected key never appears in any result or error (VII).
- The package imports without the `net` extra (lazy import); a real search needs it.
- Reachable only behind `web_search` (network-gated; V).
