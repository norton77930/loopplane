"""Deterministic, public-safe test helpers for the validator/evaluator packs
(feature 005). Builds scripted Phase-3 ``RunOutcome`` + ``LoopState`` pairs so
packs can be exercised as pure functions — no runtime, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime

from loopplane.engineering import ArtifactRef, LoopState
from loopplane.host import RunOutcome
from loopplane.loop.history import HistoryEntry
from loopplane.model import TextBlock

_FIXED_DT = datetime(2026, 1, 1, tzinfo=UTC)


def scripted_outcome(
    *,
    text: str = "",
    terminal: str = "natural-completion",
    artifacts: tuple[str, ...] = (),
) -> tuple[RunOutcome, LoopState]:
    """A scripted ``(RunOutcome, LoopState)`` pair with a single assistant text
    entry (when ``text`` is given) and the named artifact references."""

    history: tuple[HistoryEntry, ...] = ()
    if text:
        history = (
            HistoryEntry(
                role="assistant",
                blocks=(TextBlock(text=text),),
                recorded_at=_FIXED_DT,
            ),
        )
    outcome = RunOutcome(
        session_id="s1",
        termination_reason=terminal,
        turns_taken=1,
        history=history,
    )
    state = LoopState(
        loop_id="L",
        loop_definition_id="L",
        artifacts=tuple(
            ArtifactRef(session_id="s1", reference=ref) for ref in artifacts
        ),
    )
    return outcome, state


# A minimal public-safe JSON schema for the JSON-schema validator tests.
SAMPLE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
