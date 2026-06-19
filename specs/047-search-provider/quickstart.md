# Quickstart / Validation: Reference Search Provider

See [contracts/search-provider.md](contracts/search-provider.md) and
[data-model.md](data-model.md).

## Run the unit tests

```powershell
pytest tests/unit/test_search_provider.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new search-provider tests. No existing behavior
changes (web_search and its seam are untouched).

## Validation scenarios (mirror the acceptance scenarios)

1. **Parse + return** — construct `ReferenceSearchProvider(transport=<stub returning canned
   DuckDuckGo JSON>)`; `await provider.search("python", limit=5)` returns parsed `SearchResult`s
   (title/url/snippet). (FR-001/006)
2. **Through `web_search`** — `WebToolAdapter(search_provider=ReferenceSearchProvider(transport=stub))`
   → `web_search` returns the formatted results in the existing output shape. (SC-001)
3. **Limit** — request `limit=2`; at most 2 results. (FR-006)
4. **No bundled key** — default construction needs no key; an injected key never appears in
   results or errors. (FR-002/003, SC-003)
5. **Lazy import** — the package imports with the `net` extra absent; the default transport's
   `httpx` import is lazy (a search without the extra → the existing normalized extra-required
   error). (FR-004, SC-002)
6. **Transport fault** — a stub transport that raises / returns non-2xx → `web_search` emits its
   existing normalized "web search failed" error (no leak). (FR-006)
7. **Malformed JSON** — a stub returning unexpected JSON → parsed defensively (unusable entries
   skipped; remaining or `[]`). (edge case)
8. **Governance unchanged** — with network egress disabled, `web_search` is denied by the
   existing network policy regardless of the provider. (FR-007)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the public-safety scan (no private paths / secrets / keys in the diff).
