"""LoopPlane Advanced Tool Gateway layer (feature
008-loopplane-tool-gateway-advanced).

Deterministic, public-safe, offline tooling that organizes the tool ecosystem
**above** the Phase-1 Tool Gateway: it discovers tools through the public
``ToolAdapter.describe()`` surface, catalogs and bundles them, derives capability
manifests, tracks versions, and diagnoses problems. It composes only the public
``ToolAdapter`` (``loopplane.gateway``) and ``ToolDescriptor`` (``loopplane.model``)
contracts and a narrow registration seam; it **never invokes or executes a tool**
— the Tool Gateway stays the single chokepoint (Constitution V;
contracts/toolkit-boundary.md).
"""

from loopplane.toolkit.catalog import DiscoveredTool, ToolCatalog, discover
from loopplane.toolkit.plugin import (
    AdapterRegistrar,
    ToolPackage,
    ToolPlugin,
    register_plugin,
)

__all__ = [
    "AdapterRegistrar",
    "DiscoveredTool",
    "ToolCatalog",
    "ToolPackage",
    "ToolPlugin",
    "discover",
    "register_plugin",
]
