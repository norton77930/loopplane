"""Unit 059: MCP resources + host-token auth.

Offline — the MCP `ClientSession` and the transport clients are monkeypatched, so
no process/network is used. Covers: resources surfaced as Gateway-routed synthetic
tools ({server}:list_resources / :read_resource) returning existing
TextBlock/ImageBlock; the config auth_token -> Authorization header on http/sse; a
resource-less server registers no resource tools (contained); the token is never
echoed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

from loopplane.adapters.mcp import MCPServerConfig, MCPToolAdapter  # noqa: E402
from loopplane.context import RunContext  # noqa: E402
from loopplane.errors import ErrorCategory  # noqa: E402
from loopplane.gateway.spi import ErrorOutput  # noqa: E402
from loopplane.model.content import ImageBlock, TextBlock  # noqa: E402

pytestmark = pytest.mark.anyio


class _CM:
    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *_a: Any) -> bool:
        return False


class _Obj:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class _FakeSession:
    def __init__(
        self,
        *,
        tools: tuple[Any, ...] = (),
        resources: list[Any] | None = None,
        read_contents: list[Any] | None = None,
        supports_resources: bool = True,
        call_error: Exception | None = None,
        read_error: Exception | None = None,
    ) -> None:
        self._tools = tools
        self._resources = resources or []
        self._read_contents = read_contents or []
        self._supports = supports_resources
        self._call_error = call_error
        self._read_error = read_error
        self.tool_calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_a: Any) -> bool:
        return False

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> Any:
        return _Obj(tools=list(self._tools))

    async def list_resources(self, cursor: Any = None) -> Any:
        if not self._supports:
            raise RuntimeError("resources not supported")
        return _Obj(resources=list(self._resources))

    async def read_resource(self, uri: Any) -> Any:
        if self._read_error is not None:
            raise self._read_error
        return _Obj(contents=list(self._read_contents))

    async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        self.tool_calls.append((name, args))
        if self._call_error is not None:
            raise self._call_error
        return _Obj(content=[_Obj(text="tool-ok")], isError=False)


def _patch(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> dict[str, Any]:
    """Patch ClientSession + the stdio/http/sse transports; capture transport kwargs."""

    import mcp
    import mcp.client.sse as sse_mod
    import mcp.client.stdio as stdio_mod
    import mcp.client.streamable_http as http_mod

    captured: dict[str, Any] = {}
    monkeypatch.setattr(mcp, "ClientSession", lambda read, write: session)
    monkeypatch.setattr(
        stdio_mod, "stdio_client", lambda params: _CM((object(), object()))
    )

    def fake_http(url: str, **kw: Any) -> Any:
        captured["http"] = kw
        return _CM((object(), object(), None))

    def fake_sse(url: str, **kw: Any) -> Any:
        captured["sse"] = kw
        return _CM((object(), object()))

    monkeypatch.setattr(http_mod, "streamablehttp_client", fake_http)
    monkeypatch.setattr(sse_mod, "sse_client", fake_sse)
    return captured


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(session_id="s", working_scope=tmp_path)


async def _collect(adapter: MCPToolAdapter, name: str, inp: dict, tmp_path: Path):
    return [out async for out in adapter.invoke(name, inp, _ctx(tmp_path))]


async def test_resources_registered_and_readable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(
        tools=(_Obj(name="echo", description="", inputSchema={"type": "object"}),),
        resources=[_Obj(uri="res://a", name="A", description="alpha")],
        read_contents=[
            _Obj(text="hello", uri="res://a", mimeType="text/plain"),
            _Obj(blob="ZGF0YQ==", uri="res://img", mimeType="image/png"),
        ],
    )
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="stdio", command="x")
    async with MCPToolAdapter([cfg]) as adapter:
        names = {d.name for d in adapter.describe()}
        assert "srv:list_resources" in names
        assert "srv:read_resource" in names
        assert "srv:echo" in names  # the real tool is still there
        listed = await _collect(adapter, "srv:list_resources", {}, tmp_path)
        assert len(listed) == 1 and isinstance(listed[0], TextBlock)
        assert "res://a" in listed[0].text
        read = await _collect(
            adapter, "srv:read_resource", {"uri": "res://a"}, tmp_path
        )
        assert any(isinstance(b, TextBlock) and b.text == "hello" for b in read)
        assert any(isinstance(b, ImageBlock) and b.format == "image/png" for b in read)


async def test_read_resource_requires_uri(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(resources=[_Obj(uri="res://a", name="", description="")])
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="stdio", command="x")
    async with MCPToolAdapter([cfg]) as adapter:
        out = await _collect(adapter, "srv:read_resource", {}, tmp_path)
        assert len(out) == 1 and isinstance(out[0], ErrorOutput)


async def test_resourceless_server_registers_no_resource_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(
        tools=(_Obj(name="echo", description="", inputSchema={"type": "object"}),),
        supports_resources=False,
    )
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="stdio", command="x")
    async with MCPToolAdapter([cfg]) as adapter:
        names = {d.name for d in adapter.describe()}
        assert "srv:list_resources" not in names
        assert "srv:read_resource" not in names
        assert "srv:echo" in names  # the real tool still works
        out = await _collect(adapter, "srv:echo", {}, tmp_path)
        assert any(isinstance(b, TextBlock) and b.text == "tool-ok" for b in out)


async def test_real_tool_name_collision_does_not_double_register(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A server exposing a real tool literally named read_resource must NOT produce a
    # duplicate srv:read_resource descriptor (a duplicate would crash the gateway
    # build, defeating per-server isolation, FR-043). The real tool wins;
    # list_resources (no clash) still registers.
    session = _FakeSession(
        tools=(
            _Obj(name="read_resource", description="", inputSchema={"type": "object"}),
        ),
        resources=[_Obj(uri="res://a", name="A", description="d")],
    )
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="stdio", command="x")
    async with MCPToolAdapter([cfg]) as adapter:
        names = [d.name for d in adapter.describe()]
        assert names.count("srv:read_resource") == 1  # no duplicate (the real tool)
        assert "srv:list_resources" in names  # the non-clashing resource tool
        # the real read_resource still dispatches via call_tool, not the resource path
        out = await _collect(adapter, "srv:read_resource", {}, tmp_path)
        assert any(isinstance(b, TextBlock) and b.text == "tool-ok" for b in out)


async def test_auth_token_sets_http_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(supports_resources=False)
    captured = _patch(monkeypatch, session)
    cfg = MCPServerConfig(
        name="srv", transport="http", url="https://x/mcp", auth_token="tok-123"
    )
    async with MCPToolAdapter([cfg]):
        pass
    assert captured["http"]["headers"] == {"Authorization": "Bearer tok-123"}


async def test_no_token_sends_no_headers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(supports_resources=False)
    captured = _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="sse", url="https://x/sse")
    async with MCPToolAdapter([cfg]):
        pass
    assert "headers" not in captured.get("sse", {})


async def test_token_never_echoed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(
        resources=[_Obj(uri="res://a", name="A", description="d")],
        read_contents=[_Obj(text="body", uri="res://a", mimeType="text/plain")],
    )
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(
        name="srv", transport="sse", url="https://x/sse", auth_token="SEKRIT"
    )
    async with MCPToolAdapter([cfg]) as adapter:
        listed = await _collect(adapter, "srv:list_resources", {}, tmp_path)
        read = await _collect(
            adapter, "srv:read_resource", {"uri": "res://a"}, tmp_path
        )
    blob = "".join(getattr(b, "text", "") for b in [*listed, *read])
    assert "SEKRIT" not in blob


async def test_call_tool_exception_is_public_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(
        tools=(_Obj(name="echo", description="", inputSchema={"type": "object"}),),
        supports_resources=False,
        call_error=RuntimeError("token=abc123"),
    )
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="stdio", command="x")
    async with MCPToolAdapter([cfg]) as adapter:
        (error,) = await _collect(adapter, "srv:echo", {}, tmp_path)

    assert isinstance(error, ErrorOutput)
    assert error.category == ErrorCategory.ADAPTER_FAULT
    assert error.message == "external server call failed"
    assert "RuntimeError" not in error.message
    assert "token=abc123" not in error.message


async def test_read_resource_exception_is_public_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _FakeSession(
        resources=[_Obj(uri="res://a", name="A", description="d")],
        read_error=RuntimeError("password=abc123"),
    )
    _patch(monkeypatch, session)
    cfg = MCPServerConfig(name="srv", transport="stdio", command="x")
    async with MCPToolAdapter([cfg]) as adapter:
        (error,) = await _collect(
            adapter, "srv:read_resource", {"uri": "res://a"}, tmp_path
        )

    assert isinstance(error, ErrorOutput)
    assert error.category == ErrorCategory.ADAPTER_FAULT
    assert error.message == "external server resource call failed"
    assert "RuntimeError" not in error.message
    assert "password=abc123" not in error.message
