"""The discovered-tool identity, the tool catalog, and discovery
(contracts/catalog.md; FR-001-FR-012).

``discover`` reads each tool source's public ``describe()`` surface only — never
``invoke`` — and assembles a deterministic, public-safe catalog. A source whose
``describe()`` raises contributes no tools and is recorded as a failed source.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loopplane.gateway import ToolAdapter


@dataclass(frozen=True)
class DiscoveredTool:
    """A public-safe projection of a tool's identity plus its provenance
    (FR-001). Holds no adapter reference and no invocation path."""

    source: str
    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    input_schema: Mapping[str, object]


@dataclass(frozen=True)
class ToolCatalog:
    """An in-memory inventory of discovered tools, sorted by ``(source, name)``,
    plus the labels of sources whose ``describe()`` raised (FR-002)."""

    tools: tuple[DiscoveredTool, ...]
    failed_sources: tuple[str, ...]

    def list(self) -> tuple[DiscoveredTool, ...]:
        return self.tools


def discover(sources: Sequence[ToolAdapter]) -> ToolCatalog:
    """Discover the tools a set of sources expose, reading ``describe()`` only.

    Builds a ``DiscoveredTool`` per ``ToolDescriptor``, sorted by ``(source,
    name)`` for determinism. A source whose ``describe()`` raises contributes no
    tools and its positional label is recorded in ``failed_sources`` — discovery
    never crashes and never invokes a tool (FR-002-FR-004, NFR-005/NFR-006).
    """

    tools: list[DiscoveredTool] = []
    failed: list[str] = []
    for index, source in enumerate(sources):
        try:
            descriptors = source.describe()
        except Exception:  # noqa: BLE001 - fail safe: a raising source is recorded
            failed.append(f"source[{index}]")
            continue
        for descriptor in descriptors:
            tools.append(
                DiscoveredTool(
                    source=descriptor.source,
                    name=descriptor.name,
                    description=descriptor.description,
                    read_only=descriptor.read_only,
                    concurrency_safe=descriptor.concurrency_safe,
                    input_schema=descriptor.input_schema,
                )
            )
    tools.sort(key=lambda tool: (tool.source, tool.name))
    failed.sort()
    return ToolCatalog(tools=tuple(tools), failed_sources=tuple(failed))
