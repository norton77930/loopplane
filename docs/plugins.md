# Plugins

`loopplane.plugins` (unit 016) packages **skills, MCP servers, and hooks** as a
discoverable, public-safe **plugin bundle** described by a `plugin.json` manifest. A
host points at one or more plugin roots, names the plugins it trusts in an
enable-list, and the system collects each enabled plugin's contributions for the
**existing** seams — it changes no other unit's contract and is inert by default.

## A plugin on disk

```text
plugins/greeter/
├── plugin.json
└── skills/greet.json
```

```json
{
  "name": "greeter",
  "version": "1.0.0",
  "skills": ["skills"],
  "mcp_servers": {"docs": {"transport": "http", "url": "https://example.invalid/mcp"}},
  "hooks": [{"point": "after_tool_use", "target": "greeter_hooks:audit"}]
}
```

The manifest is **data only** (`extra` keys are rejected): it carries no callable
and no credential. A `hooks` entry references an importable `module:attr` target,
resolved by the loader **only for enabled plugins**.

## Discover, gate, collect

```python
from pathlib import Path
from loopplane.hooks import HookRegistry
from loopplane.plugins import load_plugins, list_plugins

registry = HookRegistry()
result = load_plugins([Path("plugins")], enabled={"greeter"}, hook_registry=registry)

result.skill_dirs   # (Path('plugins/greeter/skills'),) -> loopplane.skills.load_skills
result.mcp_layer     # {'greeter__docs': {...}}          -> loopplane.adapters.mcp.merge_layers
result.hook_count    # 1   (registered on `registry`)
result.problems      # ()  (skips/shadows/bad hooks are reported here, never raised)
```

Apply the contributions through the existing functions:

```python
from loopplane.skills import load_skills
from loopplane.adapters.mcp import merge_layers

skills, _ = load_skills([*host_skill_dirs, *result.skill_dirs])
servers, _ = merge_layers([host_mcp_layer, result.mcp_layer])
```

## Semantics

- **Enable-list gating** — only plugins named in `enabled` load; an empty list
  collects nothing and the runtime is unchanged.
- **Namespacing** — a plugin's MCP server `s` is collected as `<plugin>__s`, so two
  plugins cannot collide.
- **Skip-the-whole-plugin** — a malformed, unparseable, or credential-bearing
  manifest skips that plugin entirely (the others still load); discovery never raises.
- **Public-safe** — manifests, the `list_plugins` listing, and every diagnostic carry
  no secret, credential, or private path.
- **Precedence** — when a name appears under more than one root, the more-specific
  (later) root wins and the shadowed one is reported.

See [`examples/plugins_quickstart.py`](../examples/plugins_quickstart.py) for a
complete credential-free run.
