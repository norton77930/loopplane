"""Unit 084: interactive MCP authorization (ADR 0019).

Offline throughout — the MCP `ClientSession` and the transport clients are
monkeypatched, so nothing here opens a browser, binds a port, or reaches the
network. That is not merely convenient: three of this unit's requirements are
negatives, and a test that quietly needed a network would be proving nothing.

Covers config validation (mode/token mutual exclusion, transport applicability),
the adapter passing the SDK OAuth client to the http/sse transports, failing closed
with no handler, `(principal, server)` store isolation, sign-out, and the
non-leakage properties (fixed failure text, redacted reprs).
"""

from __future__ import annotations

import time
from typing import Any

import anyio
import pytest
from pydantic import ValidationError

pytest.importorskip("mcp")

from loopplane.adapters.mcp import (  # noqa: E402
    AuthorizationResult,
    InMemoryMcpTokenStore,
    McpAuthorizationError,
    MCPServerConfig,
    MCPToolAdapter,
    StoredAuthorizationMaterial,
)
from loopplane.adapters.mcp.oauth import (  # noqa: E402
    AUTHORIZATION_FAILED_MESSAGE,
    build_oauth_auth,
)

pytestmark = pytest.mark.anyio

# A token-shaped sentinel. This file is git-tracked on purpose: the repository's
# public-safety contract test enumerates through `git ls-files`, so a sentinel in an
# untracked fixture would prove nothing about that scan (units 051/082).
SENTINEL = "sk-live-084-sentinel-value-not-a-real-credential"


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
    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_a: Any) -> bool:
        return False

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> Any:
        return _Obj(tools=[_Obj(name="echo", description="", inputSchema={})])

    async def list_resources(self, cursor: Any = None) -> Any:
        raise RuntimeError("no resources")


class _RecordingHandler:
    """A host handler that records what it was asked to do."""

    def __init__(
        self,
        *,
        result: AuthorizationResult | None = None,
        uri: str = "http://127.0.0.1:7842/callback",
    ) -> None:
        self.presented: list[str] = []
        self.await_calls = 0
        self.redirect_calls = 0
        self._result = result or AuthorizationResult(code="the-code", state="the-state")
        self._uri = uri

    def redirect_uri(self, *, server: str) -> str:
        self.redirect_calls += 1
        return self._uri

    async def present(self, url: str, *, server: str, principal: str | None) -> None:
        self.presented.append(url)

    async def await_result(
        self, *, server: str, principal: str | None
    ) -> AuthorizationResult:
        self.await_calls += 1
        return self._result


