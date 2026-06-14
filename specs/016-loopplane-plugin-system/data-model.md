# Phase 1 Data Model: Plugin System

All types live in `loopplane.plugins`. Models are frozen and public-safe.

## PluginManifest (`manifest.py`)

A pydantic model (`extra="forbid"`, frozen), parsed from a plugin's `plugin.json`:

```
name: str                                  # required
version: str                               # required
skills: tuple[str, ...] = ()               # directory names relative to the plugin dir
mcp_servers: dict[str, dict] = {}          # server name -> MCPServerConfig-shaped mapping
hooks: tuple[HookEntry, ...] = ()
```

## HookEntry

```
point: str       # a LifecyclePoint value (validated against the known points)
target: str      # "module:attr" — the importable callback (resolved only for enabled plugins)
```

## DiscoveredPlugin (`discovery.py`)

The result of scanning one candidate directory:

```
directory: Path
manifest: PluginManifest | None    # None when the directory had no/invalid manifest
problem: str | None                # a public-safe reason when manifest is None / unsafe
```

`discover(roots: Sequence[Path]) -> list[DiscoveredPlugin]` — broadest-first; never
raises (R4).

## PluginLoadResult (`loader.py`)

The collected contribution set plus diagnostics:

```
skill_dirs: tuple[Path, ...]          # for loopplane.skills.load_skills
mcp_layer: dict[str, dict]            # namespaced "<plugin>__<server>" -> config dict, for merge_layers
hook_count: int                       # hooks registered on the supplied HookRegistry
loaded: tuple[PluginInfo, ...]        # what loaded (metadata only)
problems: tuple[str, ...]             # public-safe diagnostics (skips, shadows, bad hooks)
```

## PluginInfo (the public-safe listing — FR-011)

```
name: str
version: str
enabled: bool
skill_dir_count: int
mcp_server_count: int
hook_count: int
```

`list_plugins(roots, enabled) -> tuple[PluginInfo, ...]` is read-only and leaks
nothing (no path, no command, no credential).

## Operations

- `load_plugins(roots, enabled, *, hook_registry=None) -> PluginLoadResult` —
  discover → gate by `enabled` → collect skill_dirs + namespaced `mcp_layer` →
  (if `hook_registry` given) import each enabled plugin's hook targets and register
  them → return the result. Skip-whole-plugin on a structurally invalid manifest;
  skip-this-hook on a bad target. Never raises.
- `enabled` is an iterable of plugin names; empty (default) collects nothing.

## Relationships

```
discover(roots) ── list[DiscoveredPlugin] ──> load_plugins gates by `enabled`
load_plugins ──collects──> skill_dirs  ──(host)──> loopplane.skills.load_skills
load_plugins ──collects──> mcp_layer   ──(host)──> loopplane.adapters.mcp.merge_layers
load_plugins ──registers──> hooks      ──────────> loopplane.hooks.HookRegistry.register
```
