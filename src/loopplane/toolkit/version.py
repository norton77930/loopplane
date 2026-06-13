"""Tool package versioning (contracts/catalog.md; FR-040-FR-042).

A deterministic ``major.minor.patch`` scheme with a total order and a
select-by-policy helper. A malformed version is an explicit ``ToolkitError``,
never a silent default.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from loopplane.toolkit.plugin import ToolPackage


class ToolkitError(RuntimeError):
    """A public-safe error for a malformed version or input (FR-042)."""


@dataclass(frozen=True, order=True)
class Version:
    """A ``major.minor.patch`` version with a total order (FR-040)."""

    major: int
    minor: int
    patch: int


def parse_version(text: str) -> Version:
    """Parse ``"X.Y.Z"`` into a ``Version``; a malformed string raises an explicit
    ``ToolkitError`` (FR-042, SC-008)."""

    parts = text.split(".")
    if len(parts) != 3:
        raise ToolkitError(f"malformed version: {text!r}")
    try:
        major, minor, patch = (int(part) for part in parts)
    except ValueError as exc:
        raise ToolkitError(f"malformed version: {text!r}") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ToolkitError(f"malformed version: {text!r}")
    return Version(major, minor, patch)


def select_by_policy(
    packages: Sequence[ToolPackage], *, policy: Literal["highest"] = "highest"
) -> ToolPackage | None:
    """Deterministically choose among packages by ``policy`` (default: the highest
    version). An empty input yields ``None`` (FR-041, SC-009)."""

    if not packages:
        return None
    return max(packages, key=lambda package: parse_version(package.version))
