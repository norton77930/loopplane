# Phase 1 Data Model: Web Tools

This feature introduces no persisted entities. It adds one Web Tool Adapter (two
tool descriptors + handlers), one host-injected provider seam, one additive
`ToolDescriptor` field, one additive `RuntimeConfig` flag, and one decide-stage
policy. The "model" here is those shapes plus the in-memory adapter state.

## New / changed types

### `ToolDescriptor.network` (additive field — `src/loopplane/model/boundary.py`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `network` | `bool` | `False` | The tool requires network egress; the `network_policy` gates on it. |

All existing fields (`name`, `description`, `input_schema`, `concurrency_safe`,
`read_only`, `source`) are unchanged. Every existing descriptor keeps `network=False`.

### `SearchResult` (frozen pydantic model — `src/loopplane/tools/web.py`)

| Field | Type | Meaning |
|-------|------|---------|
| `title` | `str` | Result title. |
| `url` | `str` | Result URL. |
| `snippet` | `str` | Short text snippet (default `""`). |

### `SearchProvider` (Protocol — `src/loopplane/tools/web.py`)

```python
class SearchProvider(Protocol):
    async def search(self, query: str, *, limit: int) -> Sequence[SearchResult]: ...
```

Host-supplied; LoopPlane ships none. The host owns any credential.

### `Fetcher` (internal injectable seam — `src/loopplane/tools/web.py`)

```python
Fetcher = Callable[[str], Awaitable[FetchResponse]]   # async (url) -> (status, text)
```

An internal constructor kwarg for deterministic tests; defaults to an
`httpx`-backed implementation built lazily when first needed.

### `RuntimeConfig.allow_network` (additive field — `src/loopplane/host/config.py`)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `allow_network` | `bool` | `False` | Opt-in network egress; drives `network_policy`. Carries **no secret**. |

## New tool descriptors (`ToolDescriptor`)

| Tool | `network` | `read_only` | `concurrency_safe` | Inputs (required) |
|------|-----------|-------------|--------------------|-------------------|
| `web_fetch` | `True` | `False` | `True` | `url` |
| `web_search` | `True` | `True` | `True` | `query` (opt: `limit`) |

> `web_fetch` is **not** `read_only`: it reaches the network (a side-effecting
> action for governance clarity), though it mutates no working-scope state. Both
> tools are `concurrency_safe` (independent reads of the network).

### `web_fetch` input schema

- `url` (string, required) — the `http(s)` URL to fetch.

### `web_search` input schema

- `query` (string, required) — the search query.
- `limit` (integer, optional, default 5) — maximum number of results.

## Adapter state (`WebToolAdapter`)

- **Per-session fetch cache** — `_cache: dict[tuple[str, str], str]` keyed by
  `(session_id, url)` → fetched text. Populated by `web_fetch`; a hit short-circuits
  the network. Cleared on `shutdown()`. Never persisted, never cross-session.
- **Injected provider** — `_search_provider: SearchProvider | None` (default `None`).
- **Injected fetcher** — `_fetcher: Fetcher | None` (default `None` → lazy `httpx`).

## Output shapes (`AdapterOutput` — unchanged union)

- **Success** → `TextBlock(text=...)`:
  - `web_fetch`: the response body as decoded text (cache hit or fresh fetch).
  - `web_search`: rendered results — one `title — url` + snippet line per result, or
    an explicit "no results" message when empty.
- **Validation failure** → `ErrorOutput(category=ErrorCategory.VALIDATION, message=...)`:
  non-`http(s)`/malformed URL; `web_search` with no provider configured.
- **Execution / I-O failure** → `ErrorOutput(category=ErrorCategory.EXECUTION, message=...)`:
  timeout; connection/transport error; non-success HTTP status; `httpx` not installed;
  a raising search provider. The message carries **no** credential/header/raw
  transport object.

## Policy: `network_policy` (decide-stage — `src/loopplane/governance/network.py`)

```python
def network_policy(*, allow_network: bool) -> PolicyDecider: ...
```

| Condition | Verdict |
|-----------|---------|
| `descriptor.network` is `True` and `allow_network` is `False` | **deny** ("network egress is disabled") |
| `descriptor.network` is `True` and `allow_network` is `True` | allow |
| `descriptor.network` is `False` (any tool) | allow (never denied by this policy) |

Composed in `_build_decider` as `safe_failure(all_of(approval?, network_policy))`:
**deny-wins** (any deny short-circuits) and **fail-closed** (a raised policy → deny).

## Validation rules (from requirements)

- FR-002: `web_fetch` rejects non-`http(s)`/malformed URLs as `VALIDATION` before any fetch.
- FR-004/FR-007: timeout / transport / non-2xx / missing httpx / provider error → normalized `ErrorOutput`, never a raise across the boundary; no secret in the message.
- FR-006: `web_search` with no provider → `VALIDATION` "not configured".
- FR-008: `network` defaults to `False`; only the two web tools set it.
- FR-009/FR-010/FR-011: `network_policy` denies network tools unless `allow_network`, composed deny-wins + fail-closed through the existing combinators; egress defaults off.
- FR-012: `httpx` optional + lazily imported; absent → normalized error.
