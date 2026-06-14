"""Boundary and public-safety for the plugin system (T013/T014; FR-010, FR-013)."""

from __future__ import annotations

import ast
from pathlib import Path

from loopplane.plugins import load_plugins
from tests.plugins_helpers import write_plugin

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_DIR = REPO_ROOT / "src" / "loopplane" / "plugins"

# The plugin system only *imports* the hook layer (for LifecyclePoint); it feeds
# skills/MCP back to the host as data, so it never imports those units (FR-013).
ALLOWED_PREFIXES = ("loopplane.plugins", "loopplane.hooks")
PROHIBITED_TOKENS = (
    "ToolGateway",
    "EventEmitter",
    "RuntimeController",
    "serialize_event",
)


def test_plugins_imports_only_the_hook_layer_from_the_runtime() -> None:
    violations: list[str] = []
    for path in sorted(PLUGINS_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.startswith("loopplane") and not any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in ALLOWED_PREFIXES
                ):
                    violations.append(f"{path.name}: imports {module}")
    assert not violations, violations


def test_plugins_references_no_runtime_internal() -> None:
    violations: list[str] = []
    for path in sorted(PLUGINS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token!r}")
    assert not violations, violations


def test_diagnostics_and_listing_carry_no_secret(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        "leaky",
        raw='{"name": "leaky", "version": "1",'
        ' "mcp_servers": {"x": {"transport": "http", "url": "https://h?password=do-not-echo-me"}}}',
    )
    result = load_plugins([tmp_path], enabled={"leaky"})
    assert "do-not-echo-me" not in " ".join(result.problems)
