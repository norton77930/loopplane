"""Spec 034: opt-in, secret-gated live web_fetch check.

Excluded from the default CI gates: skipped unless ``LOOPPLANE_WEB_LIVE`` is set
in the environment AND the optional ``net`` extra (httpx) is installed. Run
manually, e.g.::

    LOOPPLANE_WEB_LIVE=1 uv run --extra net pytest tests/live/test_live_web.py
"""

from __future__ import annotations

import os

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import ErrorOutput
from loopplane.model.content import TextBlock
from loopplane.tools import WebToolAdapter

pytestmark = pytest.mark.anyio

_LIVE_URL = os.environ.get("LOOPPLANE_WEB_LIVE_URL", "https://example.com")


@pytest.mark.skipif(
    not os.environ.get("LOOPPLANE_WEB_LIVE"),
    reason="set LOOPPLANE_WEB_LIVE=1 (and the 'net' extra) to run the live check",
)
async def test_web_fetch_live_real_url(tmp_path: object) -> None:
    pytest.importorskip(
        "httpx", reason="install the 'net' extra (httpx) for the live check"
    )

    adapter = WebToolAdapter()  # real httpx-backed fetcher
    context = RunContext(session_id="live", working_scope=tmp_path)  # type: ignore[arg-type]
    outputs = [
        output
        async for output in adapter.invoke("web_fetch", {"url": _LIVE_URL}, context)
    ]

    assert outputs and not any(isinstance(o, ErrorOutput) for o in outputs)
    assert any(isinstance(o, TextBlock) and o.text for o in outputs)
