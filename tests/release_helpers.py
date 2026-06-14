"""Shared, read-only helpers for the release-packaging contract tests (014).

Inspect the committed tree offline with the standard library only: the packaging
metadata (`pyproject.toml`), the public packages (every ``loopplane`` package that
declares ``__all__``), and the docs / examples file sets. No product code; no
import side effects (package discovery is by AST, not import).
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
LOOPLANE = SRC / "loopplane"
DOCS = REPO_ROOT / "docs"
EXAMPLES = REPO_ROOT / "examples"


def load_pyproject() -> dict[str, object]:
    """The parsed ``pyproject.toml`` as a nested mapping."""

    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _all_from(init_path: Path) -> list[str] | None:
    """The string list assigned to ``__all__`` in an ``__init__.py``, or None."""

    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            if isinstance(node.value, ast.List):
                return [
                    element.value
                    for element in node.value.elts
                    if isinstance(element, ast.Constant)
                    and isinstance(element.value, str)
                ]
    return None


def public_packages() -> dict[str, list[str]]:
    """Every ``loopplane`` package that declares ``__all__`` → its sorted names.

    Keyed by dotted package name (e.g. ``loopplane.orchestration`` or
    ``loopplane.adapters.mcp``). The top-level ``loopplane`` package declares no
    ``__all__`` and is excluded. Discovered by AST, so importing is not required.
    """

    packages: dict[str, list[str]] = {}
    for init_path in sorted(LOOPLANE.rglob("__init__.py")):
        names = _all_from(init_path)
        if names is None:
            continue
        dotted = ".".join(init_path.parent.relative_to(SRC).parts)
        packages[dotted] = sorted(names)
    return packages


def docs_guides() -> list[str]:
    """Sorted ``docs/*.md`` file names (e.g. ``loop-engineering.md``)."""

    return sorted(path.name for path in DOCS.glob("*.md"))


def example_scripts() -> list[str]:
    """Sorted ``examples/*.py`` file names (e.g. ``loop_quickstart.py``)."""

    return sorted(path.name for path in EXAMPLES.glob("*.py"))
