"""US5: malformed / unsafe plugins are handled safely
(T012; FR-008, FR-009, FR-010, FR-011, FR-012, FR-014)."""

from __future__ import annotations

from pathlib import Path

from loopplane.hooks import HookRegistry
from loopplane.plugins import PluginInfo, list_plugins, load_plugins
from tests.plugins_helpers import write_plugin


def test_malformed_plugin_is_skipped_while_others_load(tmp_path: Path) -> None:
    write_plugin(tmp_path, "good")
    write_plugin(tmp_path, "bad", raw="{not valid json")
    result = load_plugins([tmp_path], enabled={"good", "bad"})
    assert [info.name for info in result.loaded] == ["good"]
    assert any("invalid" in p for p in result.problems)


def test_credential_plugin_is_skipped_without_echoing_the_secret(
    tmp_path: Path,
) -> None:
    write_plugin(
        tmp_path,
        "leaky",
        raw='{"name": "leaky", "version": "1",'
        ' "mcp_servers": {"x": {"transport": "http", "url": "https://h?api_key=do-not-echo-me"}}}',
    )
    result = load_plugins([tmp_path], enabled={"leaky"})
    assert result.loaded == ()
    blob = " ".join(result.problems)
    assert "credential" in blob
    assert "do-not-echo-me" not in blob  # the diagnostic never echoes the value


def test_enabled_name_with_no_match_is_noted_not_raised(tmp_path: Path) -> None:
    result = load_plugins([tmp_path], enabled={"ghost"})
    assert result.loaded == ()
    assert any("ghost" in p and "not found" in p for p in result.problems)


def test_bad_hook_target_is_skipped_not_fatal(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        "h",
        hooks=[{"point": "model_stop", "target": "no.such.module:f"}],
    )
    result = load_plugins([tmp_path], enabled={"h"}, hook_registry=HookRegistry())
    assert result.hook_count == 0
    assert any("importable" in p for p in result.problems)
    assert [info.name for info in result.loaded] == ["h"]  # the plugin still loads


def test_cross_root_collision_resolves_by_precedence(tmp_path: Path) -> None:
    write_plugin(tmp_path / "broad", "p", version="1.0.0")
    write_plugin(tmp_path / "specific", "p", version="2.0.0")
    result = load_plugins([tmp_path / "broad", tmp_path / "specific"], enabled={"p"})
    assert [info.version for info in result.loaded] == ["2.0.0"]  # later root wins
    assert any("shadowed" in p for p in result.problems)


def test_listing_is_metadata_only(tmp_path: Path) -> None:
    write_plugin(tmp_path, "a", version="2.0.0", skills=["skills"])
    infos = list_plugins([tmp_path], enabled={"a"})
    assert len(infos) == 1
    assert infos[0].name == "a"
    assert infos[0].version == "2.0.0"
    assert infos[0].enabled is True
    assert set(PluginInfo.__dataclass_fields__) == {
        "name",
        "version",
        "enabled",
        "skill_dir_count",
        "mcp_server_count",
        "hook_count",
    }
