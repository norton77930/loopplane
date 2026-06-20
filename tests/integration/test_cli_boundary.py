"""Boundary for the CLI host (T014; FR-008): the CLI composes only the public host
surfaces and reaches no runtime internal."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_DIR = REPO_ROOT / "src" / "loopplane" / "cli"

# The CLI is a thin host: it composes loopplane.host, names the loopplane.model
# boundary, and renders loopplane.events — nothing else from the runtime.
ALLOWED_PREFIXES = (
    "loopplane.cli",
    "loopplane.host",
    "loopplane.model",
    "loopplane.events",
    # 065: the backend slash-command surface — a host UX layer over existing host
    # seams (not a runtime internal; it never reaches the controller/gateway/loop).
    "loopplane.commands",
)
PROHIBITED_TOKENS = (
    "ToolGateway",
    "RuntimeController",
    "EventEmitter",
    "serialize_event",
)


def test_cli_imports_only_the_public_host_surfaces() -> None:
    violations: list[str] = []
    for path in sorted(CLI_DIR.glob("*.py")):
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


def test_cli_references_no_runtime_internal() -> None:
    violations: list[str] = []
    for path in sorted(CLI_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                violations.append(f"{path.name}: references {token!r}")
    assert not violations, violations
