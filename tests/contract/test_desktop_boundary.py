"""Desktop sidecar boundary guards (078 T009).

``apps/desktop/sidecar/**`` may integrate the runtime only through public
``loopplane.host`` facades (including the future non-instance
``validate_active_generation`` startup validator) and may consume normalized
events via ``loopplane.events`` serialization. It must never reach through to
live checkpoint/artifact stores, controller/gateway/tools internals, or invoke
tools outside the Tool Gateway.

See FR-006, FR-020, FR-043–FR-045; SC-010; ADR 0015 D5.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_DIR = REPO_ROOT / "apps" / "desktop" / "sidecar"
SRC_ROOT = REPO_ROOT / "src" / "loopplane"

# Absolute loopplane imports the sidecar may take at runtime.
RUNTIME_ALLOWED_PREFIXES: tuple[str, ...] = (
    "loopplane.host",
    "loopplane.events",
    # Public-safe error types for wire mapping (no private payload fields).
    "loopplane.errors",
    # Host construction only: model boundary objects fed into RuntimeConfig
    # (e.g. ScriptedModel for credential-free demo / packaged smoke).
    "loopplane.model",
    # Model construction only (ADR 0016 D5): the provider adapters an in-app
    # provider setting selects. These are the embedder-facing constructors this
    # audit's `loopplane.model` entry already blesses, reached by name instead of
    # through the caller. Desktop previously loaded them with `importlib` to stay
    # off this list, which left a real edge invisible to the scan; naming the
    # prefix keeps the rule a description of the system (constitution VII/VIII).
    "loopplane.adapters",
)

# TYPE_CHECKING-only extras (keep empty for now; host/events cover typing).
TYPE_ONLY_ALLOWED_PREFIXES: tuple[str, ...] = RUNTIME_ALLOWED_PREFIXES

# Live-store / internal surfaces the sidecar must never import or name.
PROHIBITED_IMPORT_PREFIXES: tuple[str, ...] = (
    "loopplane.checkpoint",
    "loopplane.controller",
    "loopplane.gateway",
    "loopplane.tools",
    "loopplane.artifacts",
    "loopplane.memory",
    "loopplane.loop",
)

PROHIBITED_TOKENS: tuple[str, ...] = (
    "ArtifactStore",
    "CheckpointStore",
    "FileCheckpointStore",
    "SqliteCheckpointStore",
    "RuntimeController",
    "ToolGateway",
    ".invoke(",
    "sqlite3.connect",
    # Live store constructors / open paths.
    "open_checkpoint",
    "ArtifactStore(",
)

# Startup storage validation must go through this public host facade only
# (implemented in T025). Direct store construction is still prohibited.
ALLOWED_GENERATION_VALIDATOR = "validate_active_generation"


def _sidecar_py_files() -> list[Path]:
    if not SIDECAR_DIR.is_dir():
        return []
    return sorted(
        path
        for path in SIDECAR_DIR.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    )


def _is_type_checking_test(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _collect_imports(
    node: ast.AST,
    *,
    type_checking: bool = False,
    out: list[tuple[str, int, bool]],
) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append((alias.name, node.lineno, type_checking))
        return
    if isinstance(node, ast.ImportFrom):
        if node.module:
            out.append((node.module, node.lineno, type_checking))
        return
    if isinstance(node, ast.If) and _is_type_checking_test(node.test):
        for sub in node.body:
            _collect_imports(sub, type_checking=True, out=out)
        for sub in node.orelse:
            _collect_imports(sub, type_checking=type_checking, out=out)
        return
    for child in ast.iter_child_nodes(node):
        _collect_imports(child, type_checking=type_checking, out=out)


def _imports_of(path: Path) -> list[tuple[str, int, bool]]:
    collected: list[tuple[str, int, bool]] = []
    _collect_imports(ast.parse(path.read_text(encoding="utf-8")), out=collected)
    return collected


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in prefixes
    )


def test_sidecar_directory_exists() -> None:
    assert SIDECAR_DIR.is_dir(), "apps/desktop/sidecar must exist"


def test_sidecar_imports_only_host_and_events_public_surfaces() -> None:
    """Sidecar may import loopplane.host / events / errors only."""

    violations: list[str] = []
    for path in _sidecar_py_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        for module, lineno, type_checking in _imports_of(path):
            if not module.startswith("loopplane"):
                continue
            allowed = (
                TYPE_ONLY_ALLOWED_PREFIXES
                if type_checking
                else RUNTIME_ALLOWED_PREFIXES
            )
            if not _matches(module, allowed):
                violations.append(f"{rel}:{lineno}: imports {module}")
            if _matches(module, PROHIBITED_IMPORT_PREFIXES):
                violations.append(f"{rel}:{lineno}: prohibited import {module}")
    assert not violations, "Sidecar import boundary violations:\n" + "\n".join(
        violations
    )


def test_sidecar_has_no_live_store_or_gateway_reach_through() -> None:
    """No live SQLite/ArtifactStore/controller/gateway invoke reach-through."""

    violations: list[str] = []
    for path in _sidecar_py_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for token in PROHIBITED_TOKENS:
            if token in text:
                # Allow mentioning the validator name only.
                if token == ".invoke(" and ALLOWED_GENERATION_VALIDATOR in text:
                    # Still ban .invoke( even if validator is present.
                    pass
                violations.append(f"{rel}: references {token!r}")
    assert not violations, "Sidecar live-store reach-through:\n" + "\n".join(violations)


def test_generation_validation_must_use_public_host_facade_only() -> None:
    """If generation validation appears, it must be host.validate_active_generation.

    Direct store open/create paths remain prohibited (covered above). This test
    documents the only sanctioned startup-validation name for T025+.
    """

    for path in _sidecar_py_files():
        text = path.read_text(encoding="utf-8")
        if "absent_uninitialized" in text or "active_generation" in text:
            assert ALLOWED_GENERATION_VALIDATOR in text, (
                f"{path}: generation validation must call "
                f"loopplane.host.{ALLOWED_GENERATION_VALIDATOR}"
            )


def test_tools_boundary_guard_still_present() -> None:
    """Preserve the tools-layer import guard module (T009 non-regression)."""

    tools_boundary = REPO_ROOT / "tests" / "contract" / "test_tools_boundary.py"
    assert tools_boundary.is_file()
    text = tools_boundary.read_text(encoding="utf-8")
    assert "RUNTIME_ALLOWED_PREFIXES" in text
    assert "loopplane.gateway.spi" in text


def test_sidecar_has_no_tool_invoke_outside_gateway() -> None:
    """Extend the sole invoke-execution audit to the desktop sidecar tree."""

    offenders: list[str] = []
    for path in _sidecar_py_files():
        source = path.read_text(encoding="utf-8")
        if ".invoke(" in source or ".handler(" in source:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []
