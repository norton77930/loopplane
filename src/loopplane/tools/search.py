"""A reference SearchProvider for the web_search tool (spec 047).

Ships a concrete, host-injectable implementation of the unit-034 ``SearchProvider``
seam so ``web_search`` works out of the box. The default backend is the keyless
DuckDuckGo Instant-Answer JSON API; LoopPlane bundles no API key (Constitution VII).
HTTP access is an injectable async transport (the unit-034 ``Fetcher`` shape), so the
provider is fully offline-testable; the default transport lazily imports ``httpx``
(the optional ``net`` extra), so this module imports without the extra installed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.parse import urlencode

from loopplane.tools.web import Fetcher, SearchProvider, SearchResult

_DUCKDUCKGO_ENDPOINT = "https://api.duckduckgo.com/"
_SEARCH_TIMEOUT_SECONDS = 30.0


async def _httpx_get(url: str) -> tuple[int, str]:
    """The default transport: a lazy ``httpx`` GET (the optional ``net`` extra).

    Imported lazily so this module imports without ``httpx``; an absent dependency
    raises ImportError, normalized by the ``web_search`` caller.
    """

    import httpx  # noqa: PLC0415 - lazy: the optional `net` extra

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=_SEARCH_TIMEOUT_SECONDS
    ) as client:
        response = await client.get(url)
    return (response.status_code, response.text)


class ReferenceSearchProvider(SearchProvider):
    """A concrete ``SearchProvider`` (unit 034) backed by a keyless web-search backend.

    Defaults to the DuckDuckGo Instant-Answer JSON API (no API key). The ``endpoint``
    and an optional ``api_key`` are host-configurable; an injected key (for a keyed
    backend) is sent as a query parameter and never appears in results. The
    ``transport`` is injectable for offline tests (default: the lazy ``httpx`` GET).
    """

    def __init__(
        self,
        *,
        endpoint: str = _DUCKDUCKGO_ENDPOINT,
        api_key: str | None = None,
        transport: Fetcher | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._transport = transport or _httpx_get

    async def search(self, query: str, *, limit: int) -> Sequence[SearchResult]:
        params = {"q": query, "format": "json", "no_html": "1", "no_redirect": "1"}
        if self._api_key is not None:
            params["api_key"] = self._api_key
        url = f"{self._endpoint}?{urlencode(params)}"
        status, body = await self._transport(url)
        if not 200 <= status < 300:
            raise RuntimeError(f"search backend returned HTTP {status}")
        payload = json.loads(body)
        results = self._parse(payload)
        return results[: max(0, limit)]

    @staticmethod
    def _parse(payload: object) -> list[SearchResult]:
        out: list[SearchResult] = []
        if not isinstance(payload, dict):
            return out
        abstract = payload.get("AbstractText")
        abstract_url = payload.get("AbstractURL")
        if (
            isinstance(abstract, str)
            and abstract
            and isinstance(abstract_url, str)
            and abstract_url
        ):
            heading = payload.get("Heading")
            title = heading if isinstance(heading, str) and heading else abstract
            out.append(SearchResult(title=title, url=abstract_url, snippet=abstract))
        related = payload.get("RelatedTopics")
        if isinstance(related, list):
            ReferenceSearchProvider._collect_topics(related, out)
        return out

    @staticmethod
    def _collect_topics(topics: list[object], out: list[SearchResult]) -> None:
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            nested = topic.get("Topics")
            if isinstance(nested, list):
                ReferenceSearchProvider._collect_topics(nested, out)
                continue
            text = topic.get("Text")
            url = topic.get("FirstURL")
            if isinstance(text, str) and text and isinstance(url, str) and url:
                title = text.split(" - ")[0].strip() or text
                out.append(SearchResult(title=title, url=url, snippet=text))
