"""Unit tests for plugin discovery (T003; FR-001, FR-008, FR-009, FR-010)."""

from __future__ import annotations

from pathlib import Path

from loopplane.plugins.discovery import discover
from tests.plugins_helpers import write_plugin


def test_discovers_a_valid_plugin(tmp_path: Path) -> None:
    write_plugin(tmp_path, "greeter")
    found = discover([tmp_path])
    assert len(found) == 1
    assert found[0].manifest is not None
    assert found[0].manifest.name == "greeter"


def test_ignores_a_directory_without_a_manifest(tmp_path: Path) -> None:
    (tmp_path / "notaplugin").mkdir()
    assert discover([tmp_path]) == []


def test_unparseable_manifest_is_skipped_not_raised(tmp_path: Path) -> None:
    write_plugin(tmp_path, "broken", raw="{not valid json")
    found = discover([tmp_path])
    assert len(found) == 1
    assert found[0].manifest is None
    assert found[0].problem is not None


def test_credential_bearing_manifest_is_rejected(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        "leaky",
        raw='{"name": "leaky", "version": "1",'
        ' "mcp_servers": {"x": {"transport": "http", "url": "https://h?api_key=demo"}}}',
    )
    found = discover([tmp_path])
    assert found[0].manifest is None
    assert found[0].problem is not None
    assert "credential" in found[0].problem


def test_missing_root_is_skipped(tmp_path: Path) -> None:
    assert discover([tmp_path / "does-not-exist"]) == []
