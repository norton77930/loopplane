"""Unit 057: MCP SSE + WebSocket transports.

Covers the additive transport extension: config validation (sse/websocket require a
url, mirroring http; stdio/http unchanged) and `_connect_one` dispatch to the MCP SDK's
sse_client / websocket_client. Offline — the SDK transport client is monkeypatched, so
no network connection is made.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

import pytest
from pydantic import ValidationError

from loopplane.adapters.mcp import MCPServerConfig, MCPToolAdapter

pytestmark = pytest.mark.anyio


# --- config validation (FR-001 / FR-002) -----------------------------------


@pytest.mark.parametrize("transport", ["sse", "websocket"])
def test_sse_websocket_are_valid_with_a_url(transport: str) -> None:
    cfg = MCPServerConfig(name="x", transport=transport, url="https://host/mcp")
    assert cfg.transport == transport
    assert cfg.url == "https://host/mcp"


@pytest.mark.parametrize("transport", ["sse", "websocket"])
def test_sse_websocket_require_a_url(transport: str) -> None:
    with pytest.raises(ValidationError, match="requires a url"):
        MCPServerConfig(name="x", transport=transport)


def test_existing_transports_unchanged() -> None:
    with pytest.raises(ValidationError, match="stdio transport requires a command"):
        MCPServerConfig(name="x", transport="stdio")
    with pytest.raises(ValidationError, match="http transport requires a url"):
        MCPServerConfig(name="x", transport="http")
    assert (
        MCPServerConfig(name="x", transport="http", url="https://host").transport
        == "http"
    )


# --- _connect_one dispatch (FR-003): the right SDK client per transport -----


class _Sentinel(Exception):
    """Raised by the stubbed transport on enter to prove the branch was taken."""


def _raising_client(*_args: Any, **_kwargs: Any) -> Any:
    class _CM:
        async def __aenter__(self) -> Any:
            raise _Sentinel

        async def __aexit__(self, *_a: Any) -> bool:
            return False

    return _CM()


async def test_sse_branch_uses_sse_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp.client.sse as sse_mod

    seen: dict[str, Any] = {}

    def fake(url: str, *_a: Any, **_k: Any) -> Any:
        seen["url"] = url
        return _raising_client()

    monkeypatch.setattr(sse_mod, "sse_client", fake)
    adapter = MCPToolAdapter([])
    cfg = MCPServerConfig(name="x", transport="sse", url="https://host/sse")
    async with AsyncExitStack() as stack:
        with pytest.raises(_Sentinel):
            await adapter._connect_one(cfg, stack)  # noqa: SLF001
    assert seen["url"] == "https://host/sse"


async def test_websocket_branch_uses_websocket_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mcp.client.websocket as ws_mod

    seen: dict[str, Any] = {}

    def fake(url: str, *_a: Any, **_k: Any) -> Any:
        seen["url"] = url
        return _raising_client()

    monkeypatch.setattr(ws_mod, "websocket_client", fake)
    adapter = MCPToolAdapter([])
    cfg = MCPServerConfig(name="x", transport="websocket", url="wss://host/ws")
    async with AsyncExitStack() as stack:
        with pytest.raises(_Sentinel):
            await adapter._connect_one(cfg, stack)  # noqa: SLF001
    assert seen["url"] == "wss://host/ws"
