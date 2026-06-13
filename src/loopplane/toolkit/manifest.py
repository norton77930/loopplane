"""The capability manifest, derived from a tool's identity + package metadata
(contracts/catalog.md; FR-031-FR-032).

``build_manifest`` reads declared attributes only — it never invokes the tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loopplane.toolkit.catalog import DiscoveredTool
    from loopplane.toolkit.plugin import ToolPackage


@dataclass(frozen=True)
class CapabilityManifest:
    """What a tool can do, derived without invocation (FR-031)."""

    tool_name: str
    source: str
    read_only: bool
    concurrency_safe: bool
    package: str
    package_version: str
    tags: tuple[str, ...]


def build_manifest(tool: DiscoveredTool, package: ToolPackage) -> CapabilityManifest:
    """Derive a deterministic capability manifest from the tool's declared identity
    and the package's declared tags — no invocation (FR-031, FR-032, NFR-006)."""

    return CapabilityManifest(
        tool_name=tool.name,
        source=tool.source,
        read_only=tool.read_only,
        concurrency_safe=tool.concurrency_safe,
        package=package.name,
        package_version=package.version,
        tags=tuple(package.capability_tags),
    )
