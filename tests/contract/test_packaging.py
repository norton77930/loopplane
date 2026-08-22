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


def test_the_all_extra_names_every_other_extra() -> None:
    """The `all` extra is a hand-written union, so it can silently fall out of
    step with the extras it claims to cover -- add a tenth extra, forget this
    line, and `pip install loopplane[all]` quietly stops meaning "all". The
    membership is therefore pinned rather than trusted. It is written
    self-referentially (`loopplane[a,b,...]`) so the version constraints still
    have exactly one home."""

    extras = load_pyproject()["project"]["optional-dependencies"]  # type: ignore[index]
    assert "all" in extras, "pyproject has no `all` convenience extra"
    assert len(extras["all"]) == 1, extras["all"]

    match = re.fullmatch(r"loopplane\[([a-z0-9,._-]+)\]", extras["all"][0].strip())
    assert match, (
        "the `all` extra must be self-referential, not a copy of the dependency "
        f"lines: {extras['all'][0]!r}"
    )
    named = {name.strip() for name in match.group(1).split(",")}
    others = {name for name in extras if name != "all"}
    assert named == others, (
        f"`all` names {sorted(named)} but the extras are {sorted(others)}; "
        f"missing={sorted(others - named)} unknown={sorted(named - others)}"
    )


def test_runtime_dependencies_are_unchanged() -> None:
    # The release unit MUST add no runtime dependency (NFR-002, SC-006).
    project = _project()
    names = {re.split(r"[<>=!~ ]", dep)[0] for dep in project["dependencies"]}
    assert names == {"anyio", "pydantic", "jsonschema"}, names
    # `all` is excluded deliberately, not waved through: it is a self-referential
    # alias over the nine below and names no distribution of its own, so it adds
    # no runtime dependency and NFR-002 / SC-006 still hold. Every extra that DOES
    # name a distribution stays pinned here; `all`'s membership is pinned by
    # test_the_all_extra_names_every_other_extra.
    assert set(project["optional-dependencies"]) - {"all"} == {
        "anthropic",
        "gemini",
        "mcp",
        "net",
        "oauth",
        "openai",
        "otel",
        "postgres",
        "web",
    }


def test_pyinstaller_stays_out_of_runtime_metadata() -> None:
    """078 freezes the Desktop sidecar from a build-only lock (078 T092).

    The closed dependency sets above already bar it from ``[project]``; the
    resolved runtime lock must stay clean too, so the freeze tool can never
    reach an installed runtime environment.
    """

    build_only = (
        REPO_ROOT / "apps" / "desktop" / "sidecar" / "pyinstaller-build.in"
    ).read_text(encoding="utf-8")
    assert "pyinstaller" in build_only.lower(), (
        "the build-only PyInstaller input must exist, otherwise this guard cannot fail"
    )

    for relative in ("pyproject.toml", "uv.lock"):
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "pyinstaller" not in text.lower(), (
            f"{relative} must not carry the build-only freeze tool"
        )


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
