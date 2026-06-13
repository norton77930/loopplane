"""Boundary and cross-cutting contract tests for the toolkit layer
(008; NFR-001, NFR-003, NFR-006, SC-002/005/007).

The layer composes only the public Phase-1 tool contracts, never imports the
concrete Tool Gateway or a runtime internal, never invokes a tool, and registers
only through the gateway's public ``register_adapter`` (Constitution V).
"""

from __future__ import annotations

import ast
from pathlib import Path

from loopplane.toolkit import (
    ToolPackage,
    ToolPlugin,
    discover,
    register_plugin,
)
from tests.toolkit_helpers import (
    RecordingRegistrar,
    ScriptedToolAdapter,
    tool_descriptor,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLKIT_DIR = REPO_ROOT / "src" / "loopplane" / "toolkit"

ALLOWED_PREFIXES = ("loopplane.gateway", "loopplane.model", "loopplane.toolkit")
PROHIBITED_IMPORT_NAMES = ("ToolGateway", "ToolHandler")


def _toolkit_modules() -> list[Path]:
    return sorted(TOOLKIT_DIR.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_toolkit_imports_only_public_tool_contracts() -> None:
    violations: list[str] = []
    for path in _toolkit_modules():
        for node in ast.walk(_parsed(path)):
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
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_toolkit_does_not_import_the_concrete_gateway() -> None:
    violations: list[str] = []
    for path in _toolkit_modules():
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in PROHIBITED_IMPORT_NAMES:
                        violations.append(f"{path.name}: imports {alias.name}")
    assert not violations, "Imports the concrete gateway:\n" + "\n".join(violations)


def test_toolkit_never_invokes_a_tool() -> None:
    violations: list[str] = []
    for path in _toolkit_modules():
        if ".invoke(" in path.read_text(encoding="utf-8"):
            violations.append(f"{path.name}: references .invoke(")
    assert not violations, "Invokes a tool:\n" + "\n".join(violations)


def test_registration_goes_only_through_register_adapter() -> None:
    first = ScriptedToolAdapter([tool_descriptor("a", source="s")])
    second = ScriptedToolAdapter([tool_descriptor("b", source="s")])
    plugin = ToolPlugin(
        name="p",
        package=ToolPackage("p", "1.0.0"),
        adapters=(first, second),
    )
    registrar = RecordingRegistrar()
    register_plugin(plugin, registrar)
    # Each adapter handed to register_adapter exactly once; nothing invoked.
    assert registrar.registered == [first, second]


def test_discovery_is_deterministic() -> None:
    adapter = ScriptedToolAdapter(
        [tool_descriptor("b", source="s"), tool_descriptor("a", source="s")]
    )
    assert discover([adapter]) == discover([adapter])
