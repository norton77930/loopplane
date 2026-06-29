"""074 US2: additive session parity metadata on checkpoint summaries."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loopplane.checkpoint import FileCheckpointStore, SessionMetaRecord
from loopplane.checkpoint.sqlite import SqliteCheckpointStore

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 6, 29, 0, 0, 0, tzinfo=UTC)


def _meta(session_id: str) -> SessionMetaRecord:
    return SessionMetaRecord(
        session_id=session_id,
        sequence=1,
        recorded_at=_NOW,
        payload={"created_at": _NOW, "label": "Base", "principal_id": "alice"},
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda root: FileCheckpointStore(root / "file"),
        lambda root: SqliteCheckpointStore(root / "sqlite" / "checkpoint.db"),
    ],
)
async def test_checkpoint_summaries_include_session_parity_metadata(
    tmp_path: Path,
    factory: Callable[[Path], object],
) -> None:
    store = factory(tmp_path)
    await store.append(_meta("s1"))  # type: ignore[attr-defined]

    await store.update_session_metadata(  # type: ignore[attr-defined]
        "s1",
        model="model-a",
        starred=True,
        forked_from_session_id="source-1",
        forked_from_sequence=7,
    )

    [summary] = store.list_sessions()  # type: ignore[attr-defined]
    assert summary.model == "model-a"
    assert summary.starred is True
    assert summary.forked_from_session_id == "source-1"
    assert summary.forked_from_sequence == 7
