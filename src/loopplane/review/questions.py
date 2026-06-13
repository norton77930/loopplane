"""Review questions and the Review Context (contracts/review.md; FR-041–FR-043).

The Review Context the gate passes to a reviewer, through which the reviewer can
ask the human structured review questions via a host-supplied asker. Asking is
fail-safe: no asker raises a clear ``ReviewError``; a raising asker becomes a
diagnostic and returns no answer — never a silent hang.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from loopplane.review.events import ReviewEventType

QuestionAsker = Callable[
    ["Sequence[ReviewQuestion]"], "Sequence[str] | Awaitable[Sequence[str]]"
]

# An async emitter the gate binds for one Review Request (type, payload) -> None.
EventEmit = Callable[[ReviewEventType, "dict[str, Any]"], Awaitable[None]]


@dataclass(frozen=True)
class ReviewQuestion:
    """A single structured review question with optional choices."""

    text: str
    options: tuple[str, ...] = ()


class ReviewError(RuntimeError):
    """Raised when a review question cannot be asked (no asker configured).

    Public-safe; never carries a secret or a private path (NFR-004).
    """


class ReviewContext:
    """What the gate passes to a reviewer: a channel to ask review questions."""

    def __init__(
        self, *, asker: QuestionAsker | None = None, emit: EventEmit | None = None
    ) -> None:
        self._asker = asker
        self._emit = emit

    async def ask(self, questions: Sequence[ReviewQuestion]) -> list[str]:
        """Ask the human structured review questions and return the answers
        (FR-042). With no asker, raise ``ReviewError`` (FR-043); a raising asker
        yields a diagnostic and an empty answer list."""

        if self._asker is None:
            raise ReviewError("no question asker is configured for this review")
        await self._emit_event("review_question_asked", {"count": len(questions)})
        try:
            raw = self._asker(list(questions))
            answers = list(await raw) if isinstance(raw, Awaitable) else list(raw)
        except Exception as exc:  # noqa: BLE001 - non-fatal diagnostic (FR-043)
            await self._emit_event(
                "review_question_answered", {"count": 0, "error": repr(exc)}
            )
            return []
        await self._emit_event("review_question_answered", {"count": len(answers)})
        return answers

    async def _emit_event(
        self, event_type: ReviewEventType, payload: dict[str, Any]
    ) -> None:
        if self._emit is not None:
            await self._emit(event_type, payload)
