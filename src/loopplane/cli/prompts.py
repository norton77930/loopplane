"""Terminal interaction primitives: input, answer parsing, and interruption
(spec 079 US1-US3, US6).

Three things live here because both the local and the remote conversation need
exactly the same behavior from them:

* **One line source.** A turn, an approval decision, and a question answer all
  come from the same place, which is why a pending request simply consumes the
  operator's next line — and why the whole interactive loop is drivable from a
  list of strings in tests.
* **Answers off the event loop.** The real source is a blocking ``input()``.
  Reading it inline would freeze everything else the loop is doing; on the
  remote path that means the event stream stops rendering while the operator
  thinks. ``anext_line`` moves the read to a worker thread and serializes
  concurrent readers, since the stream task and the prompt both read here.
* **Interruption that the runtime can act on.** See :func:`interrupt_watch`.

Nothing here touches a host or a runtime.
"""

from __future__ import annotations

import signal
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

import anyio
import anyio.to_thread

__all__ = [
    "ApprovalAnswer",
    "InterruptState",
    "LineSource",
    "interrupt_watch",
    "parse_approval_answer",
    "question_answer",
]


class LineSource:
    """A one-pass view over the caller's input lines.

    ``next_line`` returns ``None`` at end of input, which is distinct from an
    empty line: a blank line is a value the operator typed, end of input is the
    operator leaving.
    """

    def __init__(self, lines: Iterable[str]) -> None:
        self._lines: Iterator[str] = iter(lines)
        self._exhausted = False
        self._lock = anyio.Lock()

    @property
    def exhausted(self) -> bool:
        """Whether the source has run out of lines."""

        return self._exhausted

    def next_line(self) -> str | None:
        """The next raw line, or ``None`` once the input has ended.

        Blocking. Prefer :meth:`anext_line` from async code.
        """

        try:
            return next(self._lines)
        except StopIteration:
            self._exhausted = True
            return None

    async def anext_line(self) -> str | None:
        """The next raw line, read without blocking the event loop.

        The lock matters on the remote path, where the event-stream task answers
        a request from the same source the prompt reads turns from. Without it,
        a line typed near the settle boundary could be claimed by whichever
        happened to be scheduled first.
        """

        async with self._lock:
            # Abandoned on cancellation: the real source blocks in `input()`
            # until the operator types, so waiting for the thread would make
            # every shutdown hostage to a keystroke. The abandoned thread keeps
            # its pending read, which is harmless on the way out.
            return await anyio.to_thread.run_sync(
                self.next_line, abandon_on_cancel=True
            )


@dataclass(frozen=True)
class ApprovalAnswer:
    """A parsed permission decision: what to do, and for how long."""

    allow: bool
    scope: Literal["once", "session"]


def parse_approval_answer(line: str | None) -> ApprovalAnswer:
    """Map a typed line to a decision.

    ``y``/``yes`` allow once, ``a``/``always`` allow for the rest of the
    conversation, ``n``/``no`` deny once, ``never`` denies for the rest of it.
    Anything else — including a blank line or the end of input — denies once,
    which is the safe default: an operator who did not answer has not consented.
    """

    text = (line or "").strip().lower()
    if text in ("y", "yes"):
        return ApprovalAnswer(allow=True, scope="once")
    if text in ("a", "always"):
        return ApprovalAnswer(allow=True, scope="session")
    if text == "never":
        return ApprovalAnswer(allow=False, scope="session")
    return ApprovalAnswer(allow=False, scope="once")


def question_answer(line: str | None) -> str:
    """The answer text for a pending question; end of input answers empty
    rather than leaving the run waiting."""

    return (line or "").strip()


@dataclass
class InterruptState:
    """Whether an interrupt arrived since it was last acknowledged."""

    fired: bool = field(default=False)
    installed: bool = field(default=False)

    def take(self) -> bool:
        """Consume the flag: True once per interrupt."""

        fired = self.fired
        self.fired = False
        return fired


@contextmanager
def interrupt_watch(on_interrupt: Callable[[], None]) -> Iterator[InterruptState]:
    """Route Ctrl-C to ``on_interrupt`` for the duration of a conversation.

    **Why this exists rather than ``except KeyboardInterrupt``.** Under
    ``anyio.run`` the asyncio runner installs its own SIGINT handler and
    *cancels the main task*, so what reaches ``await session.submit(...)`` is a
    ``CancelledError``; the ``KeyboardInterrupt`` only surfaces after the runner
    unwinds, on its way out of the process. An ``except KeyboardInterrupt``
    around the turn therefore never fires in a real terminal — it fires only for
    a ``KeyboardInterrupt`` raised synchronously inside the turn's own frames,
    which is what a test can inject and a user cannot produce. Verified on
    CPython 3.12: ``CancelledError`` reaches the await, ``KeyboardInterrupt``
    escapes ``anyio.run``.

    Installing our own handler for the life of the conversation is what makes
    "cancel the turn, keep the conversation" true rather than aspirational: the
    callback runs on the main thread at the next bytecode boundary and asks the
    runtime to cancel, which the turn observes through its normal cancellation
    path instead of through exception propagation.

    Outside the main thread — an embedded host, some test harnesses — signal
    handlers cannot be installed; the watch then yields an inert state rather
    than failing the conversation, and ``installed`` says which happened.
    """

    state = InterruptState()

    def handler(signum: int, frame: object) -> None:
        state.fired = True
        on_interrupt()

    try:
        previous = signal.signal(signal.SIGINT, handler)
    except (ValueError, OSError):
        yield state
        return

    state.installed = True
    try:
        yield state
    finally:
        signal.signal(signal.SIGINT, previous)
