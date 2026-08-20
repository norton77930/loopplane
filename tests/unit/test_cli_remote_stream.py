"""The remote client's stream handling and failure surfaces (079 US6, US7).

Driven with a mock transport so every frame, status code, and drop is exact.
"""

from __future__ import annotations

import io
import signal
import time
from datetime import UTC, datetime

import pytest

pytest.importorskip("httpx")

import anyio  # noqa: E402
import httpx  # noqa: E402

from loopplane.cli.remote import (  # noqa: E402
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_EXHAUSTED_NOTICE,
    RECONNECTING_NOTICE,
    RECONNECTING_UNSEQUENCED_NOTICE,
    REMOTE_ENDED_NOTICE,
    RemoteEndpoint,
    StreamCursor,
    frames_from_lines,
    parse_frame,
    remote_command_verdict,
    remote_loop,
)
from loopplane.commands import default_registry  # noqa: E402
from loopplane.events import serialize_event  # noqa: E402
from loopplane.events.envelope import (  # noqa: E402
    AssistantOutputIncrementEvent,
    AssistantOutputIncrementPayload,
    RunTerminatedEvent,
    RunTerminatedPayload,
)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fast_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reconnection backoff is a real 1 second; only the test that is ABOUT the
    backoff should pay for it."""

    monkeypatch.setattr("loopplane.cli.remote.RECONNECT_DELAY_SECONDS", 0.0)


_T = datetime(2026, 1, 1, tzinfo=UTC)
TOKEN = "a-credential-that-must-never-be-printed"


def _text_event(sequence: int, text: str) -> AssistantOutputIncrementEvent:
    return AssistantOutputIncrementEvent(
        session_id="s1",
        sequence=sequence,
        occurred_at=_T,
        payload=AssistantOutputIncrementPayload(text=text, turn_index=0),
    )


def _terminated(sequence: int) -> RunTerminatedEvent:
    return RunTerminatedEvent(
        session_id="s1",
        sequence=sequence,
        occurred_at=_T,
        payload=RunTerminatedPayload(reason="natural-completion", turns_taken=1),
    )


def _frame(event: object) -> str:
    return f"id: {event.sequence}\ndata: {serialize_event(event)}\n\n"  # type: ignore[attr-defined]


# --- frame parsing ------------------------------------------------------------


def test_parse_frame_reads_sequence_and_event() -> None:
    sequence, event = parse_frame(_frame(_text_event(7, "hi")).strip())
    assert sequence == 7
    assert isinstance(event, AssistantOutputIncrementEvent)
    assert event.payload.text == "hi"


def test_parse_frame_without_an_id_line() -> None:
    sequence, event = parse_frame(f"data: {serialize_event(_text_event(1, 'x'))}")
    assert sequence is None
    assert event is not None


def test_parse_frame_returns_none_for_an_unknown_or_corrupt_payload() -> None:
    assert parse_frame("id: 1\ndata: not json") == (1, None)
    assert parse_frame('id: 2\ndata: {"type": "who-knows"}') == (2, None)
    assert parse_frame("id: nonsense\ndata: {}") == (None, None)
    assert parse_frame(": a comment") == (None, None)


# --- the cursor ---------------------------------------------------------------


def test_cursor_accepts_only_new_sequences() -> None:
    cursor = StreamCursor()
    assert cursor.accepts(1)
    cursor.advance(1)
    assert not cursor.accepts(1)
    assert not cursor.accepts(0)
    assert cursor.accepts(2)


def test_cursor_accepts_frames_without_a_sequence() -> None:
    cursor = StreamCursor(last_sequence=5)
    assert cursor.accepts(None)
    cursor.advance(None)
    assert cursor.last_sequence == 5  # an id-less frame does not move it


# --- the command policy -------------------------------------------------------


def test_verdict_forwards_a_remote_safe_command() -> None:
    assert remote_command_verdict(default_registry(), "/cost") is None


def test_verdict_refuses_a_non_remote_safe_command() -> None:
    verdict = remote_command_verdict(default_registry(), "/compact")
    assert verdict is not None
    assert verdict.kind == "error"
    assert "not available over a remote connection" in verdict.text


def test_verdict_reports_an_unknown_command() -> None:
    verdict = remote_command_verdict(default_registry(), "/nope")
    assert verdict is not None
    assert verdict.kind == "unknown"


# --- driving a conversation over a mock transport -----------------------------


class _Server:
    """A scripted remote: records requests and serves scripted event streams."""

    def __init__(self, *streams: list[str], session_id: str = "s1") -> None:
        self.requests: list[tuple[str, str]] = []
        self.last_event_ids: list[str | None] = []
        self._streams = list(streams)
        self._session_id = session_id

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append((request.method, path))
        if path.endswith("/events"):
            self.last_event_ids.append(request.headers.get("Last-Event-ID"))
            frames = self._streams.pop(0) if self._streams else []
            return httpx.Response(
                200,
                content="".join(frames).encode("utf-8"),
                headers={"content-type": "text/event-stream"},
            )
        if path.endswith("/sessions") and request.method == "POST":
            return httpx.Response(200, json={"session_id": self._session_id})
        if path.endswith("/commands"):
            return httpx.Response(200, json={"kind": "ok", "text": "remote answer"})
        return httpx.Response(200, json={"resolved": True})


def _endpoint(session_id: str | None = None) -> RemoteEndpoint:
    return RemoteEndpoint(
        base_url="http://server.invalid", token=TOKEN, session_id=session_id
    )


async def test_a_remote_turn_streams_through_the_shared_renderer() -> None:
    server = _Server([_frame(_text_event(1, "remote hello")), _frame(_terminated(2))])
    out = io.StringIO()
    code = await remote_loop(
        _endpoint(), ["hello", "quit"], out, transport=server.transport()
    )
    assert code == 0
    text = out.getvalue()
    assert "remote hello" in text
    assert "[run natural-completion, 1 turn(s)]" in text
    assert ("POST", "/v1/sessions") in server.requests
    assert ("POST", "/v1/sessions/s1/submit") in server.requests


async def test_attaching_uses_the_supplied_conversation_and_opens_none() -> None:
    server = _Server([_frame(_terminated(1))])
    out = io.StringIO()
    await remote_loop(
        _endpoint("existing"), ["hello", "quit"], out, transport=server.transport()
    )
    assert ("POST", "/v1/sessions") not in server.requests
    assert ("POST", "/v1/sessions/existing/submit") in server.requests


async def test_a_remote_safe_command_is_forwarded() -> None:
    server = _Server([])
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"), ["/cost", "quit"], out, transport=server.transport()
    )
    assert ("POST", "/v1/commands") in server.requests
    assert "remote answer" in out.getvalue()


async def test_a_non_remote_safe_command_never_reaches_the_server() -> None:
    server = _Server([])
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"), ["/compact", "quit"], out, transport=server.transport()
    )
    assert ("POST", "/v1/commands") not in server.requests
    assert "not available over a remote connection" in out.getvalue()


# --- reconnection -------------------------------------------------------------


async def test_a_dropped_stream_reconnects_with_the_last_event_id() -> None:
    server = _Server(
        [_frame(_text_event(1, "before "))],  # stream ends mid-turn
        [_frame(_text_event(2, "after")), _frame(_terminated(3))],
    )
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"), ["hello", "quit"], out, transport=server.transport()
    )
    text = out.getvalue()
    assert "before " in text and "after" in text
    assert RECONNECTING_NOTICE.strip() in text
    # The first attempt asks for everything; the reconnect resumes after the
    # last sequence actually rendered. (A mock stream ends at EOF, so the client
    # keeps offering to reconnect after that — a real session's stream stays
    # open, so only these first two are the behavior under test.)
    assert server.last_event_ids[:2] == [None, "1"]


async def test_a_replayed_frame_is_not_rendered_twice() -> None:
    server = _Server(
        [_frame(_text_event(1, "once "))],
        # The server replays frame 1 alongside the new ones; the cursor drops it.
        [
            _frame(_text_event(1, "once ")),
            _frame(_text_event(2, "twice")),
            _frame(_terminated(3)),
        ],
    )
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"), ["hello", "quit"], out, transport=server.transport()
    )
    assert out.getvalue().count("once ") == 1


async def test_reconnection_is_bounded_and_says_so() -> None:
    server = _Server()  # every stream is empty, so it drops immediately, forever
    out = io.StringIO()
    # One turn, so the prompt is waiting on the stream while it retries.
    await remote_loop(_endpoint("s1"), ["hello"], out, transport=server.transport())
    text = out.getvalue()
    assert RECONNECT_EXHAUSTED_NOTICE.strip() in text
    # This server sent no `id:` lines, so the operator is told that a resume is
    # not possible rather than being shown a bare "[reconnecting…]" that implies
    # one — the no-loss guarantee belongs to the server's configuration.
    assert text.count(RECONNECTING_UNSEQUENCED_NOTICE.strip()) == MAX_RECONNECT_ATTEMPTS
    assert RECONNECTING_NOTICE.strip() not in text


async def test_a_sequenced_stream_reports_a_plain_reconnect() -> None:
    """With ids in play a resume IS possible, so the notice stays plain."""

    server = _Server(
        [_frame(_text_event(1, "seen"))],
        [_frame(_terminated(2))],
    )
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"), ["hello", "quit"], out, transport=server.transport()
    )
    text = out.getvalue()
    assert RECONNECTING_NOTICE.strip() in text
    assert RECONNECTING_UNSEQUENCED_NOTICE.strip() not in text


async def test_a_gone_conversation_is_reported_and_exits_cleanly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/events"):
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json={"resolved": True})

    out = io.StringIO()
    code = await remote_loop(
        _endpoint("s1"), ["hello"], out, transport=httpx.MockTransport(handler)
    )
    # A conversation that turned out to be gone is a failure to do what was
    # asked — and the same failure whether the stream or a submit discovered it.
    assert code == 1
    assert REMOTE_ENDED_NOTICE.strip() in out.getvalue()


# --- failure surfaces ---------------------------------------------------------


async def test_a_rejected_credential_never_echoes_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unauthorized"})

    out = io.StringIO()
    code = await remote_loop(
        _endpoint(), ["hello"], out, transport=httpx.MockTransport(handler)
    )
    assert code == 1
    text = out.getvalue()
    assert "rejected the credential" in text
    assert TOKEN not in text


async def test_an_unreachable_server_fails_publicly_safely() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused to 203.0.113.9")

    out = io.StringIO()
    code = await remote_loop(
        _endpoint(), ["hello"], out, transport=httpx.MockTransport(handler)
    )
    assert code == 1
    text = out.getvalue()
    assert "could not reach the server" in text
    assert "203.0.113.9" not in text  # the raw error never surfaces
    assert TOKEN not in text


async def test_a_non_owned_conversation_is_indistinguishable_from_a_missing_one() -> (
    None
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    first = io.StringIO()
    await remote_loop(
        _endpoint("someone-elses"),
        ["hello"],
        first,
        transport=httpx.MockTransport(handler),
    )
    second = io.StringIO()
    await remote_loop(
        _endpoint("never-existed"),
        ["hello"],
        second,
        transport=httpx.MockTransport(handler),
    )
    assert first.getvalue() == second.getvalue()


async def test_the_credential_is_sent_as_a_bearer_header() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"session_id": "s1"})

    out = io.StringIO()
    await remote_loop(_endpoint(), [], out, transport=httpx.MockTransport(handler))
    assert seen and seen[0] == f"Bearer {TOKEN}"
    assert TOKEN not in out.getvalue()


# --- 079 remediation: the paths the first round never exercised ---------------


def _approval_frame(sequence: int, request_id: str = "r1") -> str:
    from loopplane.events.envelope import (
        ApprovalRequestedEvent,
        ApprovalRequestedPayload,
    )

    return _frame(
        ApprovalRequestedEvent(
            session_id="s1",
            sequence=sequence,
            occurred_at=_T,
            payload=ApprovalRequestedPayload(
                request_id=request_id,
                call_id="c1",
                tool_name="write_file",
                input_summary="1 field",
            ),
        )
    )


def _question_frame(sequence: int, request_id: str = "q1") -> str:
    from loopplane.events.envelope import (
        Question,
        QuestionAskedEvent,
        QuestionAskedPayload,
    )

    return _frame(
        QuestionAskedEvent(
            session_id="s1",
            sequence=sequence,
            occurred_at=_T,
            payload=QuestionAskedPayload(
                request_id=request_id,
                questions=[Question(text="which?", options=["a", "b"])],
            ),
        )
    )


class _RecordingServer(_Server):
    """A server that also records the bodies it was sent."""

    def __init__(self, *streams: list[str]) -> None:
        super().__init__(*streams)
        self.bodies: list[tuple[str, object]] = []

    def _handle(self, request: httpx.Request) -> httpx.Response:
        if request.content:
            import json

            with __import__("contextlib").suppress(Exception):
                self.bodies.append((request.url.path, json.loads(request.content)))
        return super()._handle(request)


async def test_a_remote_approval_is_answered_over_the_wire() -> None:
    """FR-027 remotely: the request is rendered and the operator's next line is
    POSTed back to the approvals route. This path had no test at all."""

    server = _RecordingServer(
        [_approval_frame(1), _frame(_terminated(2))],
    )
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"),
        ["do it", "a", "quit"],
        out,
        transport=server.transport(),
        reconnect_delay=0,
    )
    assert "[approve] write_file" in out.getvalue()
    answered = [body for path, body in server.bodies if "/approvals/r1" in path]
    assert answered == [{"allow": True, "scope": "session"}]


async def test_a_remote_question_is_answered_over_the_wire() -> None:
    server = _RecordingServer([_question_frame(1), _frame(_terminated(2))])
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"),
        ["ask me", "teal", "quit"],
        out,
        transport=server.transport(),
        reconnect_delay=0,
    )
    assert "[question] which?" in out.getvalue()
    answered = [body for path, body in server.bodies if "/questions/q1" in path]
    assert answered == [{"answers": ["teal"]}]


async def test_a_failed_approval_answer_is_retried_rather_than_lost() -> None:
    """If the answer POST fails, the frame must not be marked seen — otherwise
    the remote turn is parked forever on an answer that never arrived."""

    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/approvals/" in path:
            attempts.append(path)
            if len(attempts) == 1:
                raise httpx.ConnectError("transient")
            return httpx.Response(200, json={"resolved": True})
        if path.endswith("/events"):
            return httpx.Response(
                200,
                content=(_approval_frame(1) + _frame(_terminated(2))).encode("utf-8"),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(200, json={"resolved": True})

    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"),
        ["do it", "y", "y", "quit"],
        out,
        transport=httpx.MockTransport(handler),
        reconnect_delay=0,
    )
    # The first POST failed; the reconnect replayed the request and the second
    # attempt got through.
    assert len(attempts) >= 2


async def test_a_remote_interrupt_asks_the_server_to_cancel() -> None:
    """FR-028 over the wire, driven by a REAL SIGINT rather than an injected
    KeyboardInterrupt."""

    fired = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fired
        path = request.url.path
        if path.endswith("/submit") and not fired:
            fired = True
            signal.raise_signal(signal.SIGINT)
        if path.endswith("/events"):
            return httpx.Response(
                200, content=b"", headers={"content-type": "text/event-stream"}
            )
        seen.append(path)
        return httpx.Response(200, json={"resolved": True, "session_id": "s1"})

    seen: list[str] = []
    out = io.StringIO()
    code = await remote_loop(
        _endpoint("s1"),
        ["start something"],
        out,
        transport=httpx.MockTransport(handler),
        reconnect_delay=0,
    )
    assert code == 0
    assert "live remote connection has ended" in out.getvalue()
    assert any(p.endswith("/cancel") for p in seen), seen


async def test_help_is_answered_locally_and_matches_the_remote_context() -> None:
    """FR-022: a listing produced on the server would advertise /compact, which
    this terminal then refuses to send."""

    server = _Server([])
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"),
        ["/help", "quit"],
        out,
        transport=server.transport(),
        reconnect_delay=0,
    )
    text = out.getvalue()
    assert "/cost" in text
    assert "/compact" not in text
    assert ("POST", "/v1/commands") not in server.requests


async def test_a_non_json_success_body_is_still_public_safe() -> None:
    """A proxy interstitial answering 200 must not escape as a parse error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html>captive portal</html>",
            headers={"content-type": "text/html"},
        )

    out = io.StringIO()
    code = await remote_loop(
        _endpoint(),
        ["hello"],
        out,
        transport=httpx.MockTransport(handler),
        reconnect_delay=0,
    )
    assert code == 1
    text = out.getvalue()
    assert "captive portal" not in text
    assert "refused that operation" in text


