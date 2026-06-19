"""The Internal Tool Adapter and the baseline tool set (FR-030–FR-034), plus the
Web Tool Adapter and its host-injected search seam (spec 034)."""

from loopplane.tools.internal import InternalToolAdapter
from loopplane.tools.web import SearchProvider, SearchResult, WebToolAdapter

__all__ = [
    "InternalToolAdapter",
    "SearchProvider",
    "SearchResult",
    "WebToolAdapter",
]
