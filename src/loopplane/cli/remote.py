"""The terminal's remote bridge (spec 079 US6, US7).

The terminal drives a conversation on a LoopPlane web/API host by being a
**client** of the endpoints that host already exposes. Nothing here changes the
outward contract: it opens or attaches to a session, submits turns, answers
approvals and questions, interrupts, and reads the session's event stream with
``Last-Event-ID`` reconnection — all against existing routes.

Three properties are worth stating, because they are what keep this module
small:

* **The renderer is shared.** Each frame's payload is turned back into a
  ``RuntimeEvent`` and handed to the same ``EventRenderer`` the local path uses,
  so remote output is public-safe by construction and there is no second
  renderer to keep in step.
* **The no-loss guarantee is the server's.** ``reconnect_stream`` merges the
  retained buffer, the queued live frames, and any durable records in sequence
  order. This client's only obligation is to remember the last sequence it
  rendered and to drop anything at or below it.
* **The command policy is the command surface's.** Whether a command may run
  remotely is declared once in ``loopplane.commands`` and read here through
  ``describe()``. A refused command is never sent.

``httpx`` is imported lazily and only here, from the already-declared ``net``
extra, so the terminal still imports and runs with base dependencies alone.

The credential is held in memory for the life of the connection and never
rendered, logged, or included in a failure message.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Literal, TextIO

import anyio

from loopplane.cli.prompts import (
    LineSource,
    interrupt_watch,
    parse_approval_answer,
    question_answer,
)
from loopplane.cli.render import EventRenderer
from loopplane.commands import (
    REMOTE_REFUSAL,
    CommandRegistry,
    CommandResult,
    default_registry,
    format_command_listing,
)
from loopplane.events import RuntimeEvent, deserialize_event
from loopplane.events.envelope import (
    ApprovalRequestedEvent,
    QuestionAskedEvent,
    RunTerminatedEvent,
)

__all__ = [
    "MAX_RECONNECT_ATTEMPTS",
    "RemoteClient",
    "RemoteEndpoint",
    "RemoteGone",
    "RemoteUnavailable",
    "StreamCursor",
    "frames_from_lines",
    "parse_frame",
    "remote_loop",
]

API_PREFIX = "/v1"
MAX_RECONNECT_ATTEMPTS = 3
"""How many times a dropped stream is retried before giving up (FR-037)."""

TURN_SETTLE_SECONDS = 10.0
"""How long the prompt waits for the stream to finish rendering a turn.

