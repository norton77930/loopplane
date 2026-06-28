"""Unit tests for the web tools (spec 034): web_fetch and web_search on the
Web Tool Adapter. All deterministic and offline — the fetch transport is a fake
injected callable and the search provider is a stub; no real network is used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import TextBlock
from loopplane.tools import SearchResult, WebToolAdapter

pytestmark = pytest.mark.anyio


def _context(tmp_path: Path, *, session_id: str = "session-1") -> RunContext:
    return RunContext(session_id=session_id, working_scope=tmp_path)


async def _invoke(
    adapter: WebToolAdapter,
    name: str,
    call_input: dict[str, object],
    context: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, context)]


class _FakeFetcher:
    """An injectable fetch transport double: records calls and returns a scripted
    (status, text) — or raises a scripted exception — so web_fetch can be tested
    fully offline."""

    def __init__(
        self,
        *,
        status: int = 200,
        text: str = "hello body",
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.text = text
        self.error = error
        self.calls: list[str] = []

    async def __call__(self, url: str) -> tuple[int, str]:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return (self.status, self.text)


class _StubProvider:
    def __init__(
        self,
        *,
        results: list[SearchResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        self.calls.append((query, limit))
        if self.error is not None:
            raise self.error
        return self.results


# --- descriptors --------------------------------------------------------------


def test_web_tools_are_network_flagged(tmp_path: Path) -> None:
    adapter = WebToolAdapter()
    by_name = {d.name: d for d in adapter.describe()}
    assert set(by_name) == {"web_fetch", "web_search"}
    assert by_name["web_fetch"].network is True
    assert by_name["web_search"].network is True
    # web_fetch reaches out (not read-only); web_search reads.
    assert by_name["web_fetch"].read_only is False
    assert by_name["web_search"].read_only is True


# --- web_fetch (US2) ----------------------------------------------------------


async def test_web_fetch_returns_body_text_and_caches(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(text="page contents")
    adapter = WebToolAdapter(fetcher=fetcher)

    (block,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert "page contents" in block.text
    assert fetcher.calls == ["https://example.com"]


async def test_web_fetch_second_call_is_served_from_cache(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(text="cached body")
    adapter = WebToolAdapter(fetcher=fetcher)
    context = _context(tmp_path)

    await _invoke(adapter, "web_fetch", {"url": "https://example.com/a"}, context)
    (block,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com/a"}, context
    )

    assert isinstance(block, TextBlock)
    assert "cached body" in block.text
    # The transport was hit exactly once: the second call is a cache hit.
    assert fetcher.calls == ["https://example.com/a"]


async def test_web_fetch_oversized_response_is_truncated(tmp_path: Path) -> None:
    body = "x" * 70_000
    fetcher = _FakeFetcher(text=body)
    adapter = WebToolAdapter(fetcher=fetcher)

    (block,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com/large"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert block.text != body
    assert len(block.text) < len(body)
    assert "truncated" in block.text.lower()


async def test_web_fetch_cache_reuses_bounded_response(tmp_path: Path) -> None:
    body = "x" * 70_000
    fetcher = _FakeFetcher(text=body)
    adapter = WebToolAdapter(fetcher=fetcher)
    context = _context(tmp_path)

    (first,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com/large"}, context
    )
    (second,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com/large"}, context
    )

    assert isinstance(first, TextBlock)
    assert isinstance(second, TextBlock)
    assert first.text == second.text
    assert len(second.text) < len(body)
    assert fetcher.calls == ["https://example.com/large"]


async def test_web_fetch_within_limit_response_is_unchanged(tmp_path: Path) -> None:
    body = "small page contents"
    fetcher = _FakeFetcher(text=body)
    adapter = WebToolAdapter(fetcher=fetcher)

    (block,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com/small"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert block.text == body


async def test_web_fetch_cache_is_per_session(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(text="body")
    adapter = WebToolAdapter(fetcher=fetcher)

    await _invoke(
        adapter,
        "web_fetch",
        {"url": "https://example.com/x"},
        _context(tmp_path, session_id="s1"),
    )
    await _invoke(
        adapter,
        "web_fetch",
        {"url": "https://example.com/x"},
        _context(tmp_path, session_id="s2"),
    )

    # A different session does not see s1's cache entry → a second fetch.
    assert fetcher.calls == ["https://example.com/x", "https://example.com/x"]


async def test_web_fetch_rejects_non_http_scheme(tmp_path: Path) -> None:
    fetcher = _FakeFetcher()
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter, "web_fetch", {"url": "file:///etc/passwd"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert fetcher.calls == []


async def test_web_fetch_rejects_malformed_url(tmp_path: Path) -> None:
    fetcher = _FakeFetcher()
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter, "web_fetch", {"url": "not a url"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert fetcher.calls == []


async def test_web_fetch_invalid_url_error_omits_query_secret(
    tmp_path: Path,
) -> None:
    fetcher = _FakeFetcher()
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter,
        "web_fetch",
        {"url": "ftp://example.com/private?token=abc123"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert "token=abc123" not in error.message
    assert "?token" not in error.message
    assert fetcher.calls == []


async def test_web_fetch_timeout_is_normalized(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(error=TimeoutError("connect timed out for secret-host"))
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    # A timeout is an execution failure, not validation.
    assert error.category == "execution"
    # The raw transport detail must not leak into the normalized message.
    assert "secret-host" not in error.message


async def test_web_fetch_timeout_error_omits_query_secret(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(error=TimeoutError("connect timed out for secret-host"))
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter,
        "web_fetch",
        {"url": "https://example.com/private?signature=abc123"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "execution"
    assert "signature=abc123" not in error.message
    assert "?signature" not in error.message
    assert "secret-host" not in error.message


async def test_web_fetch_transport_error_is_normalized(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(error=ConnectionError("connection refused token=abc123"))
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "execution"
    assert "token=abc123" not in error.message


async def test_web_fetch_transport_error_omits_query_secret(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(error=ConnectionError("low-level password=abc123"))
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter,
        "web_fetch",
        {"url": "https://example.com/down?password=abc123"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "execution"
    assert "password=abc123" not in error.message
    assert "?password" not in error.message


async def test_web_fetch_non_2xx_status_is_an_error(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(status=404, text="not found")
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com/missing"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "execution"
    assert "404" in error.message


async def test_web_fetch_non_2xx_error_omits_query_secret(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(status=403, text="forbidden")
    adapter = WebToolAdapter(fetcher=fetcher)

    (error,) = await _invoke(
        adapter,
        "web_fetch",
        {"url": "https://example.com/forbidden?api_key=abc123"},
        _context(tmp_path),
    )

    assert isinstance(error, ErrorOutput)
    assert error.category == "execution"
    assert "403" in error.message
    assert "api_key=abc123" not in error.message
    assert "?api_key" not in error.message


async def test_web_fetch_without_httpx_degrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No injected fetcher → the adapter builds the httpx-backed default; simulate
    # httpx being absent and assert a normalized error (not an ImportError crash).
    import builtins

    real_import = builtins.__import__

    def _no_httpx(name: str, *args: object, **kwargs: object) -> object:
        if name == "httpx":
            raise ImportError("No module named 'httpx'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _no_httpx)
    adapter = WebToolAdapter()  # no fetcher injected

    (error,) = await _invoke(
        adapter, "web_fetch", {"url": "https://example.com"}, _context(tmp_path)
    )

    assert isinstance(error, ErrorOutput)
    assert "net" in error.message or "httpx" in error.message


# --- web_search (US3) ---------------------------------------------------------


async def test_web_search_renders_provider_results(tmp_path: Path) -> None:
    provider = _StubProvider(
        results=[
            SearchResult(title="First", url="https://a.example", snippet="alpha"),
            SearchResult(title="Second", url="https://b.example", snippet="beta"),
        ]
    )
    adapter = WebToolAdapter(search_provider=provider)

    (block,) = await _invoke(
        adapter, "web_search", {"query": "anything"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert "First" in block.text
    assert "https://a.example" in block.text
    assert "Second" in block.text


async def test_web_search_empty_results_message(tmp_path: Path) -> None:
    provider = _StubProvider(results=[])
    adapter = WebToolAdapter(search_provider=provider)

    (block,) = await _invoke(
        adapter, "web_search", {"query": "nothing"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert not isinstance(block, ErrorOutput)
    assert "no results" in block.text.lower()


async def test_web_search_unconfigured_is_clear_error(tmp_path: Path) -> None:
    adapter = WebToolAdapter()  # no provider

    (error,) = await _invoke(adapter, "web_search", {"query": "x"}, _context(tmp_path))

    assert isinstance(error, ErrorOutput)
    assert error.category == "validation"
    assert "not configured" in error.message.lower()


async def test_web_search_provider_error_is_normalized(tmp_path: Path) -> None:
    provider = _StubProvider(error=RuntimeError("provider boom api_key=sk-secret"))
    adapter = WebToolAdapter(search_provider=provider)

    (error,) = await _invoke(adapter, "web_search", {"query": "x"}, _context(tmp_path))

    assert isinstance(error, ErrorOutput)
    assert error.category == "execution"
    assert "sk-secret" not in error.message


async def test_web_search_passes_limit_to_provider(tmp_path: Path) -> None:
    provider = _StubProvider(results=[])
    adapter = WebToolAdapter(search_provider=provider)

    await _invoke(adapter, "web_search", {"query": "q", "limit": 3}, _context(tmp_path))
    await _invoke(adapter, "web_search", {"query": "q2"}, _context(tmp_path))

    assert provider.calls == [("q", 3), ("q2", 5)]


# --- lifecycle ----------------------------------------------------------------


async def test_shutdown_clears_the_fetch_cache(tmp_path: Path) -> None:
    fetcher = _FakeFetcher(text="body")
    adapter = WebToolAdapter(fetcher=fetcher)
    context = _context(tmp_path)

    await _invoke(adapter, "web_fetch", {"url": "https://example.com"}, context)
    await adapter.shutdown()
    await _invoke(adapter, "web_fetch", {"url": "https://example.com"}, context)

    # After shutdown the cache is empty, so the URL is fetched again.
    assert fetcher.calls == ["https://example.com", "https://example.com"]
