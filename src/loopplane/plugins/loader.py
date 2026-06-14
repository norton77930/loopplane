"""Plugin loading: gate discovered plugins by an enable-list and collect each
enabled plugin's contributions for the existing seams (spec FR-003-FR-014;
contracts/integration-boundary.md).

The loader changes no other unit's contract: it returns skill directories (for
``loopplane.skills.load_skills``) and a namespaced MCP layer (for
``loopplane.adapters.mcp.merge_layers``), and — when a ``HookRegistry`` is supplied
— registers each enabled plugin's hooks on it. The only code execution is the
bounded, enabled-only import of a hook's ``module:attr`` target (research R5).
Never raises (FR-009).
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loopplane.hooks.points import LifecyclePoint
from loopplane.plugins.discovery import DiscoveredPlugin, discover
from loopplane.plugins.manifest import HookEntry, PluginManifest

if TYPE_CHECKING:
    from loopplane.hooks.registry import HookCallback, HookRegistry


@dataclass(frozen=True)
class PluginInfo:
    """A read-only, metadata-only view of a discovered plugin (FR-011)."""

    name: str
    version: str
    enabled: bool
    skill_dir_count: int
    mcp_server_count: int
    hook_count: int


@dataclass(frozen=True)
class PluginLoadResult:
    """The collected contribution set plus public-safe diagnostics."""

    skill_dirs: tuple[Path, ...] = ()
    mcp_layer: dict[str, dict[str, object]] = field(default_factory=dict)
    hook_count: int = 0
    loaded: tuple[PluginInfo, ...] = ()
    problems: tuple[str, ...] = ()


def _choose(
    discovered: Sequence[DiscoveredPlugin], problems: list[str]
) -> dict[str, DiscoveredPlugin]:
    """Resolve discovered plugins by name; the more-specific (later) root wins,
    and the shadowed one is reported (FR-012)."""
    chosen: dict[str, DiscoveredPlugin] = {}
    for candidate in discovered:
        if candidate.manifest is None:
            if candidate.problem is not None:
                problems.append(candidate.problem)
            continue
        name = candidate.manifest.name
        if name in chosen:
            problems.append(f"plugin {name!r} shadowed by a more specific root")
        chosen[name] = candidate
    return chosen


def _resolve_hook(
    entry: HookEntry, plugin: str, problems: list[str]
) -> tuple[LifecyclePoint, HookCallback] | None:
    try:
        point = LifecyclePoint(entry.point)
    except ValueError:
        problems.append(
            f"plugin {plugin!r} hook references unknown point {entry.point!r}"
        )
        return None
    if ":" not in entry.target:
        problems.append(
            f"plugin {plugin!r} hook target {entry.target!r} is not 'module:attr'"
        )
        return None
    module_name, _, attr = entry.target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except Exception:
        problems.append(
            f"plugin {plugin!r} hook target module {module_name!r} is not importable"
        )
        return None
    callback = getattr(module, attr, None)
    if not callable(callback):
        problems.append(
            f"plugin {plugin!r} hook target {entry.target!r} is not callable"
        )
        return None
    return point, callback


def load_plugins(
    roots: Sequence[Path],
    enabled: Iterable[str],
    *,
    hook_registry: HookRegistry | None = None,
) -> PluginLoadResult:
    """Discover, gate by ``enabled``, and collect contributions. Never raises."""
    enabled_set = set(enabled)
    problems: list[str] = []
    chosen = _choose(discover(roots), problems)

    for name in sorted(enabled_set):
        if name not in chosen:
            problems.append(f"enabled plugin {name!r} was not found")

    skill_dirs: list[Path] = []
    mcp_layer: dict[str, dict[str, object]] = {}
    hook_count = 0
    loaded: list[PluginInfo] = []

    for name, candidate in chosen.items():
        if name not in enabled_set:
            continue
        manifest = candidate.manifest
        assert manifest is not None  # _choose keeps only manifested plugins

        plugin_skill_dirs = _collect_skill_dirs(
            candidate.directory, manifest, name, problems
        )
        skill_dirs.extend(plugin_skill_dirs)

        for server_name, config in manifest.mcp_servers.items():
            mcp_layer[f"{name}__{server_name}"] = dict(config)

        if hook_registry is not None:
            for entry in manifest.hooks:
                resolved = _resolve_hook(entry, name, problems)
                if resolved is None:
                    continue
                point, callback = resolved
                hook_registry.register(point, callback)
                hook_count += 1

        loaded.append(
            PluginInfo(
                name=name,
                version=manifest.version,
                enabled=True,
                skill_dir_count=len(plugin_skill_dirs),
                mcp_server_count=len(manifest.mcp_servers),
                hook_count=len(manifest.hooks),
            )
        )

    return PluginLoadResult(
        skill_dirs=tuple(skill_dirs),
        mcp_layer=mcp_layer,
        hook_count=hook_count,
        loaded=tuple(loaded),
        problems=tuple(problems),
    )


def _collect_skill_dirs(
    directory: Path, manifest: PluginManifest, name: str, problems: list[str]
) -> list[Path]:
    dirs: list[Path] = []
    for rel in manifest.skills:
        candidate = directory / rel
        if candidate.is_dir():
            dirs.append(candidate)
        else:
            problems.append(f"plugin {name!r} skill directory {rel!r} was not found")
    return dirs


def list_plugins(
    roots: Sequence[Path], enabled: Iterable[str]
) -> tuple[PluginInfo, ...]:
    """A read-only, public-safe listing of discovered plugins (FR-011)."""
    enabled_set = set(enabled)
    infos: list[PluginInfo] = []
    for name, candidate in _choose(discover(roots), []).items():
        manifest = candidate.manifest
        if manifest is None:
            continue
        infos.append(
            PluginInfo(
                name=name,
                version=manifest.version,
                enabled=name in enabled_set,
                skill_dir_count=len(manifest.skills),
                mcp_server_count=len(manifest.mcp_servers),
                hook_count=len(manifest.hooks),
            )
        )
    return tuple(infos)
