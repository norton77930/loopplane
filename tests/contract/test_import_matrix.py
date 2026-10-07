"""Default-deny import matrix contract (082 US5; R10).

This is static analysis only: optional package availability cannot affect it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "loopplane"


@dataclass(frozen=True)
class BoundaryMatrixEntry:
    allow_runtime: frozenset[str]
    allow_type_checking: frozenset[str]
    allow_function_scoped: frozenset[str]
    notes: str


def _entry(
    *,
    runtime: tuple[str, ...],
    type_checking: tuple[str, ...],
    function_scoped: tuple[str, ...],
    notes: str,
) -> BoundaryMatrixEntry:
    return BoundaryMatrixEntry(
        allow_runtime=frozenset(runtime),
        allow_type_checking=frozenset(type_checking),
        allow_function_scoped=frozenset(function_scoped),
        notes=notes,
    )


# Current source and the existing boundary guards take precedence where the
# architecture document is less specific. Every entry declares all three scopes.
MATRIX: dict[str, BoundaryMatrixEntry] = {
    "__init__": _entry(
        runtime=(), type_checking=(), function_scoped=(), notes="root API"
    ),
    "adapters": _entry(
        runtime=(
            "loopplane.adapters",
            "loopplane.context",
            "loopplane.errors",
            "loopplane.gateway.spi",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §8",
    ),
    "approval": _entry(
        runtime=(
            "loopplane.approval",
            "loopplane.context",
            "loopplane.events",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1",
    ),
    "artifacts": _entry(
        runtime=(
            "loopplane.artifacts",
            "loopplane.context",
            "loopplane.gateway",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1",
    ),
    "budget": _entry(
        runtime=("loopplane.ledger", "loopplane.model", "loopplane.pricing"),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1",
    ),
    "checkpoint": _entry(
        runtime=(
            "loopplane.checkpoint",
            "loopplane.errors",
            "loopplane.events",
            "loopplane.loop",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1 / G3",
    ),
    "cli": _entry(
        runtime=(
            "loopplane.cli",
            "loopplane.commands",
            "loopplane.events",
            "loopplane.host",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §2",
    ),
    "commands": _entry(
        runtime=(), type_checking=(), function_scoped=(), notes="TARGET §2"
    ),
    "context": _entry(
        runtime=(),
        type_checking=(
            "loopplane.approval.interactions",
            "loopplane.tools.background",
            "loopplane.tools.messaging",
            "loopplane.tools.scheduling",
            "loopplane.tools.worktree",
        ),
        function_scoped=(),
        notes="TARGET §1 / R1 TYPE_CHECKING-only",
    ),
    "controller": _entry(
        runtime=(
            "loopplane.approval",
            "loopplane.artifacts",
            "loopplane.budget",
            "loopplane.checkpoint",
            "loopplane.context",
            "loopplane.controller",
            "loopplane.events",
            "loopplane.fairness",
            "loopplane.gateway",
            "loopplane.hooks",
            "loopplane.ledger",
            "loopplane.loop",
            "loopplane.memory",
            "loopplane.model",
            "loopplane.pricing",
            "loopplane.skills",
        ),
        type_checking=("loopplane.context",),
        function_scoped=(),
        notes="TARGET §1 / G1-G3",
    ),
    "engineering": _entry(
        runtime=(
            "loopplane.engineering",
            "loopplane.events",
            "loopplane.host",
            "loopplane.model",
        ),
        type_checking=("loopplane.engineering", "loopplane.host"),
        function_scoped=(),
        notes="TARGET §5; test_engineering_boundary.py",
    ),
    "errors": _entry(
        runtime=(), type_checking=(), function_scoped=(), notes="TARGET §1"
    ),
    "events": _entry(
        runtime=("loopplane.errors", "loopplane.events", "loopplane.model"),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1 / G2",
    ),
    "fairness": _entry(
        runtime=("loopplane.fairness_permits",),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1; 086 injects permit stores",
    ),
    "fairness_permits": _entry(
        runtime=(),
        type_checking=(),
        function_scoped=(),
        notes="086 turn-permit Protocol + in-memory store",
    ),
    "fairness_postgres": _entry(
        runtime=("loopplane.fairness_permits",),
        type_checking=(),
        function_scoped=(),
        notes="086 optional postgres turn permits; lazy psycopg",
    ),
    "fairness_weighted": _entry(
        runtime=("loopplane.fairness", "loopplane.fairness_permits"),
        type_checking=(),
        function_scoped=(),
        notes="087 opt-in weighted fairness; Phase-1 composition and permit state",
    ),
    "fairness_weighted_postgres": _entry(
        runtime=("loopplane.fairness_permits", "loopplane.fairness_weighted"),
        type_checking=(),
        function_scoped=(),
        notes="087 isolated weighted coordination; lazy existing postgres extra",
    ),
    "gateway": _entry(
        runtime=(
            "loopplane.approval",
            "loopplane.context",
            "loopplane.errors",
            "loopplane.events",
            "loopplane.gateway",
            "loopplane.hooks",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1 / G1",
    ),
    "governance": _entry(
        runtime=(
            "loopplane.approval",
            "loopplane.context",
            "loopplane.events",
            "loopplane.governance",
            "loopplane.model",
        ),
        type_checking=(
            "loopplane.approval",
            "loopplane.context",
            "loopplane.events",
            "loopplane.model",
        ),
        function_scoped=(),
        notes="TARGET §6; test_governance_boundary.py",
    ),
    "hooks": _entry(
        runtime=("loopplane.hooks",),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1",
    ),
    "host": _entry(
        runtime=(
            "loopplane.approval",
            "loopplane.artifacts",
            "loopplane.budget",
            "loopplane.checkpoint",
            "loopplane.context",
            "loopplane.controller",
            "loopplane.errors",
            "loopplane.events",
            "loopplane.fairness",
            "loopplane.gateway",
            "loopplane.governance",
            "loopplane.host",
            "loopplane.ledger",
            "loopplane.loop",
            "loopplane.memory",
            "loopplane.model",
            "loopplane.observability",
            "loopplane.pricing",
            "loopplane.skills",
        ),
        type_checking=(
            "loopplane.context",
            "loopplane.events",
            "loopplane.host",
            "loopplane.tools.messaging",
            "loopplane.tools.subagent",
        ),
        function_scoped=(
            "loopplane.engineering",
            "loopplane.host",
            "loopplane.packs",
            "loopplane.tools.background",
            "loopplane.tools.messaging",
            "loopplane.tools.scheduling",
            "loopplane.tools.subagent",
            "loopplane.tools.worktree",
        ),
        notes=(
            "TARGET §2 / R4 assembly lazy-import seam; "
            "managed-MCP exception is file-scoped"
        ),
    ),
    "inspect": _entry(
        runtime=("loopplane.engineering", "loopplane.events", "loopplane.inspect"),
        type_checking=(
            "loopplane.engineering",
            "loopplane.events",
            "loopplane.inspect",
        ),
        function_scoped=(),
        notes="TARGET appendix; test_inspect_boundary.py",
    ),
    "ledger": _entry(
        runtime=("loopplane.ledger",),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §11 / G3",
    ),
    "loop": _entry(
        runtime=(
            "loopplane.budget",
            "loopplane.context",
            "loopplane.events",
            "loopplane.fairness",
            "loopplane.gateway",
            "loopplane.hooks",
            "loopplane.loop",
            "loopplane.model",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1 / G1-G2",
    ),
    "memory": _entry(
        runtime=("loopplane.memory",),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1 / G3",
    ),
    "model": _entry(
        runtime=("loopplane.errors", "loopplane.model"),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §1",
    ),
    "observability": _entry(
        runtime=("loopplane.errors", "loopplane.events"),
        type_checking=(),
        function_scoped=("loopplane.observability",),
        notes="TARGET §10 / G4",
    ),
    "orchestration": _entry(
        runtime=("loopplane.engineering", "loopplane.hooks", "loopplane.orchestration"),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §5; test_orchestration_boundary.py",
    ),
    "packs": _entry(
        runtime=(
            "loopplane.engineering",
            "loopplane.host",
            "loopplane.model",
            "loopplane.packs",
        ),
        type_checking=("loopplane.engineering", "loopplane.host"),
        function_scoped=(),
        notes="test_packs_boundary.py",
    ),
    "plugins": _entry(
        runtime=("loopplane.hooks", "loopplane.plugins"),
        type_checking=("loopplane.hooks",),
        function_scoped=(),
        notes="TARGET appendix",
    ),
    "pricing": _entry(
        runtime=("loopplane.model",),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §12",
    ),
    "recall": _entry(
        runtime=(
            "loopplane.artifacts",
            "loopplane.engineering",
            "loopplane.memory",
            "loopplane.recall",
        ),
        type_checking=(
            "loopplane.artifacts",
            "loopplane.engineering",
            "loopplane.memory",
        ),
        function_scoped=(),
        notes="test_recall_boundary.py",
    ),
    "review": _entry(
        runtime=("loopplane.engineering", "loopplane.review"),
        type_checking=("loopplane.engineering", "loopplane.review"),
        function_scoped=(),
        notes="test_review_boundary.py",
    ),
    "scheduling": _entry(
        runtime=("loopplane.engineering", "loopplane.scheduling"),
        type_checking=("loopplane.engineering",),
        function_scoped=(),
        notes="TARGET §5; test_scheduling_boundary.py",
    ),
    "skills": _entry(
        runtime=(
            "loopplane.context",
            "loopplane.gateway.spi",
            "loopplane.model",
            "loopplane.skills",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET appendix / G1",
    ),
    "studio": _entry(
        runtime=("loopplane.host", "loopplane.studio"),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §4; test_studio_boundary.py",
    ),
    "toolkit": _entry(
        runtime=("loopplane.gateway", "loopplane.model", "loopplane.toolkit"),
        type_checking=("loopplane.gateway", "loopplane.toolkit"),
        function_scoped=(),
        notes="TARGET §9; test_toolkit_boundary.py",
    ),
    "tools": _entry(
        runtime=(
            "loopplane.context",
            "loopplane.engineering",
            "loopplane.errors",
            "loopplane.events.envelope",
            "loopplane.gateway.spi",
            "loopplane.memory.store",
            "loopplane.model",
            "loopplane.orchestration",
            "loopplane.tools",
        ),
        type_checking=("loopplane.host", "loopplane.tools"),
        function_scoped=(),
        notes=(
            "TARGET §7; test_tools_boundary.py narrow "
            "payload/SPI/store/orchestration seams"
        ),
    ),
    "webapi": _entry(
        runtime=(
            "loopplane.commands",
            "loopplane.events",
            "loopplane.host",
            "loopplane.webapi",
        ),
        type_checking=(),
        function_scoped=(),
        notes="TARGET §3; test_webapi_boundary.py",
    ),
}

# Existing composition/dependency discrepancy: the managed-MCP module owns the
# only runtime host -> adapters.mcp edge. This is not a package-wide sanctioned
# direction.
FILE_SCOPED_RUNTIME_EXCEPTIONS: dict[str, frozenset[str]] = {
    # Unit 082 T032 moved this edge out of capability_manager.py. The exception
    # names a file rather than the package on purpose, so a sanctioned import
    # cannot ride along into a new home without being re-declared here.
    "host/_capability_mcp.py": frozenset(("loopplane.adapters.mcp",)),
}


def _is_type_checking_test(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _resolve_from_import(node: ast.ImportFrom, *, package: str) -> tuple[str, ...]:
    """Resolve an ``ImportFrom`` to absolute loopplane module edge(s)."""
    if node.level == 0:
        return (node.module,) if node.module else ()

    parts = package.split(".")
    retained = len(parts) - (node.level - 1)
    if retained <= 0:
        return ()
    base = ".".join(parts[:retained])
    if node.module:
        return (f"{base}.{node.module}",)
    return tuple(f"{base}.{alias.name}" for alias in node.names)


def _collect_imports(
    node: ast.AST,
    *,
    collected: list[tuple[str, int, str]],
    package: str,
    scope: str = "runtime",
) -> None:
    if isinstance(node, ast.Import):
        collected.extend((alias.name, node.lineno, scope) for alias in node.names)
        return
    if isinstance(node, ast.ImportFrom):
        collected.extend(
            (module, node.lineno, scope)
            for module in _resolve_from_import(node, package=package)
        )
        return
    if isinstance(node, ast.If) and _is_type_checking_test(node.test):
        for child in node.body:
            _collect_imports(
                child,
                collected=collected,
                package=package,
                scope="type-checking",
            )
        for child in node.orelse:
            _collect_imports(child, collected=collected, package=package, scope=scope)
        return
    child_scope = (
        "function-scoped"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and scope == "runtime"
        else scope
    )
    for child in ast.iter_child_nodes(node):
        _collect_imports(child, collected=collected, package=package, scope=child_scope)


def _discover_entries(source_root: Path) -> set[str]:
    packages = {
        path.name
        for path in source_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    }
    modules = {path.stem for path in source_root.glob("*.py")}
    return packages | modules


def _entry_files(source_root: Path, entry: str) -> list[Path]:
    path = source_root / entry
    if path.is_dir():
        return sorted(path.rglob("*.py"))
    return [source_root / f"{entry}.py"]


def _package_for_path(source_root: Path, path: Path) -> str:
    relative = path.relative_to(source_root)
    return ".".join(("loopplane", *relative.parts[:-1]))


def _matches(module: str, prefixes: frozenset[str]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes
    )


def _allowed(entry: BoundaryMatrixEntry, scope: str) -> frozenset[str]:
    if scope == "type-checking":
        return entry.allow_type_checking
    if scope == "function-scoped":
        return entry.allow_function_scoped
    return entry.allow_runtime


def _validate(source_root: Path, matrix: dict[str, BoundaryMatrixEntry]) -> list[str]:
    """Return default-deny diagnostics without importing the inspected source."""
    discovered = _discover_entries(source_root)
    violations: list[str] = []
    for entry in sorted(discovered - matrix.keys()):
        path = _entry_files(source_root, entry)[0].relative_to(source_root).as_posix()
        violations.append(
            f"{path}:1: scope=declaration; import edge=loopplane.{entry}; "
            "rule=no matrix entry (default-deny)"
        )
    for entry in sorted(matrix.keys() - discovered):
        violations.append(
            "test_import_matrix.py:1: scope=declaration; "
            f"import edge=loopplane.{entry}; "
            f"rule={matrix[entry].notes}; orphan matrix entry"
        )
    for entry in sorted(discovered & matrix.keys()):
        policy = matrix[entry]
        for path in _entry_files(source_root, entry):
            relative = path.relative_to(source_root).as_posix()
            imports: list[tuple[str, int, str]] = []
            _collect_imports(
                ast.parse(path.read_text(encoding="utf-8")),
                collected=imports,
                package=_package_for_path(source_root, path),
            )
            for module, lineno, scope in imports:
                allowed = _allowed(policy, scope)
                if scope == "runtime":
                    allowed |= FILE_SCOPED_RUNTIME_EXCEPTIONS.get(relative, frozenset())
                if module.startswith("loopplane") and not _matches(module, allowed):
                    violations.append(
                        f"{relative}:{lineno}: scope={scope}; "
                        f"import edge=loopplane.{entry} -> {module}; "
                        f"rule={policy.notes}"
                    )
    return violations


def _minimal_source_root(tmp_path: Path) -> Path:
    root = tmp_path / "src" / "loopplane"
    root.mkdir(parents=True)
    for name in ("__init__", "context", "errors", "fairness"):
        (root / f"{name}.py").write_text("", encoding="utf-8")
    return root


def test_matrix_covers_every_discovered_entry_and_current_imports() -> None:
    assert _validate(SRC_ROOT, MATRIX) == []


def test_validator_rejects_a_seeded_forbidden_edge(tmp_path: Path) -> None:
    root = _minimal_source_root(tmp_path)
    (root / "alpha").mkdir()
    (root / "alpha" / "__init__.py").write_text(
        "from loopplane.beta import value\n", encoding="utf-8"
    )
    (root / "beta").mkdir()
    (root / "beta" / "__init__.py").write_text("", encoding="utf-8")
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
    }
    violations = _validate(root, matrix)
    assert violations == [
        "alpha/__init__.py:1: scope=runtime; import edge=loopplane.alpha -> "
        "loopplane.beta; rule=self-test"
    ]


def test_validator_rejects_an_undeclared_package(tmp_path: Path) -> None:
    root = _minimal_source_root(tmp_path)
    (root / "unlisted").mkdir()
    (root / "unlisted" / "__init__.py").write_text("", encoding="utf-8")
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
        if name != "unlisted"
    }
    violations = _validate(root, matrix)
    assert violations == [
        "unlisted/__init__.py:1: scope=declaration; import edge=loopplane.unlisted; "
        "rule=no matrix entry (default-deny)"
    ]


def test_validator_rejects_a_relative_cross_package_edge(tmp_path: Path) -> None:
    root = _minimal_source_root(tmp_path)
    (root / "alpha").mkdir()
    (root / "alpha" / "__init__.py").write_text(
        "from ..tools import adapter\n", encoding="utf-8"
    )
    (root / "tools").mkdir()
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
    }

    assert _validate(root, matrix) == [
        "alpha/__init__.py:1: scope=runtime; import edge=loopplane.alpha -> "
        "loopplane.tools; rule=self-test"
    ]


def test_validator_rejects_an_undeclared_top_level_module(tmp_path: Path) -> None:
    root = _minimal_source_root(tmp_path)
    (root / "unlisted_top.py").write_text("", encoding="utf-8")
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
        if name != "unlisted_top"
    }

    assert _validate(root, matrix) == [
        "unlisted_top.py:1: scope=declaration; import edge=loopplane.unlisted_top; "
        "rule=no matrix entry (default-deny)"
    ]


def test_host_mcp_runtime_exception_is_limited_to_the_managed_mcp_module(
    tmp_path: Path,
) -> None:
    root = _minimal_source_root(tmp_path)
    (root / "adapters").mkdir()
    (root / "adapters" / "__init__.py").write_text("", encoding="utf-8")
    (root / "host").mkdir()
    (root / "host" / "__init__.py").write_text("", encoding="utf-8")
    (root / "host" / "_capability_mcp.py").write_text(
        "from loopplane.adapters.mcp import MCPServerConfig\n", encoding="utf-8"
    )
    (root / "host" / "other.py").write_text(
        "from loopplane.adapters.mcp import MCPServerConfig\n", encoding="utf-8"
    )
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
    }

    assert _validate(root, matrix) == [
        "host/other.py:1: scope=runtime; import edge=loopplane.host -> "
        "loopplane.adapters.mcp; rule=self-test"
    ]


def test_validator_rejects_a_type_checking_only_edge_at_runtime(tmp_path: Path) -> None:
    root = _minimal_source_root(tmp_path)
    (root / "alpha").mkdir()
    (root / "alpha" / "__init__.py").write_text(
        "from loopplane.tools import adapter\n", encoding="utf-8"
    )
    (root / "tools").mkdir()
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
    }
    matrix["alpha"] = _entry(
        runtime=(),
        type_checking=("loopplane.tools",),
        function_scoped=(),
        notes="self-test TYPE_CHECKING-only",
    )
    violations = _validate(root, matrix)
    assert violations == [
        "alpha/__init__.py:1: scope=runtime; import edge=loopplane.alpha -> "
        "loopplane.tools; rule=self-test TYPE_CHECKING-only"
    ]


def test_validator_rejects_an_orphan_matrix_entry(tmp_path: Path) -> None:
    root = _minimal_source_root(tmp_path)
    matrix = {
        name: _entry(
            runtime=(), type_checking=(), function_scoped=(), notes="self-test"
        )
        for name in _discover_entries(root)
    }
    matrix["orphan"] = _entry(
        runtime=(), type_checking=(), function_scoped=(), notes="self-test orphan"
    )
    violations = _validate(root, matrix)
    assert violations == [
        "test_import_matrix.py:1: scope=declaration; import edge=loopplane.orphan; "
        "rule=self-test orphan; orphan matrix entry"
    ]
