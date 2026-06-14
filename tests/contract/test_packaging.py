"""Packaging & distribution contract (014): complete metadata, a single-source
version, a shipped ``py.typed`` marker, and an unchanged runtime dependency set
(FR-001-FR-004; NFR-001/002; SC-001/006). Reads the committed tree only.
"""

from __future__ import annotations

import importlib
import re

import loopplane
from tests.release_helpers import (
    LOOPLANE,
    REPO_ROOT,
    load_pyproject,
    public_packages,
)

_VERSION_RE = re.compile(r"^\d+\.\d+")


def _project() -> dict:
    return load_pyproject()["project"]  # type: ignore[index, return-value]


def test_project_metadata_is_complete() -> None:
    project = _project()
    for field in (
        "name",
        "description",
        "readme",
        "requires-python",
        "authors",
        "keywords",
        "classifiers",
    ):
        assert project.get(field), f"pyproject [project].{field} is missing"
    assert project["name"] == "loopplane"
    assert project.get("urls"), "pyproject [project.urls] is missing"


def test_runtime_dependencies_are_unchanged() -> None:
    # The release unit MUST add no runtime dependency (NFR-002, SC-006).
    project = _project()
    names = {re.split(r"[<>=!~ ]", dep)[0] for dep in project["dependencies"]}
    assert names == {"anyio", "pydantic", "jsonschema"}, names
    assert set(project["optional-dependencies"]) == {"mcp", "otel", "web"}


def test_version_has_a_single_source() -> None:
    data = load_pyproject()
    project = data["project"]  # type: ignore[index]
    assert "version" not in project, "[project].version literal must be removed"
    assert "version" in project.get("dynamic", []), "version must be dynamic"
    hatch_version = data["tool"]["hatch"]["version"]  # type: ignore[index]
    assert hatch_version["path"] == "src/loopplane/__init__.py"
    # The single source of truth is the in-code constant.
    assert isinstance(loopplane.__version__, str)
    assert _VERSION_RE.match(loopplane.__version__), loopplane.__version__


def test_py_typed_marker_is_present_and_shipped() -> None:
    assert (LOOPLANE / "py.typed").is_file(), "src/loopplane/py.typed missing"
    wheel = load_pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]  # type: ignore[index]
    assert wheel["packages"] == ["src/loopplane"], wheel


def test_every_public_subpackage_is_importable() -> None:
    for dotted in public_packages():
        importlib.import_module(dotted)


def test_license_is_declared() -> None:
    project = _project()
    assert project.get("license") == "MIT", project.get("license")
    assert project.get("license-files") == ["LICENSE"], project.get("license-files")
    assert (REPO_ROOT / "LICENSE").is_file(), "LICENSE file missing"
