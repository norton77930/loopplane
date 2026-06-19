"""The Web Tool Adapter and the network tool set (spec 034): web_fetch and
web_search — each reachable only through the Gateway and gated by the network-egress
policy (loopplane.governance.network).

web_fetch retrieves an http(s) URL to readable text with a small per-session
in-memory cache; web_search runs a query through a host-injected SearchProvider
(LoopPlane bundles no provider and no API key). Every failure — a bad URL, a
timeout, a transport error, a missing optional dependency, an unconfigured or
raising provider — is returned as a normalized ErrorOutput; no raw exception,
credential, header, or transport object crosses the Gateway boundary
(Constitution V, VII). httpx is an optional extra (`net`), imported lazily and only
when a fetch actually needs it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from loopplane.context import RunContext
from loopplane.errors import ErrorCategory
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.boundary import ToolDescriptor
from loopplane.model.content import TextBlock

_DEFAULT_SEARCH_LIMIT = 5
_FETCH_TIMEOUT_SECONDS = 30.0


class SearchResult(BaseModel):
    """One result from a host-supplied search provider."""

    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    snippet: str = ""


class SearchProvider:
    """The host-injected search seam (a Protocol-shaped duck type).

    A host supplies an object with this single async method; LoopPlane ships no
    implementation and no API key (the credential lives in the host's object).
    Declared as a class for a clean type reference; any object with a matching
    ``search`` coroutine satisfies it.
    """

    async def search(self, query: str, *, limit: int) -> Sequence[SearchResult]:
        raise NotImplementedError


# An injectable fetch transport: ``async (url) -> (status_code, body_text)``.
Fetcher = Callable[[str], Awaitable[tuple[int, str]]]


_DESCRIPTORS = [
    ToolDescriptor(
        name="web_fetch",
        description=(
            "Fetch an http(s) URL and return its body as readable text. Requires "
            "network egress to be enabled; a repeat fetch of the same URL in the "
            "same session is served from an in-memory cache."
        ),
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        concurrency_safe=True,
        network=True,
    ),
    ToolDescriptor(
        name="web_search",
        description=(
            "Search the web through the host-configured search provider and return "
            "ranked results as text. Requires network egress to be enabled and a "
            "search provider to be configured by the host."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        concurrency_safe=True,
        read_only=True,
        network=True,
    ),
]


async def _httpx_fetch(url: str) -> tuple[int, str]:
    """The default fetch transport, backed by the optional ``httpx`` extra.

    Imported lazily so the core install never requires ``httpx``; an absent
    dependency is raised as ImportError and normalized by the caller.
    """

    import httpx  # noqa: PLC0415 - lazy: the optional `net` extra

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=_FETCH_TIMEOUT_SECONDS
    ) as client:
        response = await client.get(url)
    return (response.status_code, response.text)


class WebToolAdapter:
    def __init__(
        self,
        *,
        search_provider: SearchProvider | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        self._search_provider = search_provider
        self._fetcher = fetcher
        # (session_id, url) -> fetched text; in-memory, per-session, ephemeral.
        self._cache: dict[tuple[str, str], str] = {}

    def describe(self) -> Sequence[ToolDescriptor]:
        return list(_DESCRIPTORS)

    async def invoke(
        self, name: str, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        handlers = {
            "web_fetch": self._web_fetch,
            "web_search": self._web_search,
        }
        async for output in handlers[name](call_input, context):
            yield output

    async def shutdown(self) -> None:
        self._cache.clear()

    async def _web_fetch(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        url = str(call_input["url"])
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(f"web_fetch only supports http(s) URLs; refused {url!r}"),
            )
            return

        key = (context.session_id, url)
        cached = self._cache.get(key)
        if cached is not None:
            yield TextBlock(text=cached)
            return

        fetcher = self._fetcher or _httpx_fetch
        try:
            status, text = await fetcher(url)
        except ImportError:
            yield ErrorOutput(
                category=ErrorCategory.EXECUTION,
                message=(
                    "web_fetch requires the optional 'net' extra (httpx); install "
                    "loopplane[net] to enable network fetches"
                ),
            )
            return
        except TimeoutError:
            yield ErrorOutput(
                category=ErrorCategory.EXECUTION,
                message=f"web_fetch timed out fetching {url}",
            )
            return
        except Exception:  # noqa: BLE001 - normalize any transport fault, no leak
            yield ErrorOutput(
                category=ErrorCategory.EXECUTION,
                message=f"web_fetch could not reach {url}",
            )
            return

        if not 200 <= status < 300:
            yield ErrorOutput(
                category=ErrorCategory.EXECUTION,
                message=f"web_fetch got HTTP {status} for {url}",
            )
            return

        self._cache[key] = text
        yield TextBlock(text=text)

    async def _web_search(
        self, call_input: dict[str, object], context: RunContext
    ) -> AsyncIterator[AdapterOutput]:
        if self._search_provider is None:
            yield ErrorOutput(
                category=ErrorCategory.VALIDATION,
                message=(
                    "web search is not configured: the host supplied no search provider"
                ),
            )
            return

        query = str(call_input["query"])
        raw_limit = call_input.get("limit", _DEFAULT_SEARCH_LIMIT)
        limit = int(raw_limit) if isinstance(raw_limit, int) else _DEFAULT_SEARCH_LIMIT
        try:
            results = await self._search_provider.search(query, limit=limit)
        except Exception:  # noqa: BLE001 - normalize any provider fault, no leak
            yield ErrorOutput(
                category=ErrorCategory.EXECUTION,
                message=f"web search failed for {query!r}",
            )
            return

        if not results:
            yield TextBlock(text=f"no results for {query!r}")
            return

        lines: list[str] = []
        for result in results:
            line = f"{result.title} — {result.url}"
            if result.snippet:
                line += f"\n    {result.snippet}"
            lines.append(line)
        yield TextBlock(text="\n".join(lines))
