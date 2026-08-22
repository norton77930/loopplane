"""Unit 084: the managed-MCP capability surface carries an authorization mode.

Before this unit the surface could express neither an authorization mode nor even
the 059 static token — `_capability_mcp.py` built `MCPServerConfig` from name,
transport, and url alone — so no UI on any surface could reach an authenticated MCP
server at all. These tests pin the two halves of closing that: the mode round-trips,
and **material never joins it**.

The second half matters more than it looks. The record these tests inspect is
persisted by `CapabilitySettingsStore` inside the LoopPlane profile root, which is
inside the backup whitelist — so anything stored here reaches an archive by
construction (ADR 0019 D8).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

import loopplane.host._capability_mcp as mcp_module
from loopplane.adapters.mcp import (
    AuthorizationResult,
    InMemoryMcpTokenStore,
    MCPServerConfig,
    StoredAuthorizationMaterial,
)
from loopplane.host import (
    CapabilityManagementConfig,
    LoopPlaneHost,
    RuntimeConfig,
    StorageConfig,
)
from loopplane.model import ScriptedModel

pytestmark = pytest.mark.anyio

SENTINEL = "sk-live-084-capability-sentinel-not-a-real-credential"


class _Handler:
    """A host handler that would authorize, if the runtime ever asked it to."""

    def __init__(self) -> None:
        self.present_calls = 0

    def redirect_uri(self, *, server: str) -> str:
        return "http://127.0.0.1:7842/callback"

    async def present(self, url: str, *, server: str, principal: str | None) -> None:
        self.present_calls += 1

    async def await_result(
        self, *, server: str, principal: str | None
    ) -> AuthorizationResult:
        return AuthorizationResult(code="code", state="state")


class _CapturingAdapter:
    """Stands in for MCPToolAdapter and records what the host handed it."""

    seen: list[dict[str, object]] = []

    def __init__(
        self,
        configs: Sequence[MCPServerConfig],
        *,
        authorization_handler: object | None = None,
        token_store: object | None = None,
        principal_id: str | None = None,
    ) -> None:
        [self.config] = configs
        type(self).seen.append(
            {
                "authorization": self.config.authorization,
                "handler": authorization_handler,
                "store": token_store,
                "principal": principal_id,
            }
        )

    @property
    def connection_failures(self) -> dict[str, str]:
        return {}

    async def connect(self) -> None:
        return None

    def describe(self) -> list[object]:
        return []

    async def shutdown(self) -> None:
        return None


def _host(tmp_path: Path, **capability: object) -> LoopPlaneHost:
    return LoopPlaneHost(
        RuntimeConfig(
            model=ScriptedModel([], context_capacity=100_000),
            storage=StorageConfig(root=tmp_path / "store"),
            capability_management=CapabilityManagementConfig(
                mutations_enabled=True,
                mcp_endpoint_policy=lambda *_a: True,
                **capability,  # type: ignore[arg-type]
            ),
        ),
        working_scope=tmp_path,
    )


async def test_mode_round_trips_and_starts_unauthorized(tmp_path: Path) -> None:
    host = _host(tmp_path)
    result = await host.upsert_managed_mcp(
        name="docs",
        transport="http",
        url="https://mcp.example.invalid",
        principal_id="alice",
        authorization="interactive",
    )
    assert result.ok

    record = host.get_managed_mcp("docs", principal_id="alice")
    assert record.authorization == "interactive"
    # Not "disconnected": the operator needs to be told which of the two it is,
    # and the runtime can say so without holding any material to check.
    assert record.status == "needs_authorization"


async def test_ordinary_server_is_unchanged(tmp_path: Path) -> None:
    host = _host(tmp_path)
    assert (
        await host.upsert_managed_mcp(
            name="plain",
            transport="http",
            url="https://mcp.example.invalid",
            principal_id="alice",
        )
    ).ok
    record = host.get_managed_mcp("plain", principal_id="alice")
    assert record.authorization is None
    assert record.status == "disconnected"


@pytest.mark.parametrize(
    ("transport", "mode"),
    [("websocket", "interactive"), ("http", "implicit"), ("sse", "device_code")],
)
async def test_unsupported_mode_or_transport_is_rejected(
    tmp_path: Path, transport: str, mode: str
) -> None:
    """websocket cannot carry auth (ADR 0007 D3); an unknown mode is a defect, not
    a value to store and puzzle over later."""
    host = _host(tmp_path)
    result = await host.upsert_managed_mcp(
        name="bad",
        transport=transport,
        url="wss://mcp.example.invalid"
        if transport == "websocket"
        else "https://mcp.example.invalid",
        principal_id="alice",
        authorization=mode,
    )
    assert not result.ok
    assert result.status == "invalid"


async def test_persisted_record_holds_the_mode_and_no_material(
    tmp_path: Path,
) -> None:
    """The whole point of D8, checked against the bytes actually written."""
    store = InMemoryMcpTokenStore()
    await store.save(
        principal="alice",
        server="docs",
        material=StoredAuthorizationMaterial(tokens=SENTINEL, client_info=SENTINEL),
    )
    host = _host(tmp_path, mcp_authorization_handler=_Handler(), mcp_token_store=store)
    assert (
        await host.upsert_managed_mcp(
            name="docs",
            transport="http",
            url="https://mcp.example.invalid",
            principal_id="alice",
            authorization="interactive",
        )
    ).ok

    written = [
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "store").rglob("*")
        if path.is_file()
    ]
    assert written, "expected the capability settings document to exist"
    blob = "\n".join(written)
    assert SENTINEL not in blob
    # The mode is there under a key the store's credential-shaped-key guard
    # accepts: "authorization" is in _FORBIDDEN_KEY_PARTS, and rightly so.
    assert "interactive" in blob
    assert '"authorization"' not in blob


async def test_seams_reach_the_adapter_only_for_an_interactive_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-016 at the call site: an ordinary server is constructed with exactly the
    arguments it was before 084, so 'default-unused is byte-identical' is a
    property of the wiring and not only of the adapter's behaviour."""
    _CapturingAdapter.seen = []
    monkeypatch.setattr(mcp_module, "MCPToolAdapter", _CapturingAdapter)
    handler = _Handler()
    store = InMemoryMcpTokenStore()
    host = _host(tmp_path, mcp_authorization_handler=handler, mcp_token_store=store)

    for name, mode in (("plain", None), ("docs", "interactive")):
        assert (
            await host.upsert_managed_mcp(
                name=name,
                transport="http",
                url="https://mcp.example.invalid",
                principal_id="alice",
                authorization=mode,
            )
        ).ok
        await host.reconnect_managed_mcp(name, principal_id="alice")

    plain, interactive = _CapturingAdapter.seen
    assert plain == {
        "authorization": None,
        "handler": None,
        "store": None,
        "principal": None,
    }
    assert interactive == {
        "authorization": "interactive",
        "handler": handler,
        "store": store,
        "principal": "alice",
    }


async def test_interactive_server_without_seams_needs_authorization(
    tmp_path: Path,
) -> None:
    """Fail closed, and say the useful thing: an interactive server that cannot
    authorize is something to authorize, not something that is broken."""
    host = _host(tmp_path)
    assert (
        await host.upsert_managed_mcp(
            name="docs",
            transport="http",
            url="https://mcp.example.invalid",
            principal_id="alice",
            authorization="interactive",
        )
    ).ok

    result = await host.reconnect_managed_mcp("docs", principal_id="alice")
    assert not result.ok
    assert result.status == "needs_authorization"
    assert result.message == "mcp needs authorization"

    record = host.get_managed_mcp("docs", principal_id="alice")
    assert record.status == "needs_authorization"
    assert record.problem == "authorization required"
