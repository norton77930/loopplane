# Contract: Plugin Integration Boundary

How collected contributions feed the existing seams **without changing any unit's
contract**. The plugin system depends on (consumes) these public functions; it adds
no parameter to them and reaches no internal.

## Skills (unit 001)

`PluginLoadResult.skill_dirs` is a tuple of existing directories. The host merges
them with its own skill sources (broadest-first) and calls the existing
`loopplane.skills.load_skills(sources)`. The plugin system introduces **no** new
skill loader or skill format — a plugin's skills are ordinary skill packages.

## MCP servers (units 001/008)

`PluginLoadResult.mcp_layer` is one configuration layer, `dict[namespaced_name,
config_dict]`. The host passes it as a layer to the existing
`loopplane.adapters.mcp.merge_layers([...host layers, plugin_layer])`; the existing
`MCPServerConfig` validation screens each entry (report-not-crash). The plugin
system executes and authorizes **no** tool — MCP servers run behind the Gateway
exactly as host-declared ones do (Constitution V).

## Hooks (unit 015)

When the host passes a `HookRegistry`, the loader registers each enabled plugin's
hooks on it via `registry.register(point, callback)`. The callback is resolved by
importing the manifest's `target` (`module:attr`) — **enabled plugins only**, and
only when a registry is supplied. The plugin system never fires hooks and never
touches the dispatcher; it only registers, through the existing public method.

## Non-goals on this boundary

- No existing unit (001 skills, 008 toolkit, 015 hooks) gains a parameter or a
  contract change; the plugin system only *calls* their public functions.
- No new runtime dependency; the manifest is data and the only code execution is the
  bounded, enabled-only hook-target import.
- The plugin system emits no event and drives no run.
