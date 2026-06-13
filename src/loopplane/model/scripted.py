"""The scripted model substitute: the primary test instrument (research R7).

Implements the model boundary from a declarative script of turns and must be
indistinguishable from a real model to the loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

from loopplane.model.boundary import (
    ContextOverflowError,
    ModelIncrement,
    ModelRequest,
    TokenUsage,
    TurnEnd,
)


@dataclass(frozen=True)
class ScriptedTurn:
    """One scripted model turn: increments in order, then a turn end."""

    increments: Sequence[ModelIncrement] = ()
    stop_reason: str = "end-turn"
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True)
class ScriptedOverflow:
    """Directive: signal context overflow instead of producing a turn."""


@dataclass(frozen=True)
class ScriptedFailure:
    """Directive: raise the given error instead of producing a turn."""

    error: Exception


ScriptEntry = ScriptedTurn | ScriptedOverflow | ScriptedFailure


class ScriptedModel:
    """Plays back a declarative script of turns through the model boundary."""

    def __init__(self, script: Sequence[ScriptEntry], context_capacity: int) -> None:
        self._script = list(script)
        self._capacity = context_capacity
        self._cursor = 0

    def context_capacity(self) -> int:
        return self._capacity

    async def stream_turn(self, request: ModelRequest) -> AsyncIterator[ModelIncrement]:
        entry = self._next_entry()
        if isinstance(entry, ScriptedOverflow):
            raise ContextOverflowError("scripted context overflow")
        if isinstance(entry, ScriptedFailure):
            raise entry.error
        for increment in entry.increments:
            yield increment
        yield TurnEnd(stop_reason=entry.stop_reason, usage=entry.usage)

    def _next_entry(self) -> ScriptEntry:
        if self._cursor >= len(self._script):
            raise RuntimeError("scripted model exhausted: no scripted turn remains")
        entry = self._script[self._cursor]
        self._cursor += 1
        return entry
