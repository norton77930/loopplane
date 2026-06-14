"""The plugin manifest (`plugin.json`): a public-safe, data-only declaration of a
plugin's identity and contributions (spec FR-002, FR-010; data-model.md).

The manifest carries no callable and no credential: ``hooks`` reference an
importable ``module:attr`` target (resolved only for enabled plugins, by the
loader), and MCP entries are ``MCPServerConfig``-shaped mappings the host merges
through the existing MCP layer. ``extra="forbid"`` keeps a manifest from smuggling
unknown fields.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HookEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    point: str
    target: str


class PluginManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str
    skills: tuple[str, ...] = ()
    mcp_servers: dict[str, dict[str, object]] = {}
    hooks: tuple[HookEntry, ...] = ()


def parse_manifest(raw: bytes | str) -> PluginManifest:
    """Parse and validate one ``plugin.json``; raises ``ValidationError`` on a
    malformed or schema-invalid manifest (the caller skips that plugin)."""
    return PluginManifest.model_validate_json(raw)
