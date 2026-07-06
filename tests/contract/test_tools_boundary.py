"""Boundary contract tests for the built-in tools layer and its two seams
(TARGET_ARCHITECTURE_BOUNDARIES.md §7; RISK_REGISTER.md R1).

Two directions of one boundary:

* Outbound — what ``loopplane.tools`` may import: the gateway SPI (never
  gateway internals — G1), Phase-1 public surfaces, the ``engineering``
  public surface (§7), and the ``orchestration`` public surface sanctioned by
  ``specs/043-dynamic-subagents/contracts/spawn-subagent.md`` for the
  dynamic-subagent path only. ``loopplane.host`` is type-only (the
  supervisors name ``LoopPlaneHost`` for factory typing — specs 048/050 —
  never a runtime edge).
* Inbound — who may import ``loopplane.tools``: only ``context.py``
  (TYPE_CHECKING-only) and ``host/assembly.py`` (TYPE_CHECKING or
  function-scoped lazy — the single wiring seam, R4).

The G1 execution audit (no ``.invoke(`` outside the gateway) lives in
``tests/contract/test_tool_gateway.py`` and is intentionally not repeated.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "loopplane"
TOOLS_DIR = SRC_ROOT / "tools"

# Runtime imports the tools layer may take (module-prefix allow-list).
RUNTIME_ALLOWED_PREFIXES = (
    "loopplane.tools",
    # SPI only — the stage pipeline in loopplane.gateway.gateway stays out of
    # reach (G1: adapters never see policy/timeouts/size/events).
    "loopplane.gateway.spi",
    "loopplane.model",
    "loopplane.context",
    "loopplane.errors",
    # Phase-1 public payload/store surfaces used by the internal tools
    # (ask_question's Question envelope; the memory tools' backing store).
    "loopplane.events.envelope",
    "loopplane.memory.store",
    # Sanctioned by §7: SpawnSubagentAdapter launches through run_loop only.
    "loopplane.engineering",
    # Sanctioned by specs/043-dynamic-subagents/contracts/spawn-subagent.md:
    # aggregate_events / SubagentResult / ChildRunReference for the
    # dynamic-subagent path. This edge must stay narrow.
    "loopplane.orchestration",
)
# Additionally allowed under ``if TYPE_CHECKING:`` only.
TYPE_ONLY_ALLOWED_PREFIXES = RUNTIME_ALLOWED_PREFIXES + ("loopplane.host",)

CONTEXT_PROTOCOLS = (
    "BackgroundSupervisor",
    "ScheduleSupervisor",
    "SwarmSupervisor",
    "WorktreeManager",
)


def _is_type_checking_test(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _collect_imports(
    node: ast.AST,
    *,
    type_checking: bool = False,
    in_function: bool = False,
    out: list[tuple[str, int, bool, bool]],
) -> None:
    """Record every absolute import as (module, lineno, type_checking, in_function)."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append((alias.name, node.lineno, type_checking, in_function))
        return
    if isinstance(node, ast.ImportFrom):
        if node.module:  # relative imports (module=None) stay in-package
            out.append((node.module, node.lineno, type_checking, in_function))
        return
    if isinstance(node, ast.If) and _is_type_checking_test(node.test):
        for sub in node.body:
            _collect_imports(sub, type_checking=True, in_function=in_function, out=out)
        for sub in node.orelse:
            _collect_imports(
                sub, type_checking=type_checking, in_function=in_function, out=out
            )
        return
    scoped = in_function or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    for child in ast.iter_child_nodes(node):
        _collect_imports(
            child, type_checking=type_checking, in_function=scoped, out=out
        )


def _imports_of(path: Path) -> list[tuple[str, int, bool, bool]]:
    collected: list[tuple[str, int, bool, bool]] = []
    _collect_imports(
        ast.parse(path.read_text(encoding="utf-8")),
        out=collected,
    )
    return collected


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in prefixes
    )


def test_tools_imports_only_sanctioned_surfaces() -> None:
    violations: list[str] = []
    for path in sorted(TOOLS_DIR.rglob("*.py")):
        for module, lineno, type_checking, _ in _imports_of(path):
            if not module.startswith("loopplane"):
                continue
            allowed = (
                TYPE_ONLY_ALLOWED_PREFIXES
                if type_checking
                else RUNTIME_ALLOWED_PREFIXES
            )
            if not _matches(module, allowed):
                guard = "TYPE_CHECKING " if type_checking else ""
                violations.append(f"{path.name}:{lineno}: {guard}imports {module}")
    assert not violations, "tools boundary violations:\n" + "\n".join(violations)


def test_tools_inbound_edges_are_sanctioned() -> None:
    violations: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        relative = path.relative_to(SRC_ROOT).as_posix()
        if relative.startswith("tools/"):
            continue
        for module, lineno, type_checking, in_function in _imports_of(path):
            if not _matches(module, ("loopplane.tools",)):
                continue
            if relative == "context.py" and type_checking:
                continue  # the neutral-Protocol typing seam (R1)
            if relative == "host/assembly.py" and (type_checking or in_function):
                continue  # the single lazy wiring seam (R4)
            violations.append(f"{relative}:{lineno}: imports {module}")
    assert not violations, "unsanctioned loopplane.tools imports:\n" + "\n".join(
        violations
    )


def test_context_type_checking_only() -> None:
    context_path = SRC_ROOT / "context.py"
    runtime_tools_imports = [
        f"context.py:{lineno}: {module}"
        for module, lineno, type_checking, _ in _imports_of(context_path)
        if _matches(module, ("loopplane.tools",)) and not type_checking
    ]
    assert not runtime_tools_imports, (
        "context.py must never import loopplane.tools at runtime (R1):\n"
        + "\n".join(runtime_tools_imports)
    )

    tree = ast.parse(context_path.read_text(encoding="utf-8"))
    protocols = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in CONTEXT_PROTOCOLS
    }
    missing = [name for name in CONTEXT_PROTOCOLS if name not in protocols]
    assert not missing, f"neutral supervisor Protocols missing: {missing}"
    for name, node in protocols.items():
        bases = {
            base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
            for base in node.bases
        }
        assert "Protocol" in bases, f"{name} must remain a neutral Protocol"
