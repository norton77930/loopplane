"""Deterministic, public-safe helpers for the plugin-system suites (feature 016).

Includes an importable hook target (`tests.plugins_helpers:sample_hook`) so the
loader's bounded hook-import seam can be exercised end-to-end.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

# A module-level sink the sample hook appends to (for US4 assertions).
HOOK_CALLS: list[str] = []


def sample_hook(payload: object) -> None:
    HOOK_CALLS.append(getattr(payload, "tool_name", "?"))


def write_plugin(
    root: Path,
    name: str,
    *,
    version: str = "1.0.0",
    skills: Sequence[str] | None = None,
    mcp_servers: Mapping[str, Mapping[str, object]] | None = None,
    hooks: Sequence[Mapping[str, str]] | None = None,
    raw: str | None = None,
) -> Path:
    """Create a plugin directory with a plugin.json (or a verbatim `raw` body)."""
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        (directory / "plugin.json").write_text(raw, encoding="utf-8")
        return directory
    manifest: dict[str, object] = {"name": name, "version": version}
    if skills is not None:
        manifest["skills"] = list(skills)
    if mcp_servers is not None:
        manifest["mcp_servers"] = dict(mcp_servers)
    if hooks is not None:
        manifest["hooks"] = [dict(h) for h in hooks]
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def write_skill(plugin_dir: Path, subdir: str, skill_name: str) -> None:
    """Write one valid skill JSON inside a plugin's skill directory."""
    skill_dir = plugin_dir / subdir
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / f"{skill_name}.json").write_text(
        json.dumps(
            {"name": skill_name, "description": "demo skill", "instructions": "do it"}
        ),
        encoding="utf-8",
    )