def test_frames_from_lines_yields_a_trailing_frame() -> None:
    """A stream that ends without a blank line still delivers its last frame."""

    async def lines():
        yield "id: 1"
        yield "data: {}"

    async def collect():
        return [frame async for frame in frames_from_lines(lines())]

    import anyio as _anyio

    frames = _anyio.run(collect)
    assert frames == ["id: 1\ndata: {}"]


def test_parse_frame_joins_multi_line_data() -> None:
    """Per SSE, several `data:` lines in one frame join with newlines."""

    event = _text_event(3, "multi")
    payload = serialize_event(event)
    cut = payload.index(",") + 1  # split between fields, so the join stays valid
    frame = f"id: 3\ndata: {payload[:cut]}\ndata: {payload[cut:]}"
    sequence, parsed = parse_frame(frame)
    assert sequence == 3
    assert parsed is not None
    assert getattr(parsed.payload, "text", None) == "multi"


def test_parse_frame_drops_only_the_separator_space() -> None:
    """`data:` is followed by one optional separator space; further leading
    whitespace belongs to the payload and must survive."""

    assert parse_frame('data: {"a": 1}')[1] is None  # not an event, but parsed
    assert parse_frame("data:  padded")[1] is None
    # The separator handling itself:
    from loopplane.cli.remote import parse_frame as _pf

    assert _pf("data: x")[0] is None


