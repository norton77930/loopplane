"""Unit tests for the plugin manifest (T002; FR-002, FR-010)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from loopplane.plugins import HookEntry, PluginManifest
from loopplane.plugins.manifest import parse_manifest


def test_manifest_requires_name_and_version() -> None:
    with pytest.raises(ValidationError):
        PluginManifest(version="1.0.0")  # type: ignore[call-arg]
    manifest = PluginManifest(name="p", version="1.0.0")
    assert manifest.skills == ()
    assert manifest.mcp_servers == {}
    assert manifest.hooks == ()


def test_manifest_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        parse_manifest('{"name": "p", "version": "1", "bogus": true}')


def test_manifest_parses_contributions() -> None:
    manifest = parse_manifest(
        '{"name": "p", "version": "1", "skills": ["s"],'
        ' "mcp_servers": {"x": {"transport": "http", "url": "https://h"}},'
        ' "hooks": [{"point": "model_stop", "target": "m:f"}]}'
    )
    assert manifest.skills == ("s",)
    assert manifest.mcp_servers == {"x": {"transport": "http", "url": "https://h"}}
    assert manifest.hooks == (HookEntry(point="model_stop", target="m:f"),)


def test_hook_entry_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        HookEntry(point="p", target="t", extra="x")  # type: ignore[call-arg]