def _patch(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch ClientSession + the http/sse transports; capture transport kwargs."""

    import mcp
    import mcp.client.sse as sse_mod
    import mcp.client.streamable_http as http_mod

    captured: dict[str, Any] = {}
    monkeypatch.setattr(mcp, "ClientSession", lambda read, write: _FakeSession())

    def fake_http(url: str, **kw: Any) -> Any:
        captured["http"] = kw
        return _CM((object(), object(), None))

    def fake_sse(url: str, **kw: Any) -> Any:
        captured["sse"] = kw
        return _CM((object(), object()))

    monkeypatch.setattr(http_mod, "streamablehttp_client", fake_http)
    monkeypatch.setattr(sse_mod, "sse_client", fake_sse)
    return captured


# --- T004/T005: configuration is a mode, never a credential (C3.2, C3.4) ------


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_interactive_is_valid_on_http_and_sse(transport: str) -> None:
    cfg = MCPServerConfig(
        name="x",
        transport=transport,
        url="https://host/mcp",
        authorization="interactive",
    )
    assert cfg.authorization == "interactive"
    assert cfg.auth_token is None


def test_interactive_and_static_token_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        MCPServerConfig(
            name="x",
            transport="http",
            url="https://host/mcp",
            authorization="interactive",
            auth_token=SENTINEL,
        )


def test_interactive_rejected_on_stdio() -> None:
    with pytest.raises(ValidationError, match="cannot use interactive authorization"):
        MCPServerConfig(
            name="x", transport="stdio", command="run", authorization="interactive"
        )


def test_interactive_rejected_on_websocket() -> None:
    """C3.3 — websocket carries neither headers nor auth (ADR 0007 D3), unchanged."""
    with pytest.raises(ValidationError, match="cannot use interactive authorization"):
        MCPServerConfig(
            name="x",
            transport="websocket",
            url="wss://host/ws",
            authorization="interactive",
        )


def test_invalid_entry_disables_only_itself() -> None:
    """C3.5 — reuses merge_layers' existing per-entry containment, not a new path."""
    from loopplane.adapters.mcp import merge_layers

    effective, problems = merge_layers(
        [
            {
                "bad": {
                    "transport": "websocket",
                    "url": "wss://h/ws",
                    "authorization": "interactive",
                },
                "good": {"transport": "http", "url": "https://h/mcp"},
            }
        ]
    )
    assert [cfg.name for cfg in effective] == ["good"]
    assert len(problems) == 1 and "bad" in problems[0]


def test_websocket_without_authorization_is_untouched() -> None:
    """C3.3 — the ordinary websocket path behaves exactly as before 084."""
    cfg = MCPServerConfig(name="x", transport="websocket", url="wss://host/ws")
    assert cfg.authorization is None and cfg.auth_token is None


# --- T009/T010: the adapter hands the SDK OAuth client to the transport ------


@pytest.mark.parametrize("transport", ["http", "sse"])
async def test_interactive_server_passes_auth_to_transport(
    monkeypatch: pytest.MonkeyPatch, transport: str
) -> None:
    import httpx

    captured = _patch(monkeypatch)
    handler = _RecordingHandler()
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport=transport,
                url="https://host/mcp",
                authorization="interactive",
            )
        ],
        authorization_handler=handler,
    )
    await adapter.connect()
    try:
        assert adapter.connection_failures == {}
        kwargs = captured[transport]
        assert isinstance(kwargs["auth"], httpx.Auth)
        assert "headers" not in kwargs
        # C1.4 — tools register exactly as for an unauthenticated server.
        assert [d.name for d in adapter.describe()] == ["srv:echo"]
    finally:
        await adapter.shutdown()


