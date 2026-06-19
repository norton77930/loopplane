"""The Internal Tool Adapter and the baseline tool set (FR-030–FR-034), the Web Tool
Adapter and its host-injected search seam (spec 034), and the Subagent Spawn Tool
Adapter (spec 043)."""

from loopplane.tools.internal import InternalToolAdapter
from loopplane.tools.search import ReferenceSearchProvider
from loopplane.tools.subagent import SpawnSubagentAdapter
from loopplane.tools.web import SearchProvider, SearchResult, WebToolAdapter

__all__ = [
    "InternalToolAdapter",
    "ReferenceSearchProvider",
    "SearchProvider",
    "SearchResult",
    "SpawnSubagentAdapter",
    "WebToolAdapter",
]