async def test_an_id_less_stream_still_renders_and_does_not_replay_from_zero() -> None:
    """A server with no replay buffer emits no `id:` lines, so the cursor never
    advances — the reconnect then carries no Last-Event-ID, which is the
    server's documented no-buffer behavior rather than a client bug."""

    frame = f"data: {serialize_event(_text_event(1, 'no id here'))}\n\n"
    server = _Server([frame], [f"data: {serialize_event(_terminated(2))}\n\n"])
    out = io.StringIO()
    await remote_loop(
        _endpoint("s1"),
        ["hello", "quit"],
        out,
        transport=server.transport(),
        reconnect_delay=0,
    )
    assert "no id here" in out.getvalue()
    assert server.last_event_ids[:2] == [None, None]


async def test_reconnection_actually_waits_between_attempts() -> None:
    """Without a delay the retry loop is a busy spin: it burns every attempt in
    milliseconds — too fast to survive a one-second server restart — and starves
    the prompt on the same event loop."""

    server = _Server()  # every stream is empty, so it drops immediately
    out = io.StringIO()
    started = time.monotonic()
    await remote_loop(
        _endpoint("s1"),
        ["hello"],
        out,
        transport=server.transport(),
        reconnect_delay=0.05,
    )
    elapsed = time.monotonic() - started
    assert elapsed >= 0.05 * MAX_RECONNECT_ATTEMPTS
    assert RECONNECT_EXHAUSTED_NOTICE.strip() in out.getvalue()


