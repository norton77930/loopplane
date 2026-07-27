"""Public API reference drift contract (014): the reference documents exactly the
public surface — every ``loopplane`` package that declares ``__all__``, and per
package the documented names equal that package's ``__all__`` (FR-010-FR-012;
SC-002). A drift in either direction fails. Reads the committed tree only.

Parse rule (kept in lock-step with ``docs/api-reference.md``):
- a package section opens with a heading ``### `loopplane.<dotted>` ``;
- within it, each public name is a bullet ``- `Name` — description``;
- any other heading (``#``/``##``/a non-package ``###``) closes the section.
"""

from __future__ import annotations

import inspect
import re

import loopplane.host as host_api
from loopplane.host import AllowedWorkspaceContextProvider, LoopPlaneHost
from tests.release_helpers import DOCS, public_packages

API_REFERENCE = DOCS / "api-reference.md"

_PACKAGE_HEADING = re.compile(r"^### `(loopplane[.\w]+)`")
_NAME_BULLET = re.compile(r"^- `([A-Za-z_]\w*)`")


def _documented() -> dict[str, set[str]]:
    """Map each documented package to the set of public names it lists."""

    documented: dict[str, set[str]] = {}
    current: str | None = None
    for line in API_REFERENCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            heading = _PACKAGE_HEADING.match(line)
            current = heading.group(1) if heading else None
            if current is not None:
                documented.setdefault(current, set())
            continue
        if current is not None:
            bullet = _NAME_BULLET.match(line)
            if bullet:
                documented[current].add(bullet.group(1))
    return documented


def test_capability_host_public_surface_tracks_async_and_provider_contract() -> None:
    assert "AllowedWorkspaceContextProvider" in host_api.__all__
    assert AllowedWorkspaceContextProvider is not None
    assert inspect.iscoroutinefunction(LoopPlaneHost.upsert_managed_mcp)
    assert inspect.iscoroutinefunction(LoopPlaneHost.delete_managed_mcp)


def test_api_reference_documents_every_public_package() -> None:
    documented = set(_documented())
    expected = set(public_packages())
    assert documented == expected, {
        "missing_from_doc": sorted(expected - documented),
        "extra_in_doc": sorted(documented - expected),
    }


def test_api_reference_names_match_each_package_all() -> None:
    documented = _documented()
    drift: dict[str, dict[str, list[str]]] = {}
    for package, names in public_packages().items():
        listed = documented.get(package, set())
        want = set(names)
        if listed != want:
            drift[package] = {
                "missing": sorted(want - listed),
                "extra": sorted(listed - want),
            }
    assert not drift, drift


def test_api_reference_is_metadata_only() -> None:
    # Names + descriptions only — no fenced code block (no source/internals).
    text = API_REFERENCE.read_text(encoding="utf-8")
    assert "```" not in text, "the API reference must not embed fenced code blocks"