async def test_default_unused_is_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T058/C10.1 — no mode declared means the transport call is what it always was."""
    captured = _patch(monkeypatch)
    adapter = MCPToolAdapter(
        [MCPServerConfig(name="srv", transport="http", url="https://host/mcp")]
    )
    await adapter.connect()
    try:
        assert captured["http"] == {}
    finally:
        await adapter.shutdown()


async def test_static_token_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """C10.1 — the 059 bearer still arrives as a header and no auth is added."""
    captured = _patch(monkeypatch)
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                auth_token=SENTINEL,
            )
        ]
    )
    await adapter.connect()
    try:
        assert captured["http"] == {"headers": {"Authorization": f"Bearer {SENTINEL}"}}
        assert "auth" not in captured["http"]
    finally:
        await adapter.shutdown()


# --- T013/T015: fail closed, and alone (C5.4, C5.5) --------------------------


async def test_no_handler_means_no_connection_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch(monkeypatch)
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            )
        ]
    )
    await adapter.connect()
    try:
        # Not merely "failed to connect" — the transport was never called at all,
        # so there was no unauthenticated attempt to fail.
        assert "http" not in captured
        assert set(adapter.connection_failures) == {"srv"}
        assert adapter.describe() == []
    finally:
        await adapter.shutdown()


async def test_authorization_failure_is_contained_to_its_own_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch)
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="needs-auth",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            ),
            MCPServerConfig(name="ordinary", transport="http", url="https://other/mcp"),
        ]
    )
    await adapter.connect()
    try:
        assert set(adapter.connection_failures) == {"needs-auth"}
        assert [d.name for d in adapter.describe()] == ["ordinary:echo"]
    finally:
        await adapter.shutdown()


# --- T003: (principal, server) isolation (C4.3) ------------------------------


async def test_store_isolates_by_principal_and_by_server() -> None:
    store = InMemoryMcpTokenStore()
    mine = StoredAuthorizationMaterial(tokens="mine")
    await store.save(principal="alice", server="srv", material=mine)

    assert await store.load(principal="bob", server="srv") is None
    assert await store.load(principal="alice", server="other") is None
    assert await store.load(principal=None, server="srv") is None
    assert (await store.load(principal="alice", server="srv")) is mine


async def test_discard_is_idempotent_and_reveals_nothing() -> None:
    """C4.4 — a sign-out must not double as a probe for whether material existed."""
    store = InMemoryMcpTokenStore()
    assert await store.discard(principal="nobody", server="srv") is None
    await store.save(
        principal="alice",
        server="srv",
        material=StoredAuthorizationMaterial(tokens="t"),
    )
    await store.discard(principal="alice", server="srv")
    assert await store.load(principal="alice", server="srv") is None
    assert await store.discard(principal="alice", server="srv") is None


# --- T026: nothing leaks through repr/str (C6.3) -----------------------------


def test_material_and_result_reprs_are_redacted() -> None:
    result = AuthorizationResult(code=SENTINEL, state=SENTINEL)
    material = StoredAuthorizationMaterial(tokens=SENTINEL, client_info=SENTINEL)
    store = InMemoryMcpTokenStore()
    store._entries[("alice", "srv")] = material  # noqa: SLF001

    for text in (repr(result), str(result), repr(material), str(material), repr(store)):
        assert SENTINEL not in text
    # A traceback formats args, so the exception text matters as much as the repr.
    assert SENTINEL not in str(McpAuthorizationError(AUTHORIZATION_FAILED_MESSAGE))


async def test_authorization_failure_text_is_fixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C6.2 — the SDK interpolates compared values into its errors; we must not
    forward that. A failing handler stands in for any authorization-side fault."""

    class _Leaky:
        def redirect_uri(self, *, server: str) -> str:
            raise RuntimeError(f"boom {SENTINEL}")

        async def present(
            self, url: str, *, server: str, principal: str | None
        ) -> None:
            return None

        async def await_result(
            self, *, server: str, principal: str | None
        ) -> AuthorizationResult:
            raise AssertionError("not reached")

    _patch(monkeypatch)
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            )
        ],
        authorization_handler=_Leaky(),
    )
    await adapter.connect()
    try:
        failure = adapter.connection_failures["srv"]
        assert failure == AUTHORIZATION_FAILED_MESSAGE
        assert SENTINEL not in failure
    finally:
        await adapter.shutdown()


# --- T027: authorization is not a tool (C7) ----------------------------------


async def test_authorization_is_not_reachable_by_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch)
    handler = _RecordingHandler()
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            )
        ],
        authorization_handler=handler,
    )
    await adapter.connect()
    try:
        names = [d.name for d in adapter.describe()]
        assert names == ["srv:echo"]
        assert not any(
            token in name.lower()
            for name in names
            for token in ("auth", "oauth", "token", "login")
        )
    finally:
        await adapter.shutdown()


# --- build_oauth_auth: the host owns the redirect uri ------------------------


async def test_build_requires_a_redirect_uri_from_the_host() -> None:
    class _NoUri(_RecordingHandler):
        def redirect_uri(self, *, server: str) -> str:
            return "   "

    with pytest.raises(McpAuthorizationError, match="no redirect uri"):
        await build_oauth_auth(
            server_url="https://host/mcp",
            server_name="srv",
            principal=None,
            handler=_NoUri(),
            store=InMemoryMcpTokenStore(),
        )


async def test_build_rejects_an_unusable_redirect_uri() -> None:
    with pytest.raises(McpAuthorizationError, match="invalid redirect uri"):
        await build_oauth_auth(
            server_url="https://host/mcp",
            server_name="srv",
            principal=None,
            handler=_RecordingHandler(uri="not a uri at all"),
            store=InMemoryMcpTokenStore(),
        )


