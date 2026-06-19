"""Reference search provider tests (spec 047). Deterministic and offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import TextBlock
from loopplane.tools import ReferenceSearchProvider
from loopplane.tools.web import SearchProvider, WebToolAdapter

pytestmark = pytest.mark.anyio


_CANNED = {
    "Heading": "Python",
    "AbstractText": "Python is a programming language.",
    "AbstractURL": "https://en.wikipedia.org/wiki/Python",
    "RelatedTopics": [
        {
            "Text": "Python (programming) - a language",
            "FirstURL": "https://py.example/1",
        },
        {"Topics": [{"Text": "Monty Python", "FirstURL": "https://py.example/2"}]},
        {"NoUsableFields": "skipped"},
    ],
}


def _ok(body: str):
    async def _t(url: str) -> tuple[int, str]:
        return (200, body)

    return _t


def _status(code: int):
    async def _t(url: str) -> tuple[int, str]:
        return (code, "")

    return _t


def _context(tmp_path: Path) -> RunContext:
    return RunContext(session_id="s", working_scope=tmp_path)


async def _invoke(
    adapter: WebToolAdapter,
    name: str,
    call_input: dict[str, object],
    context: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, context)]


# --- US1: search works --------------------------------------------------------


async def test_search_parses_abstract_and_related() -> None:
    provider = ReferenceSearchProvider(transport=_ok(json.dumps(_CANNED)))

    results = await provider.search("python", limit=5)

    urls = [r.url for r in results]
    assert "https://en.wikipedia.org/wiki/Python" in urls  # abstract
    assert "https://py.example/1" in urls  # related topic
    assert "https://py.example/2" in urls  # nested topic
    assert all(r.title and r.url for r in results)


async def test_web_search_through_reference_provider(tmp_path: Path) -> None:
    adapter = WebToolAdapter(
        search_provider=ReferenceSearchProvider(transport=_ok(json.dumps(_CANNED)))
    )

    (block,) = await _invoke(
        adapter, "web_search", {"query": "python"}, _context(tmp_path)
    )

    assert isinstance(block, TextBlock)
    assert "https://py.example/1" in block.text


async def test_limit_bounds_results() -> None:
    provider = ReferenceSearchProvider(transport=_ok(json.dumps(_CANNED)))

    results = await provider.search("python", limit=2)

    assert len(results) == 2


# --- US2: configurable & credential-safe --------------------------------------


async def test_default_transport_is_the_lazy_httpx_get() -> None:
    import loopplane.tools.search as search_mod

    provider = search_mod.ReferenceSearchProvider()

    # The default transport is the lazy-httpx GET; httpx is imported only inside it,
    # so importing this module needs no `net` extra.
    assert provider._transport is search_mod._httpx_get  # noqa: SLF001


async def test_api_key_is_not_leaked_on_failure(tmp_path: Path) -> None:
    fake_key = "do-not-leak-token"

    async def _raise(url: str) -> tuple[int, str]:
        raise RuntimeError(f"connection failed to {url}")  # the url carries the key

    adapter = WebToolAdapter(
        search_provider=ReferenceSearchProvider(api_key=fake_key, transport=_raise)
    )

    (out,) = await _invoke(adapter, "web_search", {"query": "q"}, _context(tmp_path))

    assert isinstance(out, ErrorOutput)
    assert fake_key not in out.message


async def test_custom_endpoint_is_honored() -> None:
    sink: list[str] = []

    async def _capture(url: str) -> tuple[int, str]:
        sink.append(url)
        return (200, json.dumps(_CANNED))

    provider = ReferenceSearchProvider(
        endpoint="https://custom.example/s", transport=_capture
    )
    await provider.search("q", limit=1)

    assert sink and sink[0].startswith("https://custom.example/s?")


# --- US3: bounded, governed, reuse-first --------------------------------------


async def test_non_2xx_surfaces_normalized_error(tmp_path: Path) -> None:
    adapter = WebToolAdapter(
        search_provider=ReferenceSearchProvider(transport=_status(500))
    )

    (out,) = await _invoke(adapter, "web_search", {"query": "q"}, _context(tmp_path))

    assert isinstance(out, ErrorOutput)


async def test_unexpected_json_is_parsed_defensively(tmp_path: Path) -> None:
    # Valid JSON but not the expected shape -> no usable results -> the existing
    # "no results" text (not a crash).
    adapter = WebToolAdapter(
        search_provider=ReferenceSearchProvider(transport=_ok("{}"))
    )

    (block,) = await _invoke(adapter, "web_search", {"query": "q"}, _context(tmp_path))

    assert isinstance(block, TextBlock)
    assert "no results" in block.text.lower()


async def test_provider_satisfies_the_seam() -> None:
    assert isinstance(ReferenceSearchProvider(), SearchProvider)