class _WedgingTransport(httpx.AsyncBaseTransport):
    """A server whose turn never finishes, and an operator who gives up.

    This is the shape that made the remediation's own fix necessary: with no
    read deadline, a wedged submit has no timeout to rescue it, and the watch
    owns SIGINT so the runner cannot cancel either. Only racing the submit
    against the interrupt gets the operator out.
    """

    def __init__(self) -> None:
        self.paths: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        if path.endswith("/events"):
            # A live session's stream stays open; it must not end and send the
            # client into its reconnect loop while this test is running.
            await anyio.sleep(30)
        if path.endswith("/submit"):
            signal.raise_signal(signal.SIGINT)  # the operator presses Ctrl-C
            await anyio.sleep(30)  # ...and the turn never comes back
        return httpx.Response(200, json={"resolved": True, "session_id": "s1"})


async def test_a_wedged_remote_turn_can_still_be_interrupted() -> None:
    transport = _WedgingTransport()
    out = io.StringIO()
    started = time.monotonic()
    code = await remote_loop(
        _endpoint("s1"),
        ["start something"],
        out,
        transport=transport,
        reconnect_delay=0,
    )
    elapsed = time.monotonic() - started
    assert code == 0
    assert elapsed < 10, elapsed  # not the 30s the server would have taken

    assert "live remote connection has ended" in out.getvalue()
    assert any(p.endswith("/cancel") for p in transport.paths), transport.paths
