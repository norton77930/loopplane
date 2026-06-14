# Contract: Public Plugin API (`loopplane.plugins`)

In-process, public-safe, additive. The host supplies plugin roots + an enable-list;
the system returns a contribution set the host applies through the existing seams.

## Discovery

```
discover(roots: Sequence[Path]) -> list[DiscoveredPlugin]
```

- Scans each root's immediate subdirectories; a subdir is a candidate when it has a
  `plugin.json`. Roots are broadest-first.
- Every candidate becomes a `DiscoveredPlugin`; a bad/unsafe one carries
  `manifest=None` + a public-safe `problem`. **Never raises** (FR-009).

## Load

```
load_plugins(roots, enabled, *, hook_registry: HookRegistry | None = None) -> PluginLoadResult
```

- Discovers, then keeps only plugins whose `name` is in `enabled` (FR-003). An
  empty `enabled` collects nothing (FR-004).
- Collects `skill_dirs` (existing-dir skill folders), a namespaced `mcp_layer`
  (`"<plugin>__<server>"` → config dict — FR-006), and, when `hook_registry` is
  supplied, registers each enabled plugin's hooks on it (FR-007).
- A structurally invalid manifest skips the **whole** plugin (FR-008); a bad hook
  target skips that hook. Cross-root name collisions resolve by precedence
  (more-specific root wins) and the loser is reported (FR-012). An enabled name with
  no match is reported, not raised (FR-014). **Never raises** (FR-009).

## Listing

```
list_plugins(roots, enabled) -> tuple[PluginInfo, ...]
```

- Read-only, metadata-only: `name`, `version`, `enabled`, and the three contribution
  counts. Carries no path, command, url, or credential (FR-011, SC-004).

## Manifest

`plugin.json` (data only, `extra="forbid"`): `name`, `version` required; `skills`,
`mcp_servers`, `hooks` optional. A manifest that fails validation — or carries a
credential — disables its plugin (FR-010). Hook entries are `{point, target}` where
`target` (`"module:attr"`) is resolved by import **only for enabled plugins**.

## Default-inert guarantee

No roots, or an empty enable-list, collects nothing and registers nothing, so the
runtime behaves exactly as without the plugin system (FR-015, SC-002).
