"""The CLI run core over the Host Application Interface (spec 017 FR-002,
FR-003; spec 079 US1-US3).

``run_once`` is the unchanged one-shot path behind ``loopplane run``.

``chat_loop`` and ``resume_loop`` are the interactive core. Both hold ONE
conversation open over the host's interactive seam, so every turn shares a
session instead of starting a new one; both answer a permission request and an
agent question from the same line source the turns come from; and both let an
interrupt cancel the running turn while leaving the conversation open for the
next one.

All three take a host, their input, and an output stream, so the whole CLI is
exercised with a scripted model and captured streams. The REPL in ``app`` is a
thin wrapper feeding real stdin lines in.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import TextIO

from loopplane.cli.prompts import (
    LineSource,
    interrupt_watch,
    parse_approval_answer,
    question_answer,
)
from loopplane.cli.render import EventRenderer
from loopplane.commands import CommandContext, CommandRegistry, default_registry
from loopplane.events.envelope import (
    ApprovalRequestedPayload,
    QuestionAskedEvent,
    RuntimeEvent,
)
from loopplane.host import (
    ApprovalDecision,
    LoopPlaneHost,
    RunOutcome,
    Session,
)

# The host's approval-handler shape, spelled out here rather than imported: the
# alias lives on a host module that is not part of the public surface.
_OnApproval = Callable[[ApprovalRequestedPayload], Awaitable[ApprovalDecision]]

# The CLI is a single local user with no principal auth; the command surface uses a
# fixed local principal id for caller-scoped reads (065).
_CLI_PRINCIPAL = "local"

INTERRUPTED_NOTICE = "\n[interrupted]\n"
"""Shown when an interrupt stops a turn; the conversation stays open."""


async def run_once(host: LoopPlaneHost, prompt: str, out: TextIO) -> RunOutcome:
    """Run one prompt and render it to ``out``; returns the run outcome."""
    return await host.run(prompt, EventRenderer(out))


class _InteractiveSink:
    """Render every event, and answer a question while the turn still waits.

    A question parks the run until it is answered, so it cannot be handled after
    ``submit`` returns — by then the run would be blocked forever. The event
    stream is the only place the terminal sees the request while the run is
    live, so the answer is given from here. Rendering stays in ``EventRenderer``;
    this only adds the answering.
    """

    def __init__(self, renderer: EventRenderer, source: LineSource) -> None:
        self._renderer = renderer
        self._source = source
        self.session: Session | None = None

    async def __call__(self, event: RuntimeEvent) -> None:
        await self._renderer(event)
        session = self.session
        if session is None or not isinstance(event, QuestionAskedEvent):
            return
        answers = [
            question_answer(await self._source.anext_line())
            for _ in event.payload.questions
        ]
        session.answer_question(event.payload.request_id, answers)


def _approval_handler(source: LineSource) -> _OnApproval:
    """An approval handler reading the operator's decision from ``source``.

    The host calls this after the consumer has already rendered the request
    (``RunSink`` forwards to the consumer first, then to the relay), so the
    operator answers something they have seen. End of input denies, which is the
    safe default.
    """

    async def on_approval(payload: ApprovalRequestedPayload) -> ApprovalDecision:
        answer = parse_approval_answer(await source.anext_line())
        return ApprovalDecision(allow=answer.allow, scope=answer.scope)

    return on_approval


async def _converse(
    session: Session,
    source: LineSource,
    out: TextIO,
    host: LoopPlaneHost,
    registry: CommandRegistry,
) -> None:
    """Read lines and drive one open conversation until the operator leaves."""

    try:
        while True:
            line = await source.anext_line()
            if line is None:
                return
            text = line.strip()
            if not text:
                continue
            if text in ("quit", "exit"):
                return
            if registry.is_command(text):
                result = registry.dispatch(
                    text,
                    CommandContext(
                        host=host,
                        principal_id=_CLI_PRINCIPAL,
                        session_id=session.session_id,
                    ),
                )
                out.write(result.text + "\n")
                continue
            # The watch is installed for the TURN, not for the conversation.
            # Mid-turn, Ctrl-C means "stop this turn"; at an idle prompt it has
            # always meant "leave", and leaving that window to the runtime's own
            # handling is what keeps that true — a handler of ours covering the
            # idle window would either swallow the interrupt or arm the
            # controller's next-turn cancellation and silently discard the
            # operator's next input.
            with interrupt_watch(session.cancel) as interrupted:
                try:
                    await session.submit(text)
                except KeyboardInterrupt:
                    # Only reachable when a KeyboardInterrupt is raised
                    # synchronously inside the turn's own frames. Note we do NOT
                    # cancel here: the turn is already over and the controller
                    # has re-armed a fresh cancellation signal, so cancelling
                    # would kill the NEXT turn instead.
                    interrupted.fired = False
                    out.write(INTERRUPTED_NOTICE)
                    continue
            if interrupted.take():
                # The watch cancelled the turn; it ended through the runtime's
                # normal cancellation path, and the conversation is still open.
                out.write(INTERRUPTED_NOTICE)
    finally:
        # Leaving for good: cancel resolves anything still pending, and no
        # further turn will observe the signal.
        session.cancel()


async def chat_loop(host: LoopPlaneHost, lines: Iterable[str], out: TextIO) -> None:
    """Hold one conversation, running each input line as a turn in it.

    A leading ``/`` is intercepted as a backend command (065) and dispatched
    against the host's existing seams (never sent to the model); ordinary input
    is submitted as a turn. ``quit``/``exit`` or end of input closes the
    conversation.
    """

    source = LineSource(lines)
    sink = _InteractiveSink(EventRenderer(out), source)
    async with host.session(sink, on_approval=_approval_handler(source)) as session:
        sink.session = session
        await _converse(session, source, out, host, default_registry())


async def resume_loop(
    host: LoopPlaneHost, session_id: str, lines: Iterable[str], out: TextIO
) -> None:
    """Pick a stored conversation back up and continue it interactively.

    Raises ``KeyError``/``RuntimeError`` when the conversation cannot be
    resumed; the caller renders that as a public-safe failure.
    """

    source = LineSource(lines)
    sink = _InteractiveSink(EventRenderer(out), source)
    async with host.resume_session(
        session_id, sink, on_approval=_approval_handler(source)
    ) as session:
        sink.session = session
        await _converse(session, source, out, host, default_registry())