This bounds a *render* lag, not the turn: the submit request has no read
deadline, so a turn takes as long as it takes. If the stream is still behind
after this, the prompt returns anyway and late frames keep rendering.
"""

_CANCEL_GRACE_SECONDS = 5.0
"""How long an interrupt waits for the server to acknowledge the cancel."""

RECONNECT_DELAY_SECONDS = 1.0
"""How long to wait between reconnection attempts (FR-037)."""

RECONNECTING_NOTICE = "\n[reconnecting…]\n"
RECONNECTING_UNSEQUENCED_NOTICE = (
    "\n[reconnecting… this server sends no event ids, so anything missed"
    " while disconnected cannot be replayed]\n"
)
RECONNECT_EXHAUSTED_NOTICE = "\n[reconnect failed; giving up]\n"
REMOTE_ENDED_NOTICE = "\n[the remote conversation is no longer available]\n"
INTERRUPT_NOTICE = "\n[interrupted; the live remote connection has ended]\n"

_MISSING_HTTP = (
    "remote operation needs the optional network capability, which is not installed"
)
_UNREACHABLE = "could not reach the server"
_REJECTED = "the server rejected the credential"
_REFUSED_OPERATION = "the server refused that operation"


class RemoteUnavailable(Exception):
    """A public-safe remote failure. Its message never carries the credential,
    a private path, or a raw exception."""


class RemoteGone(RemoteUnavailable):
    """The conversation is not available on that server — it ended, it is not
    resumable, or it does not belong to this caller. The three are deliberately
    indistinguishable (FR-029)."""


@dataclass(frozen=True)
class RemoteEndpoint:
    """Where to connect and as whom. Holds the credential only in memory."""

    base_url: str
    token: str
    session_id: str | None = None
    # `create_app` takes an `api_prefix`, so a deployment need not use /v1.
    api_prefix: str = API_PREFIX

    @property
    def api(self) -> str:
        return self.base_url.rstrip("/") + self.api_prefix


@dataclass
class StreamCursor:
    """The operator's place in a remote conversation's event sequence."""

    last_sequence: int | None = None
    attempts: int = 0

    def accepts(self, sequence: int | None) -> bool:
        """Whether a frame at ``sequence`` has not been rendered yet."""

        if sequence is None:
            return True
        return self.last_sequence is None or sequence > self.last_sequence

    def advance(self, sequence: int | None) -> None:
        """Record a rendered frame; only rendered frames move the cursor."""

        if sequence is not None:
            self.last_sequence = sequence


def parse_frame(frame: str) -> tuple[int | None, RuntimeEvent | None]:
    """The sequence and the event carried by one SSE frame.

    The ``id:`` line is present when the server retains a replay buffer or a
    replay store and absent otherwise. An unknown or corrupt payload yields
    ``None`` for the event rather than raising.
    """

    sequence: int | None = None
    data: list[str] = []
    for raw in frame.splitlines():
        if raw.startswith("id:"):
            try:
                sequence = int(raw[3:].strip())
            except ValueError:
                sequence = None
        elif raw.startswith("data:"):
            # Exactly one space after the colon is the field separator and is
            # dropped; anything beyond that is data. Stripping all leading
            # whitespace would silently alter a payload that begins with it.
            value = raw[5:]
            data.append(value[1:] if value.startswith(" ") else value)
    if not data:
        return sequence, None
    # Multiple `data:` lines in one frame are joined with newlines, per SSE.
    return sequence, deserialize_event("\n".join(data))


async def frames_from_lines(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    """Group SSE lines into frames; a blank line ends a frame."""

    buffer: list[str] = []
    async for line in lines:
        if not line.strip():
            if buffer:
                yield "\n".join(buffer)
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        yield "\n".join(buffer)


def _httpx() -> Any:
    """The HTTP client module, or a public-safe explanation of its absence."""

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RemoteUnavailable(_MISSING_HTTP) from exc
    return httpx


class RemoteClient:
    """A thin client over the web/API host's existing session endpoints."""

    def __init__(
        self,
        endpoint: RemoteEndpoint,
        *,
        transport: Any = None,
        timeout: float = 30.0,
    ) -> None:
        self._endpoint = endpoint
        self._transport = transport
        self._timeout = timeout
        self._client: Any = None

    async def __aenter__(self) -> RemoteClient:
        httpx = _httpx()
        # A turn legitimately takes as long as the model takes, and the submit
        # request spans the whole turn server-side, so a READ deadline would end
        # the conversation on any realistic call — and would do it with
        # "could not reach the server", which is not what happened. Connect,
        # write, and pool still fail fast, so an actually unreachable host is
        # still reported promptly.
        kwargs: dict[str, Any] = {
            "base_url": self._endpoint.api,
            "headers": {"Authorization": f"Bearer {self._endpoint.token}"},
            "timeout": httpx.Timeout(
                connect=self._timeout,
                read=None,
                write=self._timeout,
                pool=self._timeout,
            ),
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        self._client = httpx.AsyncClient(**kwargs)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        client = self._client
        self._client = None
        if client is not None:
            await client.aclose()

    def _require(self) -> Any:
        if self._client is None:  # pragma: no cover - programming error
            raise RemoteUnavailable(_UNREACHABLE)
        return self._client

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """One request, with every failure normalized to a public-safe error.

        The credential is never echoed: the messages here are fixed strings and
        the underlying exception is never rendered.
        """

        httpx = _httpx()
        client = self._require()
        try:
            response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise RemoteUnavailable(_UNREACHABLE) from exc
        return self._checked(response)

    @staticmethod
    def _body(response: Any) -> dict[str, Any]:
        """The response's JSON object, or a public-safe failure.

        A 2xx that is not JSON — a proxy interstitial, a captive portal, an
        HTML error page — must not escape as a raw parse error carrying whoever
        wrote that page.
        """

        try:
            body = response.json()
        except Exception as exc:  # noqa: BLE001 - any parse failure is the same
            raise RemoteUnavailable(_REFUSED_OPERATION) from exc
        if not isinstance(body, dict):
            raise RemoteUnavailable(_REFUSED_OPERATION)
        return body

    @staticmethod
    def _checked(response: Any) -> Any:
        status = response.status_code
        if status in (401, 403):
            raise RemoteUnavailable(_REJECTED)
        if status == 404:
            raise RemoteGone(REMOTE_ENDED_NOTICE.strip().strip("[]"))
        if status >= 400:
            raise RemoteUnavailable(_REFUSED_OPERATION)
        return response

    async def open_session(self) -> str:
        response = await self._request("POST", "/sessions")
        session_id = self._body(response).get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise RemoteUnavailable(_REFUSED_OPERATION)
        return session_id

    async def submit(self, session_id: str, prompt: str) -> None:
        await self._request(
            "POST", f"/sessions/{session_id}/submit", json={"prompt": prompt}
        )

    async def answer_approval(
        self,
        session_id: str,
        request_id: str,
        *,
        allow: bool,
        scope: Literal["once", "session"],
    ) -> None:
        await self._request(
            "POST",
            f"/sessions/{session_id}/approvals/{request_id}",
            json={"allow": allow, "scope": scope},
        )

    async def answer_question(
        self, session_id: str, request_id: str, answers: list[str]
    ) -> None:
        await self._request(
            "POST",
            f"/sessions/{session_id}/questions/{request_id}",
            json={"answers": answers},
        )

    async def cancel(self, session_id: str) -> None:
        await self._request("POST", f"/sessions/{session_id}/cancel")

    async def run_command(self, line: str, session_id: str | None) -> CommandResult:
        response = await self._request(
            "POST", "/commands", json={"command": line, "session_id": session_id}
        )
        body = self._body(response)
        kind = body.get("kind", "error")
        if kind not in ("ok", "unknown", "error"):
            kind = "error"
        return CommandResult(kind=kind, text=str(body.get("text", "")))

    async def stream(
        self, session_id: str, last_sequence: int | None
    ) -> AsyncIterator[tuple[int | None, RuntimeEvent | None]]:
        """The session's events, resuming after ``last_sequence`` when set."""

        httpx = _httpx()
        client = self._require()
        headers = {}
        if last_sequence is not None:
            headers["Last-Event-ID"] = str(last_sequence)
        try:
            async with client.stream(
                "GET",
                f"/sessions/{session_id}/events",
                headers=headers,
                # Reads are unbounded (a stream is idle between turns), but
                # connect stays bounded: `timeout=None` here would override the
                # client's Timeout entirely, and a blackholed host would then
                # block forever in connect — silently defeating the bounded
                # reconnect attempts.
                timeout=httpx.Timeout(
                    connect=self._timeout,
                    read=None,
                    write=self._timeout,
                    pool=self._timeout,
                ),
            ) as response:
                self._checked(response)
                async for frame in frames_from_lines(response.aiter_lines()):
                    yield parse_frame(frame)
        except httpx.HTTPError as exc:
            raise RemoteUnavailable(_UNREACHABLE) from exc


def remote_command_verdict(
    registry: CommandRegistry, line: str
) -> CommandResult | None:
    """``None`` when the command may be forwarded, a refusal otherwise.

    The classification is read from the shared command surface, so the terminal
    and every other host answer the same question the same way.
    """

    name = line.strip()[1:].strip().split(" ", 1)[0].lower()
    for descriptor in registry.describe():
        if descriptor.name == name:
            if descriptor.remote_safe:
                return None
            return CommandResult(kind="error", text=f"/{name}: {REMOTE_REFUSAL}")
    return CommandResult(kind="unknown", text=f"unknown command: /{name}")


@dataclass
class _Remote:
    """The pieces one remote conversation is driven with."""

    client: RemoteClient
    session_id: str
    source: LineSource
    out: TextIO
    renderer: EventRenderer
    registry: CommandRegistry
    cursor: StreamCursor = field(default_factory=StreamCursor)
    reconnect_delay: float = field(default_factory=lambda: RECONNECT_DELAY_SECONDS)
    # How many turns the stream has seen end. The prompt waits for this to move
    # rather than for a per-turn Event, because a terminal frame can arrive
    # BEFORE the submit call returns — a fresh Event would then be waiting for
    # something that already happened, and would sit out its whole timeout.
    turns_ended: int = 0
    # Released alongside the counter, so a waiter wakes immediately.
    turn_done: anyio.Event = field(default_factory=anyio.Event)
    # Set when the stream found the conversation gone, so the exit code matches
    # the one the same discovery produces through a submit.
    gone: bool = False


async def _answer_pending(remote: _Remote, event: RuntimeEvent) -> None:
    """Answer a request while the remote turn is still parked on it."""

    if isinstance(event, ApprovalRequestedEvent):
        answer = parse_approval_answer(await remote.source.anext_line())
        await remote.client.answer_approval(
            remote.session_id,
            event.payload.request_id,
            allow=answer.allow,
            scope=answer.scope,
        )
    elif isinstance(event, QuestionAskedEvent):
        answers = [
            question_answer(await remote.source.anext_line())
            for _ in event.payload.questions
        ]
        await remote.client.answer_question(
            remote.session_id, event.payload.request_id, answers
        )


async def _stream_until(remote: _Remote, stop: anyio.Event) -> None:
    """Render the remote stream, reconnecting when it drops (US7)."""

    while not stop.is_set():
        try:
            async for sequence, event in remote.client.stream(
                remote.session_id, remote.cursor.last_sequence
            ):
                if not remote.cursor.accepts(sequence):
                    continue
                if event is None:
                    # A frame we could not read is not progress. Resetting the
                    # attempt count here would let a server that answers with
                    # something unparseable keep the client retrying forever.
                    remote.cursor.advance(sequence)
                    continue
                remote.cursor.attempts = 0
                await remote.renderer(event)
                if isinstance(event, RunTerminatedEvent):
                    remote.turns_ended += 1
                    remote.turn_done.set()
                await _answer_pending(remote, event)
                # The cursor advances only once the frame is fully handled. If
                # answering a request failed, the frame is not marked seen, so
                # the reconnect replays it and the operator is asked again —
                # a repeated prompt is far better than a turn parked forever on
                # an answer that never arrived.
                remote.cursor.advance(sequence)
        except RemoteGone:
            remote.out.write(REMOTE_ENDED_NOTICE)
            remote.gone = True
            _halt(remote, stop)
            return
        except RemoteUnavailable:
            pass
        if stop.is_set():
            return
        remote.cursor.attempts += 1
        if remote.cursor.attempts > MAX_RECONNECT_ATTEMPTS:
            remote.out.write(RECONNECT_EXHAUSTED_NOTICE)
            _halt(remote, stop)
            return
        # The no-loss guarantee is the server's, and it depends on the server
        # keeping a replay buffer. Without one there are no `id:` lines, the
        # cursor never advances, and the reconnect carries no Last-Event-ID —
        # say so rather than implying a resume that cannot happen.
        remote.out.write(
            RECONNECTING_NOTICE
            if remote.cursor.last_sequence is not None
            else RECONNECTING_UNSEQUENCED_NOTICE
        )
        # Wait before retrying. Without this the loop is a busy spin: a server
        # that closes the stream immediately burns every attempt in
        # milliseconds — too fast to survive even a one-second restart — and
        # starves everything else on the event loop, including the prompt.
        await anyio.sleep(remote.reconnect_delay)


def _halt(remote: _Remote, stop: anyio.Event) -> None:
    """End the conversation from the stream's side.

    ``turn_done`` is released too: a prompt waiting for the stream to finish a
    turn must wake up when the stream has given up, rather than sitting out its
    settle timeout for a stream that will never speak again.
    """

    stop.set()
    remote.turn_done.set()


async def _converse(remote: _Remote, stop: anyio.Event) -> int:
    """Read lines and drive the remote conversation until the operator leaves.

    Returns a process exit code. A remote failure is reported here rather than
    raised, because raising out of the surrounding task group would arrive at
    the caller wrapped in an exception group.
    """

    while True:
        line = await remote.source.anext_line()
        if line is None:
            return 0
        text = line.strip()
        if not text:
            continue
        if text in ("quit", "exit"):
            return 0
        if remote.registry.is_command(text):
            answered = _local_command(remote, text)
            if answered is not None:
                remote.out.write(answered.text + "\n")
                continue
            try:
                result = await remote.client.run_command(text, remote.session_id)
            except RemoteUnavailable as exc:
                remote.out.write(f"{exc}\n")
                return 1
            remote.out.write(result.text + "\n")
            continue
        ended_before = remote.turns_ended
        remote.turn_done = anyio.Event()
        interrupt_requested = anyio.Event()
        cut_short = False
        # Installed for the TURN only — see the note in `session._converse`:
        # the idle window belongs to the runtime's own Ctrl-C handling.
        with interrupt_watch(interrupt_requested.set) as interrupted:
            try:
                cut_short = await _submit_racing_interrupt(
                    remote, text, interrupt_requested
                )
                # Let the stream finish rendering this turn before prompting
                # again — unless it already finished while submit was in flight,
                # which the counter, unlike the Event, can still tell us.
                if (
                    not cut_short
                    and remote.turns_ended == ended_before
                    and not stop.is_set()
                ):
                    await _wait_either(remote.turn_done, stop, TURN_SETTLE_SECONDS)
            except RemoteUnavailable as exc:
                remote.out.write(f"{exc}\n")
                return 1
            except KeyboardInterrupt:
                # Only reachable from a synchronously raised KeyboardInterrupt.
                interrupted.fired = True
        if cut_short or interrupted.take() or interrupt_requested.is_set():
            # Interrupting remotely ends the live connection: that is the
            # server's existing behavior, which this unit does not change.
            # The conversation itself survives and stays listed (FR-028).
            await _cancel_remote_turn(remote)
            remote.out.write(INTERRUPT_NOTICE)
            return 0
            if stop.is_set():
                # A conversation that turned out to be gone is a failure to do
                # what was asked, however it was discovered.
                return 1 if remote.gone else 0


async def _submit_racing_interrupt(
    remote: _Remote, text: str, interrupt_requested: anyio.Event
) -> bool:
    """Submit a turn, abandoning the wait if the operator interrupts.

    Returns ``True`` when the interrupt won the race.

    A remote submit spans the whole turn server-side and deliberately has no
    read deadline, because a turn may legitimately take minutes. That makes this
    race the *only* way to interrupt one: without it the signal handler would
    set an event nobody is waiting on while the request stays blocked, and —
    since the watch owns SIGINT — the runner's own cancellation is gone too. An
    operator whose turn wedged would have no way out short of killing the
    process.
    """

    failure: list[BaseException] = []
    interrupted = False

    async with anyio.create_task_group() as tg:

        async def submit() -> None:
            try:
                await remote.client.submit(remote.session_id, text)
            except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - re-raised
                # Deliberately NOT BaseException: catching the cancellation that
                # the watch below raises here would swallow the very cancel that
                # is ending this turn, and re-raising it afterwards would look
                # like a failure instead of an interrupt.
                failure.append(exc)
            finally:
                tg.cancel_scope.cancel()

        async def watch() -> None:
            nonlocal interrupted
            await interrupt_requested.wait()
            interrupted = True
            tg.cancel_scope.cancel()

        tg.start_soon(submit)
        tg.start_soon(watch)

    if failure:
        raise failure[0]
    return interrupted


def _local_command(remote: _Remote, text: str) -> CommandResult | None:
    """The answer this terminal gives without asking the server, or ``None``
    when the command should be forwarded.

    ``/help`` is answered here on purpose: a listing produced on the server
    describes the server's context, not the operator's, and would advertise
    commands this terminal will then refuse to send (FR-022).
    """

    verdict = remote_command_verdict(remote.registry, text)
    if verdict is not None:
        return verdict
    if text.strip()[1:].strip().split(" ", 1)[0].lower() == "help":
        return CommandResult(
            kind="ok",
            text=format_command_listing(remote.registry.describe(), remote=True),
        )
    return None


async def _wait_either(first: anyio.Event, second: anyio.Event, timeout: float) -> None:
    """Wait until either event fires, or ``timeout`` elapses.

    The prompt waits on two things at once: the turn finishing, and the stream
    giving up. Waiting on only the first is what made a dead stream cost a full
    settle timeout before the prompt noticed.
    """

    with anyio.move_on_after(timeout):
        async with anyio.create_task_group() as tg:

            async def wait(event: anyio.Event) -> None:
                await event.wait()
                tg.cancel_scope.cancel()

            tg.start_soon(wait, first)
            tg.start_soon(wait, second)


async def _cancel_remote_turn(remote: _Remote) -> None:
    """Ask the server to stop the running turn, shielded so the request still
    goes out while everything around it is being torn down."""

    with anyio.CancelScope(shield=True):
        with anyio.move_on_after(_CANCEL_GRACE_SECONDS):
            try:
                await remote.client.cancel(remote.session_id)
            except RemoteUnavailable:
                pass


async def remote_loop(
    endpoint: RemoteEndpoint,
    lines: Iterable[str],
    out: TextIO,
    *,
    transport: Any = None,
    reconnect_delay: float | None = None,
) -> int:
    """Drive a remote conversation from ``lines``; returns a process exit code.

    Every failure surfaces as a public-safe line and exit code 1; the credential
    never appears in any of them.
    """

    source = LineSource(lines)
    code = 0
    try:
        async with RemoteClient(endpoint, transport=transport) as client:
            session_id = endpoint.session_id or await client.open_session()
            remote = _Remote(
                client=client,
                session_id=session_id,
                source=source,
                out=out,
                renderer=EventRenderer(out),
                registry=default_registry(),
                reconnect_delay=(
                    RECONNECT_DELAY_SECONDS
                    if reconnect_delay is None
                    else reconnect_delay
                ),
            )
            stop = anyio.Event()
            async with anyio.create_task_group() as tg:
                tg.start_soon(_stream_until, remote, stop)
                try:
                    code = await _converse(remote, stop)
                finally:
                    stop.set()
                    tg.cancel_scope.cancel()
            if code == 0 and remote.gone:
                # The stream may only discover the conversation is gone after
                # the prompt has already returned; deciding here rather than
                # inside the loop keeps the exit code independent of that race.
                code = 1
    except RemoteUnavailable as exc:
        # Reaching here means the failure happened before the conversation was
        # under way (connecting, or opening the session).
        out.write(f"{exc}\n")
        return 1
    return code
