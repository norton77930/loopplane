"""The MCP Tool Adapter (FR-040–FR-045)."""

from loopplane.adapters.mcp.adapter import MCPToolAdapter
from loopplane.adapters.mcp.config import MCPServerConfig, merge_layers
from loopplane.adapters.mcp.schema import translate_schema

__all__ = [
    "MCPServerConfig",
    "MCPToolAdapter",
    "merge_layers",
    "translate_schema",
]
