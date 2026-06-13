"""US2: recall the artifacts the loop produced (spec US2; SC-007)."""

from __future__ import annotations

from loopplane.recall import artifact_recall
from tests.recall_helpers import (
    ScriptedArtifactReader,
    artifact_meta,
    artifact_ref,
    scripted_state,
)


def test_artifact_recall_is_newest_first() -> None:
    state = scripted_state(artifacts=[artifact_ref("s", "a1"), artifact_ref("s", "a2")])
    reader = ScriptedArtifactReader(
        [artifact_meta("s", "a1", day=1), artifact_meta("s", "a2", day=3)]
    )
    entries = artifact_recall(reader)(state)
    assert [e.identifier for e in entries] == ["a2", "a1"]
    assert all(e.origin == "artifact" for e in entries)


def test_artifact_recall_surfaces_public_safe_metadata_only() -> None:
    state = scripted_state(artifacts=[artifact_ref("s", "a1")])
    reader = ScriptedArtifactReader(
        [artifact_meta("s", "a1", day=1, size=42, media_kind="text")]
    )
    text = artifact_recall(reader)(state)[0].text
    assert "a1" in text and "42" in text and "text" in text
    # No raw content, no Windows or POSIX filesystem path.
    assert ":\\" not in text and "/home/" not in text


def test_artifact_recall_skips_missing_metadata() -> None:
    state = scripted_state(
        artifacts=[artifact_ref("s", "a1"), artifact_ref("s", "missing")]
    )
    reader = ScriptedArtifactReader([artifact_meta("s", "a1", day=1)])
    entries = artifact_recall(reader)(state)
    assert [e.identifier for e in entries] == ["a1"]


def test_artifact_recall_raising_reader_is_fail_safe() -> None:
    state = scripted_state(artifacts=[artifact_ref("s", "a1")])
    assert artifact_recall(ScriptedArtifactReader(raising=True))(state) == ()


def test_artifact_recall_no_artifacts_is_empty() -> None:
    assert artifact_recall(ScriptedArtifactReader())(scripted_state()) == ()


def test_artifact_recall_does_not_mutate_state() -> None:
    state = scripted_state(artifacts=[artifact_ref("s", "a1")])
    before = state.artifacts
    artifact_recall(ScriptedArtifactReader([artifact_meta("s", "a1")]))(state)
    assert state.artifacts == before
