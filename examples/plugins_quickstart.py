"""Runnable example: discover, enable, and load a plugin (unit 016).

Public-safe and credential-free. A demo plugin is written to a temporary directory,
then discovered and loaded; its contributions are collected for the existing seams —
skill directories (for ``loopplane.skills.load_skills``), a namespaced MCP layer
(for ``loopplane.adapters.mcp.merge_layers``), and hooks (registered on a
``HookRegistry``). With an empty enable-list nothing is collected.

Run::

    python examples/plugins_quickstart.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from loopplane.hooks import HookRegistry
from loopplane.plugins import list_plugins, load_plugins


def _write_demo_plugin(root: Path) -> None:
    plugin = root / "greeter"
    (plugin / "skills").mkdir(parents=True)
    (plugin / "skills" / "greet.json").write_text(
        json.dumps({"name": "greet", "description": "demo", "instructions": "say hi"}),
        encoding="utf-8",
    )
    (plugin / "plugin.json").write_text(
        json.dumps(
            {
                "name": "greeter",
                "version": "1.0.0",
                "skills": ["skills"],
                "mcp_servers": {
                    "docs": {"transport": "http", "url": "https://example.invalid/mcp"}
                },
            }
        ),
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_demo_plugin(root)

        # Read-only listing — public-safe, counts only.
        for info in list_plugins([root], enabled={"greeter"}):
            print(
                f"discovered {info.name} v{info.version} "
                f"enabled={info.enabled} skills={info.skill_dir_count} "
                f"mcp={info.mcp_server_count}"
            )

        # Load the enabled plugin and collect its contributions.
        registry = HookRegistry()
        result = load_plugins([root], enabled={"greeter"}, hook_registry=registry)
        print("skill dirs:", [p.name for p in result.skill_dirs])
        print("mcp layer:", sorted(result.mcp_layer))  # ['greeter__docs']
        print("hooks registered:", result.hook_count)
        print("problems:", result.problems)

        # Empty enable-list is inert.
        empty = load_plugins([root], enabled=set())
        print(
            "inert with empty enable-list:", not empty.loaded and not empty.skill_dirs
        )


if __name__ == "__main__":
    main()