async def test_store_bridge_round_trips_through_the_host_store() -> None:
    """The SDK's TokenStorage is keyless; the (principal, server) pair is bound at
    construction, so two servers under one principal must not collide."""
    from loopplane.adapters.mcp.oauth import _StoreBridge  # noqa: SLF001

    store = InMemoryMcpTokenStore()
    one = _StoreBridge(store, principal="alice", server="one")
    two = _StoreBridge(store, principal="alice", server="two")

    await one.set_tokens("token-one")
    await one.set_client_info("client-one")

    assert await one.get_tokens() == "token-one"
    assert await one.get_client_info() == "client-one"
    assert await two.get_tokens() is None
    assert await two.get_client_info() is None


async def test_connect_uses_the_host_store_not_a_fresh_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host-supplied store must actually be the one the flow reads and writes."""

    class _CountingStore(InMemoryMcpTokenStore):
        def __init__(self) -> None:
            super().__init__()
            self.loads = 0

        async def load(
            self, *, principal: str | None, server: str
        ) -> StoredAuthorizationMaterial | None:
            self.loads += 1
            return await super().load(principal=principal, server=server)

    _patch(monkeypatch)
    store = _CountingStore()
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            )
        ],
        authorization_handler=_RecordingHandler(),
        token_store=store,
        principal_id="alice",
    )
    await adapter.connect()
    try:
        auth = (
            await adapter._transport_auth_kwargs(  # noqa: SLF001
                MCPServerConfig(
                    name="srv",
                    transport="http",
                    url="https://host/mcp",
                    authorization="interactive",
                )
            )
        )["auth"]
        assert await auth.context.storage.get_tokens() is None
        assert store.loads > 0
    finally:
        await adapter.shutdown()


async def test_state_and_code_reach_the_sdk_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The boundary captures the SDK-generated state from the presented URL and
    returns a matching host result without exposing either value."""
    handler = _RecordingHandler(result=AuthorizationResult(code="abc", state="xyz"))
    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal="alice",
        handler=handler,
        store=InMemoryMcpTokenStore(),
    )
    await auth.context.redirect_handler("https://idp/authorize?state=xyz")
    assert handler.presented == ["https://idp/authorize?state=xyz"]
    assert await auth.context.callback_handler() == ("abc", "xyz")
    assert handler.await_calls == 1


async def test_state_mismatch_is_consumed_without_echoing_transient_values() -> None:
    expected = "expected-state-must-not-reach-logs"
    returned = "returned-state-must-not-reach-logs"
    handler = _RecordingHandler(result=AuthorizationResult(code="abc", state=returned))
    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal="alice",
        handler=handler,
        store=InMemoryMcpTokenStore(),
    )
    await auth.context.redirect_handler(f"https://idp/authorize?state={expected}")

    with pytest.raises(McpAuthorizationError) as caught:
        await auth.context.callback_handler()

    message = str(caught.value)
    assert message == AUTHORIZATION_FAILED_MESSAGE
    assert expected not in message and returned not in message
    with pytest.raises(McpAuthorizationError, match=AUTHORIZATION_FAILED_MESSAGE):
        await auth.context.callback_handler()
    assert handler.await_calls == 1


async def test_token_endpoint_failure_does_not_echo_remote_body() -> None:
    import httpx

    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal="alice",
        handler=_RecordingHandler(),
        store=InMemoryMcpTokenStore(),
    )
    request = httpx.Request("POST", "https://host/token")

    with pytest.raises(McpAuthorizationError) as caught:
        await auth._handle_token_response(  # noqa: SLF001
            httpx.Response(400, request=request, text=f"invalid {SENTINEL}")
        )

    assert str(caught.value) == AUTHORIZATION_FAILED_MESSAGE
    assert SENTINEL not in str(caught.value)


# --- T016/T018: renewal never needs a person (C5.1) --------------------------
#
# These drive the SDK's real `async_auth_flow`, because that is where the decision
# actually lives (oauth2.py:500): a valid token short-circuits, an expired-but-
# refreshable one takes the refresh branch, and only the remaining case reaches
# `_perform_authorization` — the one path that calls the host handler. Asserting on
# our own wrapper instead would prove nothing about which branch the SDK takes.


