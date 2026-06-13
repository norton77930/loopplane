"""Artifact recall: newest-first, public-safe references + metadata of the
artifacts the loop produced (contracts/recall.md; FR-020-FR-022).

Reads ``LoopState.artifacts`` and fetches metadata through a narrow, host-supplied
``ArtifactReader`` (the public Phase-1 ``ArtifactStore`` satisfies it structurally).
It surfaces only a reference + declared metadata — never artifact content or a
filesystem path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from loopplane.recall.entry import RecalledEntry, RecallSource

if TYPE_CHECKING:
    from loopplane.artifacts import ArtifactMeta
    from loopplane.engineering import LoopState


class ArtifactReader(Protocol):
    """A narrow read seam over artifact metadata; the host's ``ArtifactStore``
    satisfies it (FR-020)."""

    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None: ...


def artifact_recall(reader: ArtifactReader, *, limit: int = 10) -> RecallSource:
    """A recall source over the loop's artifacts, newest-first by ``created_at``,
    surfacing public-safe metadata only (FR-020-FR-022). A missing reference is
    skipped; a raising reader contributes nothing (NFR-005)."""

    def source(state: LoopState) -> tuple[RecalledEntry, ...]:
        metas: list[ArtifactMeta] = []
        for ref in state.artifacts:
            try:
                meta = reader.metadata(ref.session_id, ref.reference)
            except Exception:  # noqa: BLE001 - fail safe: a raising reader contributes nothing
                return ()
            if meta is not None:
                metas.append(meta)
        metas.sort(key=lambda meta: meta.created_at, reverse=True)
        return tuple(
            RecalledEntry(
                text=(
                    f"artifact {meta.reference} "
                    f"({meta.media_kind}, {meta.size} bytes, "
                    f"created {meta.created_at.isoformat()})"
                ),
                origin="artifact",
                identifier=meta.reference,
            )
            for meta in metas[:limit]
        )

    return source
