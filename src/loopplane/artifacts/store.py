"""Artifact Storage: oversized tool output preserved in full as sidecar
files, retrievable by a stable reference after the run (contracts/artifacts.md;
FR-090, FR-091, FR-093).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loopplane.context import RunContext
from loopplane.gateway.gateway import ArtifactHandoff
from loopplane.model.boundary import ToolCallRequest
from loopplane.model.content import OutputBlock, TextBlock

_ARTIFACT_DIR = "artifacts"


@dataclass(frozen=True)
class ArtifactMeta:
    reference: str
    session_id: str
    call_id: str
    size: int
    media_kind: Literal["text", "image", "binary"]
    created_at: datetime


class ArtifactStore:
    def __init__(self, base_dir: Path, *, preview_chars: int = 1024) -> None:
        self._base = base_dir
        self._preview_chars = preview_chars

    def _directory(self, session_id: str) -> Path:
        return self._base / session_id / _ARTIFACT_DIR

    async def offload(
        self, *, session_id: str, call_id: str, outputs: Sequence[OutputBlock]
    ) -> tuple[str, str]:
        """Persist the full content; return (stable reference, bounded
        preview) for the in-conversation representation (FR-090, FR-091).
        """
        content = "\n".join(
            block.text for block in outputs if isinstance(block, TextBlock)
        )
        data = content.encode("utf-8")
        reference = uuid.uuid4().hex
        directory = self._directory(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{reference}.txt").write_bytes(data)
        metadata = {
            "reference": reference,
            "session_id": session_id,
            "call_id": call_id,
            "size": len(data),
            "media_kind": "text",
            "created_at": datetime.now(UTC).isoformat(),
        }
        (directory / f"{reference}.meta.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        preview = content[: self._preview_chars]
        if len(content) > self._preview_chars:
            preview += (
                f"\n[preview only: the full {len(data)}-byte output is stored "
                f"as artifact {reference}]"
            )
        return reference, preview

    def retrieve(self, session_id: str, reference: str) -> str | None:
        """Content by reference; unknown references are a normal not-found,
        never a crash (FR-093).
        """
        path = self._directory(session_id) / f"{reference}.txt"
        if not path.is_file():
            return None
        return path.read_bytes().decode("utf-8")

    def metadata(self, session_id: str, reference: str) -> ArtifactMeta | None:
        path = self._directory(session_id) / f"{reference}.meta.json"
        if not path.is_file():
            return None
        document = json.loads(path.read_text("utf-8"))
        return ArtifactMeta(
            reference=document["reference"],
            session_id=document["session_id"],
            call_id=document["call_id"],
            size=document["size"],
            media_kind=document["media_kind"],
            created_at=datetime.fromisoformat(document["created_at"]),
        )


def make_artifact_handoff(store: ArtifactStore) -> ArtifactHandoff:
    """Bind an ArtifactStore as the Gateway's offload seam (FR-090)."""

    async def handoff(
        call: ToolCallRequest, outputs: list[OutputBlock], context: RunContext
    ) -> tuple[str, str]:
        return await store.offload(
            session_id=context.session_id, call_id=call.call_id, outputs=outputs
        )

    return handoff