def _authorized_store(
    *, access: str, refresh: str | None, expires_in: int | None
) -> tuple[InMemoryMcpTokenStore, Any]:
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

    store = InMemoryMcpTokenStore()
    token = OAuthToken(
        access_token=access, refresh_token=refresh, expires_in=expires_in
    )
    client = OAuthClientInformationFull(
        client_id="client-084",
        redirect_uris=["http://127.0.0.1:7842/callback"],  # type: ignore[list-item]
    )
    return store, (token, client)


async def _seed(store: InMemoryMcpTokenStore, seeded: Any) -> None:
    token, client = seeded
    await store.save(
        principal="alice",
        server="srv",
        material=StoredAuthorizationMaterial(tokens=token, client_info=client),
    )


async def test_valid_token_never_invokes_the_authorization_handler() -> None:
    import httpx

    handler = _RecordingHandler()
    store, seeded = _authorized_store(access=SENTINEL, refresh="r", expires_in=3600)
    await _seed(store, seeded)
    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal="alice",
        handler=handler,
        store=store,
    )

    request = httpx.Request("POST", "https://host/mcp")
    flow = auth.async_auth_flow(request)
    sent = await flow.__anext__()
    with pytest.raises(StopAsyncIteration):
        await flow.asend(httpx.Response(200, request=sent))

    assert handler.await_calls == 0
    assert handler.presented == []
    assert sent.headers["Authorization"] == f"Bearer {SENTINEL}"


async def test_expired_material_refreshes_instead_of_prompting_after_a_restart() -> (
    None
):
    """The regression this unit's own implementation had to fix.

    The SDK restores tokens and client info from storage but not the expiry, so a
    restarted process would treat long-dead material as valid, send it, take a 401,
    and run a **full re-authorization** — a browser prompt in a job that has no
    person attached. Persisting the absolute expiry and restoring it is what makes
    the refresh branch reachable across a restart (FR-008, C5.1).
    """
    import httpx

    handler = _RecordingHandler()
    store, seeded = _authorized_store(
        access="stale", refresh="refresh-084", expires_in=3600
    )
    await _seed(store, seeded)
    # Simulate the restart: material persisted an hour ago, now past its expiry.
    material = await store.load(principal="alice", server="srv")
    assert material is not None
    material.expires_at = time.time() - 1

    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal="alice",
        handler=handler,
        store=store,
    )

    flow = auth.async_auth_flow(httpx.Request("POST", "https://host/mcp"))
    first = await flow.__anext__()
    await flow.aclose()

    assert handler.await_calls == 0, "renewal must not ask a person"
    assert handler.presented == []
    # The first thing on the wire is the token endpoint, not the resource request.
    assert b"refresh_token" in first.content


async def test_set_tokens_records_the_absolute_expiry() -> None:
    """Without this the restore above has nothing to restore."""
    from mcp.shared.auth import OAuthToken

    from loopplane.adapters.mcp.oauth import _StoreBridge  # noqa: SLF001

    store = InMemoryMcpTokenStore()
    bridge = _StoreBridge(store, principal="alice", server="srv")
    before = time.time()
    await bridge.set_tokens(OAuthToken(access_token="a", expires_in=3600))

    material = await store.load(principal="alice", server="srv")
    assert material is not None and material.expires_at is not None
    assert before + 3500 <= material.expires_at <= time.time() + 3600


async def test_unknown_expiry_stays_unknown() -> None:
    """A server that does not say when a token expires must not get a guess."""
    from mcp.shared.auth import OAuthToken

    from loopplane.adapters.mcp.oauth import _StoreBridge  # noqa: SLF001

    store = InMemoryMcpTokenStore()
    await _StoreBridge(store, principal="alice", server="srv").set_tokens(
        OAuthToken(access_token="a")
    )
    material = await store.load(principal="alice", server="srv")
    assert material is not None and material.expires_at is None


async def test_flow_writes_nothing_to_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """T022/C4.2 — the behavioural half of the static guard.

    The static scan proves no write *call* exists; this proves the flow, run for
    real against an empty directory, leaves it empty. Either alone is weaker: a
    scan can miss an indirect path, and an observation can miss a branch not taken.
    """
    _patch(monkeypatch)
    monkeypatch.chdir(tmp_path)
    store = InMemoryMcpTokenStore()
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            )
        ],
        authorization_handler=_RecordingHandler(),
        token_store=store,
        principal_id="alice",
    )
    await adapter.connect()
    try:
        await store.save(
            principal="alice",
            server="srv",
            material=StoredAuthorizationMaterial(tokens=SENTINEL),
        )
        assert list(tmp_path.iterdir()) == []
    finally:
        await adapter.shutdown()
    assert list(tmp_path.iterdir()) == []


