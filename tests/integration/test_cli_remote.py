"""The terminal's remote client against a REAL web/API host (079 US6).

These go through `create_app` over an in-process ASGI transport, so the request
shapes, the ownership rules, and the failure statuses are the actual ones — not
a mock of them.

**What is deliberately not here.** An in-process ASGI transport cannot read an
open-ended SSE stream: it drives the app to completion and hands back the body,
so a session stream that stays open (which is exactly what a live session's
stream does) never yields a frame. Streaming, frame parsing, cursor dedup, and
reconnection are covered in `tests/unit/test_cli_remote_stream.py`, whose mock
transport reproduces the server's frame format byte for byte
(`id: <sequence>\\ndata: <event json>`), and by the manual scenario in the
feature's quickstart. What this file proves is everything else: that the client
speaks the real routes correctly and that the server's ownership and credential
rules hold through it.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import anyio  # noqa: E402
import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from loopplane.cli.remote import (  # noqa: E402
    RemoteClient,
    RemoteEndpoint,
    RemoteGone,
    RemoteUnavailable,
    remote_loop,
)
from loopplane.model import (  # noqa: E402
    TextIncrement,
    TokenUsage,
    TurnEnd,
)
from loopplane.webapi import create_app, token_authenticator  # noqa: E402
from tests.webapi_helpers import (  # noqa: E402
    build_test_host,
    multi_text_model,
    tool_then_text_model,
)

pytestmark = pytest.mark.anyio

ALICE_TOKEN = "tok-alice"
BOB_TOKEN = "tok-bob"


def _app(working_scope: Path, **host_kwargs: object) -> tuple[FastAPI, object]:
    host = build_test_host(working_scope, **host_kwargs)  # type: ignore[arg-type]
    app = create_app(
        host,
        authenticator=token_authenticator({ALICE_TOKEN: "alice", BOB_TOKEN: "bob"}),
        sse_replay_buffer=64,
    )
    return app, host


class _Lifespan:
    """Run the app's lifespan around a body — `create_app` starts its session
    task group there, so the interactive routes need it."""

    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._ctx: object | None = None

    async def __aenter__(self) -> httpx.ASGITransport:
        self._ctx = self._app.router.lifespan_context(self._app)
        await self._ctx.__aenter__()  # type: ignore[attr-defined]
        return httpx.ASGITransport(app=self._app)

    async def __aexit__(self, *exc: object) -> None:
        if self._ctx is not None:
            await self._ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]
            self._ctx = None


def _endpoint(
    token: str = ALICE_TOKEN, session_id: str | None = None
) -> RemoteEndpoint:
    return RemoteEndpoint(
        base_url="http://remote.invalid", token=token, session_id=session_id
    )


# --- the client against the real routes ---------------------------------------


async def test_open_and_submit_reach_the_real_host(tmp_path: Path) -> None:
    app, host = _app(tmp_path, model=multi_text_model("a real reply"))
    async with _Lifespan(app) as transport:
        async with RemoteClient(_endpoint(), transport=transport) as client:
            session_id = await client.open_session()
            assert session_id
            await client.submit(session_id, "hello from the terminal")
            await client.cancel(session_id)
    # The turn really ran on the server: its history holds both sides of it.
    roles = [entry.role for entry in host.history_snapshot(session_id)]  # type: ignore[attr-defined]
    assert "user" in roles and "assistant" in roles


async def test_a_remote_command_is_answered_by_the_server(tmp_path: Path) -> None:
    app, _host = _app(tmp_path, model=multi_text_model("a reply"))
    async with _Lifespan(app) as transport:
        async with RemoteClient(_endpoint(), transport=transport) as client:
            session_id = await client.open_session()
            result = await client.run_command("/cost", session_id)
            await client.cancel(session_id)
    assert result.kind == "ok"
    assert "monthly:" in result.text


async def test_answering_an_unknown_request_is_reported_not_raised(
    tmp_path: Path,
) -> None:
    app, _host = _app(tmp_path, model=tool_then_text_model())
    async with _Lifespan(app) as transport:
        async with RemoteClient(_endpoint(), transport=transport) as client:
            session_id = await client.open_session()
            # The route exists and answers; an id nobody is waiting on resolves
            # to False rather than failing.
            await client.answer_approval(
                session_id, "no-such-request", allow=True, scope="once"
            )
            await client.answer_question(session_id, "no-such-request", ["x"])
            await client.cancel(session_id)


# --- ownership and credentials ------------------------------------------------


async def test_another_principals_conversation_is_not_disclosed(
    tmp_path: Path,
) -> None:
    app, _host = _app(tmp_path, model=multi_text_model("a", "b"))
    async with _Lifespan(app) as transport:
        async with RemoteClient(_endpoint(), transport=transport) as alice:
            alice_session = await alice.open_session()

        async with RemoteClient(_endpoint(BOB_TOKEN), transport=transport) as bob:
            with pytest.raises(RemoteGone) as owned:
                await bob.submit(alice_session, "let me in")
            with pytest.raises(RemoteGone) as absent:
                await bob.submit("no-such-session", "let me in")
        # Indistinguishable: the same failure, carrying neither session's id.
        assert str(owned.value) == str(absent.value)
        assert alice_session not in str(owned.value)

        async with RemoteClient(_endpoint(), transport=transport) as alice:
            await alice.cancel(alice_session)


async def test_a_rejected_credential_never_echoes_it(tmp_path: Path) -> None:
    app, _host = _app(tmp_path, model=multi_text_model("a reply"))
    bad = "not-a-real-token"
    async with _Lifespan(app) as transport:
        async with RemoteClient(_endpoint(bad), transport=transport) as client:
            with pytest.raises(RemoteUnavailable) as failure:
                await client.open_session()
    assert bad not in str(failure.value)
    assert "rejected the credential" in str(failure.value)


# --- the loop's command path (no turn, so no stream to wait on) ---------------


async def test_the_mutating_command_is_refused_before_it_is_sent(
    tmp_path: Path,
) -> None:
    app, _host = _app(tmp_path, model=multi_text_model("a reply"))
    out = io.StringIO()
    async with _Lifespan(app) as transport:
        code = await remote_loop(
            _endpoint(), ["/compact", "quit"], out, transport=transport
        )
    assert code == 0
    assert "not available over a remote connection" in out.getvalue()


async def test_a_remote_safe_command_is_forwarded_by_the_loop(tmp_path: Path) -> None:
    app, _host = _app(tmp_path, model=multi_text_model("a reply"))
    out = io.StringIO()
    async with _Lifespan(app) as transport:
        code = await remote_loop(
            _endpoint(), ["/cost", "quit"], out, transport=transport
        )
    assert code == 0
    text = out.getvalue()
    assert "monthly:" in text
    assert ALICE_TOKEN not in text


async def test_a_slow_turn_is_not_cut_off_by_a_read_deadline(tmp_path: Path) -> None:
    """B3: `/submit` spans the whole turn server-side, so a read timeout would
    end any realistic conversation — and would blame the network for it."""

    class _SlowModel:
        def context_capacity(self) -> int:
            return 100_000

        async def stream_turn(self, request: object) -> AsyncIterator[object]:
            await anyio.sleep(0.4)  # longer than the client's other budgets
            yield TextIncrement(text="worth the wait")
            yield TurnEnd(stop_reason="end-turn", usage=TokenUsage())

    app, host = _app(tmp_path, model=_SlowModel())
    async with _Lifespan(app) as transport:
        # A tiny connect/write budget: only a READ deadline would break this.
        async with RemoteClient(_endpoint(), transport=transport, timeout=0.05) as c:
            session_id = await c.open_session()
            await c.submit(session_id, "take your time")
            await c.cancel(session_id)
    roles = [entry.role for entry in host.history_snapshot(session_id)]
    assert "assistant" in roles


async def test_the_client_leaves_reads_unbounded(tmp_path: Path) -> None:
    """Pinning the reason, so nobody restores a read timeout by tidying."""

    app, _host = _app(tmp_path, model=multi_text_model("a"))
    async with _Lifespan(app) as transport:
        async with RemoteClient(_endpoint(), transport=transport) as client:
            configured = client._require().timeout  # noqa: SLF001 - pinning intent
    assert configured.read is None
    assert configured.connect is not None


async def test_an_api_prefix_override_is_honored(tmp_path: Path) -> None:
    """`create_app` takes an `api_prefix`, so the client must not hardcode /v1."""

    host = build_test_host(tmp_path, model=multi_text_model("a"))
    app = create_app(
        host,
        authenticator=token_authenticator({ALICE_TOKEN: "alice"}),
        api_prefix="/api",
    )
    endpoint = RemoteEndpoint(
        base_url="http://remote.invalid", token=ALICE_TOKEN, api_prefix="/api"
    )
    async with _Lifespan(app) as transport:
        async with RemoteClient(endpoint, transport=transport) as client:
            session_id = await client.open_session()
            assert session_id
            await client.cancel(session_id)
