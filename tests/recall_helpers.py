"""Deterministic, public-safe test helpers for the recall layer (007).

Scripted public Loop State plus in-memory doubles for the host-supplied stores
(an artifact reader, durable memory entries). No filesystem, credentials, or
clock — every value is fixed so recall is reproducible.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from loopplane.artifacts import ArtifactMeta
from loopplane.engineering import (
    ArtifactRef,
    LoopState,
    RunReference,
    ValidationResult,
)
from loopplane.memory import MemoryEntry


def scripted_state(
    *,
    loop_id: str = "L",
    run_refs: Sequence[RunReference] = (),
    artifacts: Sequence[ArtifactRef] = (),
    validation_reason: str | None = None,
) -> LoopState:
    """A scripted public Loop State (references only; no host needed)."""

    validation = (
        ValidationResult(status="pass", reason=validation_reason)
        if validation_reason is not None
        else None
    )
    return LoopState(
        loop_id=loop_id,
        loop_definition_id=f"def-{loop_id}",
        run_refs=tuple(run_refs),
        artifacts=tuple(artifacts),
        latest_validation=validation,
    )


def run_ref(session_id: str, reason: str = "natural-completion") -> RunReference:
    return RunReference(session_id, reason)


def artifact_ref(session_id: str, reference: str) -> ArtifactRef:
    return ArtifactRef(session_id, reference)


def artifact_meta(
    session_id: str,
    reference: str,
    *,
    day: int = 1,
    size: int = 10,
    media_kind: str = "text",
) -> ArtifactMeta:
    """An ArtifactMeta with a fixed, deterministic ``created_at`` (``day`` orders
    newest-first tests)."""

    return ArtifactMeta(
        reference=reference,
        session_id=session_id,
        call_id="call",
        size=size,
        media_kind=media_kind,  # type: ignore[arg-type]
        created_at=datetime(2026, 1, day, tzinfo=UTC),
    )


class ScriptedArtifactReader:
    """An in-memory ``ArtifactReader`` double keyed by (session_id, reference)."""

    def __init__(
        self, metas: Sequence[ArtifactMeta] = (), *, raising: bool = False
    ) -> None:
        self._by_key = {(meta.session_id, meta.reference): meta for meta in metas}
        self._raising = raising

    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None:
        if self._raising:
            raise RuntimeError("artifact reader boom")
        return self._by_key.get((session_id, reference))


def memory_entry(
    name: str,
    description: str = "",
    *,
    entry_type: str = "reference",
    body: str = "",
) -> MemoryEntry:
    return MemoryEntry(type=entry_type, name=name, description=description, body=body)
