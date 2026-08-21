"""Boundary for the CLI host (T014; FR-008; extended by 079 T066): the CLI
composes only the public host surfaces, reaches no runtime internal, and keeps
its optional network capability out of module import."""

from __future__ import annotations

import ast
import re
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
)

# The CLI must not SERIALIZE events — emitting frames is the web transport's job,
# and a consumer that re-emits the bus would cross Constitution VI. Reading an
# already-serialized frame back (079's remote client) is the opposite direction
# and is how the remote path reuses the one renderer, so `deserialize_event` is
# allowed and only the bare `serialize_event` is refused.
_SERIALIZE_CALL = re.compile(r"(?<!de)serialize_event")

# 079: the optional network capability must never be imported at module import
# time — the terminal has to keep working with only the base dependencies.
_MODULE_LEVEL_HTTPX = re.compile(r"^\s{0,3}(import httpx|from httpx\b)", re.MULTILINE)


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
        if _SERIALIZE_CALL.search(text):
            violations.append(f"{path.name}: references 'serialize_event'")
    assert not violations, violations


def test_cli_never_imports_the_optional_network_capability_at_module_level() -> None:
    """`httpx` is lazy inside the remote module, so importing the CLI with only
    the base dependencies installed still works (079 FR-030, FR-031)."""

    violations: list[str] = []
    for path in sorted(CLI_DIR.glob("*.py")):
        for node in ast.iter_child_nodes(ast.parse(path.read_text(encoding="utf-8"))):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module == "httpx" or module.startswith("httpx."):
                    violations.append(f"{path.name}: imports {module} at module level")
    assert not violations, violations


def test_boundary_guard_detects_a_violation() -> None:
    """Negative self-check: the guards must actually catch what they claim to.

    Without this, a regex that silently stopped matching would leave every other
    assertion here passing on nothing.
    """

    assert _SERIALIZE_CALL.search("frame = serialize_event(event)")
    assert not _SERIALIZE_CALL.search("event = deserialize_event(payload)")
    assert _MODULE_LEVEL_HTTPX.search("import httpx\n")
    assert _MODULE_LEVEL_HTTPX.search("from httpx import AsyncClient\n")
    assert not _MODULE_LEVEL_HTTPX.search("    import httpx\n")