def _sweep_surfaces(adapter: MCPToolAdapter, store: InMemoryMcpTokenStore) -> list[str]:
    """Every string surface a caller could plausibly read or log."""

    return [
        repr(adapter),
        str(adapter),
        repr(store),
        str(store),
        repr(adapter.connection_failures),
        repr(adapter.fallback_schemas),
        repr(
            [
                (d.name, d.description, d.input_schema, d.source)
                for d in adapter.describe()
            ]
        ),
    ]


async def test_no_surface_echoes_stored_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T024/C6.1 — one authorized server, then sweep everything readable."""
    _patch(monkeypatch)
    store = InMemoryMcpTokenStore()
    await store.save(
        principal="alice",
        server="srv",
        material=StoredAuthorizationMaterial(tokens=SENTINEL, client_info=SENTINEL),
    )
    adapter = MCPToolAdapter(
        [
            MCPServerConfig(
                name="srv",
                transport="http",
                url="https://host/mcp",
                authorization="interactive",
            )
        ],
        authorization_handler=_RecordingHandler(),
        token_store=store,
        principal_id="alice",
    )
    await adapter.connect()
    try:
        for text in _sweep_surfaces(adapter, store):
            assert SENTINEL not in text
    finally:
        await adapter.shutdown()


async def test_the_leak_sweep_actually_catches_a_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T060 — the negative self-check for the sweep above.

    The sweep's failure mode is matching nothing: if `_sweep_surfaces` collected the
    wrong objects it would pass forever. Plant the sentinel into one of the surfaces
    it collects and confirm it is seen.
    """
    _patch(monkeypatch)
    store = InMemoryMcpTokenStore()
    adapter = MCPToolAdapter(
        [MCPServerConfig(name="srv", transport="http", url="https://host/mcp")]
    )
    await adapter.connect()
    try:
        adapter._failures["planted"] = f"leaked {SENTINEL}"  # noqa: SLF001
        assert any(SENTINEL in text for text in _sweep_surfaces(adapter, store))
    finally:
        await adapter.shutdown()


# --- review remediation: three defects the four green gates did not see --------


def test_config_repr_and_errors_do_not_echo_the_token() -> None:
    """F2, corrected by measurement.

    A review reported that the new mutual-exclusion rule printed the live bearer,
    because pydantic interpolates the rejected input and `merge_layers` forwards
    the exception string. Isolating the two settings showed that half is wrong:
    pydantic emits `input_value=` for the **offending field only**, and no error is
    raised on `auth_token` itself, so neither path ever carried the token.

    The real leak was simpler and older — `repr(config)` printed it, and had since
    059. Both are pinned here: the repr assertion is the one that goes red when the
    fix is removed, and the error assertions are a regression guard against a
    pydantic behaviour change.
    """
    from loopplane.adapters.mcp import merge_layers

    with pytest.raises(ValidationError) as caught:
        MCPServerConfig(
            name="x",
            transport="http",
            url="https://host/mcp",
            authorization="interactive",
            auth_token=SENTINEL,
        )
    assert SENTINEL not in str(caught.value)

    _effective, problems = merge_layers(
        [
            {
                "bad": {
                    "transport": "http",
                    "url": "https://host/mcp",
                    "authorization": "interactive",
                    "auth_token": SENTINEL,
                }
            }
        ]
    )
    assert problems and all(SENTINEL not in problem for problem in problems)

    # The leak that was actually there, and is actually closed.
    cfg = MCPServerConfig(
        name="x", transport="http", url="https://host/mcp", auth_token=SENTINEL
    )
    assert SENTINEL not in repr(cfg)
    assert SENTINEL not in str(cfg)
    assert cfg.auth_token == SENTINEL  # still readable by the transport


