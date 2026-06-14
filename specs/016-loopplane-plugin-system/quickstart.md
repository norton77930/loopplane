# Quickstart: Plugins

A credential-free walkthrough. The runnable form ships as
`examples/plugins_quickstart.py`.

## 1. A plugin on disk

```text
plugins/
└── greeter/
    ├── plugin.json
    └── skills/
        └── greet.json
```

`plugins/greeter/plugin.json`:

```json
{
  "name": "greeter",
  "version": "1.0.0",
  "skills": ["skills"],
  "mcp_servers": {"docs": {"transport": "http", "url": "https://example.invalid/mcp"}},
  "hooks": [{"point": "after_tool_use", "target": "greeter_hooks:audit"}]
}
```

## 2. Discover and load enabled plugins

```python
from pathlib import Path
from loopplane.hooks import HookRegistry
from loopplane.plugins import load_plugins, list_plugins

registry = HookRegistry()
result = load_plugins([Path("plugins")], enabled={"greeter"}, hook_registry=registry)

print(result.skill_dirs)   # (Path('plugins/greeter/skills'),)
print(result.mcp_layer)    # {'greeter__docs': {'transport': 'http', 'url': '...'}}
print(result.hook_count)   # 1  (registered on `registry`)
print(result.problems)     # ()  (a broken plugin would be skipped and noted here)
```

## 3. Apply through the existing seams

```python
from loopplane.skills import load_skills
from loopplane.adapters.mcp import merge_layers

skills, skill_problems = load_skills([*host_skill_dirs, *result.skill_dirs])
servers, mcp_problems = merge_layers([host_mcp_layer, result.mcp_layer])
# `registry` already holds the plugin's hooks; pass it via HookDispatcher (unit 015).
```

## 4. Default-inert

With an empty enable-list, `load_plugins(roots, enabled=set())` collects nothing and
registers nothing — the runtime is unchanged.

## 5. Read-only listing

```python
for info in list_plugins([Path("plugins")], enabled={"greeter"}):
    print(info.name, info.version, info.enabled, info.skill_dir_count)
# Carries counts only — no path, command, url, or credential.
```
