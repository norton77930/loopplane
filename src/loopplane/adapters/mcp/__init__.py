"""The MCP Tool Adapter (FR-040–FR-045)."""

from loopplane.adapters.mcp.adapter import MCPToolAdapter
from loopplane.adapters.mcp.config import MCPServerConfig, merge_layers
from loopplane.adapters.mcp.oauth import (
    AuthorizationResult,
    InMemoryMcpTokenStore,
    McpAuthorizationError,
    McpAuthorizationHandler,
    McpTokenStore,
    StoredAuthorizationMaterial,
)
from loopplane.adapters.mcp.schema import translate_schema

__all__ = [
    "AuthorizationResult",
    "InMemoryMcpTokenStore",
    "MCPServerConfig",
    "MCPToolAdapter",
    "McpAuthorizationError",
    "McpAuthorizationHandler",
    "McpTokenStore",
    "StoredAuthorizationMaterial",
    "merge_layers",
    "translate_schema",
]
