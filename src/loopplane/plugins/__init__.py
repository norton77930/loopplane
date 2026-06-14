"""LoopPlane plugin system (feature 016-loopplane-plugin-system).

A plugin is a directory described by a public-safe, data-only ``plugin.json`` that
declares skills, namespaced MCP servers, and hooks. :func:`discover` scans
host-supplied roots; :func:`load_plugins` gates discovered plugins by an enable-list
and collects each enabled plugin's contributions for the **existing** seams — skill
directories for :func:`loopplane.skills.load_skills`, a namespaced MCP layer for
:func:`loopplane.adapters.mcp.merge_layers`, and hook registrations on a
:class:`loopplane.hooks.HookRegistry`. It changes no other unit's contract and is
inert by default: with an empty enable-list nothing is collected or registered.
"""

from __future__ import annotations

from loopplane.plugins.discovery import DiscoveredPlugin, discover
from loopplane.plugins.loader import (
    PluginInfo,
    PluginLoadResult,
    list_plugins,
    load_plugins,
)
from loopplane.plugins.manifest import HookEntry, PluginManifest

__all__ = [
    "DiscoveredPlugin",
    "HookEntry",
    "PluginInfo",
    "PluginLoadResult",
    "PluginManifest",
    "discover",
    "list_plugins",
    "load_plugins",
]
