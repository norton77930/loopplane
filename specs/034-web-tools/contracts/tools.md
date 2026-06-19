# Contracts: Web Tools (Web Tool Adapter) + Network-Egress Policy

The "interface" this unit exposes is two model-facing NETWORK tools, surfaced
through the Tool Gateway as `ToolDescriptor`s (with `network=True`) and invoked
via `WebToolAdapter.invoke(name, call_input, context)`; a host-injected
`SearchProvider` seam; an additive `ToolDescriptor.network` flag; and a
`network_policy` decide-stage decider composed through the existing combinators.
All errors are returned as `ErrorOutput` (never raised across the gateway
boundary), and no credential / header / raw transport object appears in any
message (Constitution V, VII).

## `web_fetch`

**Description**: Fetch an `http(s)` URL and return its body as readable text.
Requires network egress to be enabled (else denied at the decide stage). A repeat
fetch of the same URL in the same session is served from an in-memory cache.

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "url": {"type": "string"}
  },
  "required": ["url"],
  "additionalProperties": false
}
```

**Behaviour contract**

| Condition | Result |
|-----------|--------|
| reachable `http(s)` URL, first fetch | `TextBlock` with the body text; cache `(session_id, url)` |
| same URL already fetched this session | `TextBlock` from cache; **no** second network call |
| non-`http(s)` scheme (`file://`, `ftp://`, …) or malformed URL | `ErrorOutput(VALIDATION)`; no fetch |
| timeout | `ErrorOutput(EXECUTION)` ("timed out"); no leaked internals |
| connection / transport error | `ErrorOutput(EXECUTION)`; no leaked internals |
| non-success HTTP status (4xx/5xx) | `ErrorOutput(EXECUTION)` with the status code |
| `httpx` not installed | `ErrorOutput(EXECUTION)` naming the optional `net` extra |

**Flags**: `network=True`, `read_only=False`, `concurrency_safe=True`.

## `web_search`

**Description**: Run a query through the host-injected search provider and return
ranked results as readable text. Requires network egress to be enabled.

**Input schema**

```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string"},
    "limit": {"type": "integer"}
  },
  "required": ["query"],
  "additionalProperties": false
}
```

**Behaviour contract**

| Condition | Result |
|-----------|--------|
| provider configured, results returned | `TextBlock` of `title — url` (+ snippet) lines |
| provider configured, no results | `TextBlock` with an explicit "no results" message |
| no provider configured | `ErrorOutput(VALIDATION)` ("web search is not configured") |
| provider raises | `ErrorOutput(EXECUTION)`; no leaked internals |

**Flags**: `network=True`, `read_only=True`, `concurrency_safe=True`.

## `SearchProvider` (host-injected seam)

```python
class SearchProvider(Protocol):
    async def search(self, query: str, *, limit: int) -> Sequence[SearchResult]: ...


class SearchResult(BaseModel):   # frozen
    title: str
    url: str
    snippet: str = ""
```

- LoopPlane ships **no** provider and **no** API key; the host supplies an instance
  to `WebToolAdapter(search_provider=...)`. The host owns the credential (VII).

## `network_policy` (decide-stage decider)

```python
def network_policy(*, allow_network: bool) -> PolicyDecider: ...
```

| Condition | Verdict |
|-----------|---------|
| `descriptor.network is True` and not `allow_network` | **deny** ("network egress is disabled") |
| `descriptor.network is True` and `allow_network` | allow |
| `descriptor.network is False` | allow (never denied here) |

**Composition** (in `host/assembly.py::_build_decider`): combined with the existing
approval decider via the existing combinators —
`safe_failure(all_of(<approval?>, network_policy))` — so the chain is **deny-wins**
(`all_of`) and **fail-closed** (`safe_failure`). When network egress is the
harmless default *and* no approval/skills/network tool is present, the builder still
returns `None` (the existing allow-all posture is unchanged for non-network runs).

## `RuntimeConfig.allow_network` (host opt-in)

- `allow_network: bool = False` — an additive, public-safe flag enabling network
  egress. It carries **no secret** (the search credential lives in the host-supplied
  provider object, never in the config).

## Invariants (all)

- Both web tools are reachable **only** through the Tool Gateway (Constitution V); no bypass path.
- Network egress defaults **off**; a network tool is denied at the decide stage unless the host opts in.
- Every failure is an `ErrorOutput` / normalized error — no raw exception, credential, header, or transport object crosses the boundary (V, VII).
- `httpx` is optional and imported lazily; its absence is a normalized error, not a crash.
- The output union remains `TextBlock | ImageBlock | ErrorOutput` (unchanged); every existing tool, descriptor, and policy is unchanged (back-compat).
