"""Tool packages, plugins, and registration through the gateway
(contracts/toolkit-boundary.md; FR-020-FR-022, FR-030).

A ``ToolPlugin`` bundles tool sources plus package metadata. ``register_plugin``
hands each adapter to the gateway's public ``register_adapter`` and nothing else —
the gateway keeps resolution, authorization, and execution (Constitution V).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from loopplane.gateway import ToolAdapter


@dataclass(frozen=True)
class ToolPackage:
    """Public-safe package metadata (FR-030)."""

    name: str
    version: str
    description: str = ""
    source: str = ""
    capability_tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolPlugin:
    """A named bundle of tool sources plus a package (FR-020)."""

    name: str
    package: ToolPackage
    adapters: tuple[ToolAdapter, ...]


class AdapterRegistrar(Protocol):
    """The gateway's public registration seam; the host's ``ToolGateway`` satisfies
    it structurally (FR-021)."""

    def register_adapter(self, adapter: ToolAdapter) -> None: ...


def register_plugin(plugin: ToolPlugin, registrar: AdapterRegistrar) -> None:
    """Register each of the plugin's adapters through ``register_adapter`` and
    nothing else; the layer never invokes a tool (FR-021, FR-022, NFR-006)."""

    for adapter in plugin.adapters:
        registrar.register_adapter(adapter)