async def test_failed_renewal_fails_closed_without_prompting() -> None:
    """F3 — the SDK, on a failed refresh, clears the tokens, sends the request
    **unauthenticated**, and drives a full interactive flow off the 401. C5.3
    forbids the first and C5.2 forbids the second: an unattended job must surface
    "needs authorization", not block on a handler nobody is watching.
    """
    import httpx

    handler = _RecordingHandler()
    store, seeded = _authorized_store(
        access="stale", refresh="refresh-084", expires_in=3600
    )
    await _seed(store, seeded)
    material = await store.load(principal="alice", server="srv")
    assert material is not None
    material.expires_at = time.time() - 1

    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal="alice",
        handler=handler,
        store=store,
    )

    flow = auth.async_auth_flow(httpx.Request("POST", "https://host/mcp"))
    refresh_request = await flow.__anext__()
    assert b"refresh_token" in refresh_request.content

    # The authorization server rejects the refresh token (revoked / expired).
    with pytest.raises(McpAuthorizationError):
        await flow.asend(
            httpx.Response(
                400, request=refresh_request, json={"error": "invalid_grant"}
            )
        )

    # Neither forbidden thing happened: no unauthenticated resource request was
    # yielded, and no person was asked.
    assert handler.await_calls == 0
    assert handler.presented == []
    assert await store.load(principal="alice", server="srv") is None
    await flow.aclose()


def test_the_sdk_refresh_hook_still_exists() -> None:
    """The fail-closed override hangs off an SDK method. If a future SDK renames
    it, the override silently stops applying and the unsafe path returns — so pin
    the seam rather than trusting it."""
    from mcp.client.auth import OAuthClientProvider

    assert callable(getattr(OAuthClientProvider, "_handle_refresh_response", None))


async def test_waiting_for_a_person_is_bounded() -> None:
    """F1 — the SDK accepts a `timeout` and never enforces it (it is stored on the
    context and read by nothing), and the sse flow fires at transport context
    entry, outside the adapter's connect budget. A handler that never resolves
    would hang `connect()` forever. The bound belongs on the one await that waits
    for a person.
    """

    class _NeverAnswers(_RecordingHandler):
        async def await_result(
            self, *, server: str, principal: str | None
        ) -> AuthorizationResult:
            await anyio.sleep_forever()
            raise AssertionError("unreachable")

    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal=None,
        handler=_NeverAnswers(),
        store=InMemoryMcpTokenStore(),
        timeout=0.05,
    )
    await auth.context.redirect_handler("https://idp/authorize?state=waiting")
    with pytest.raises(McpAuthorizationError, match=AUTHORIZATION_FAILED_MESSAGE):
        await auth.context.callback_handler()


def test_interactive_connect_budget_exceeds_the_human_bound() -> None:
    """F1's other half: the OAuth flow fires inside `initialize()` on http, which
    the adapter wraps in its connect timeout. A 15s budget for a person to open a
    browser, log in, and consent is not a budget — and being cut short discards
    the pending state and verifier, so the retry starts over."""
    from loopplane.adapters.mcp.adapter import (
        _AUTHORIZATION_CONNECT_TIMEOUT_SECONDS,
        _CONNECT_TIMEOUT_SECONDS,
    )
    from loopplane.adapters.mcp.oauth import DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS

    assert _CONNECT_TIMEOUT_SECONDS < DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS
    assert (
        _AUTHORIZATION_CONNECT_TIMEOUT_SECONDS > DEFAULT_AUTHORIZATION_TIMEOUT_SECONDS
    )


async def test_empty_code_fails_before_the_token_endpoint() -> None:
    auth = await build_oauth_auth(
        server_url="https://host/mcp",
        server_name="srv",
        principal=None,
        handler=_RecordingHandler(result=AuthorizationResult(code="", state="xyz")),
        store=InMemoryMcpTokenStore(),
    )
    await auth.context.redirect_handler("https://idp/authorize?state=xyz")
    with pytest.raises(McpAuthorizationError, match=AUTHORIZATION_FAILED_MESSAGE):
        await auth.context.callback_handler()
