# Phase 0 Research: Plugin System

Seam signatures grounded in the existing units; every decision re-derived for
LoopPlane (Constitution IX).

## R1 — The three seams a plugin feeds

| Contribution | Existing seam (consumed, not changed) | Shape it needs |
|---|---|---|
| skills | `loopplane.skills.load_skills(sources: Sequence[Path]) -> (dict, problems)` | a list of skill **directories** |
| MCP servers | `loopplane.adapters.mcp.merge_layers(layers) -> (list[MCPServerConfig], problems)` where each layer is `dict[name, dict]` | a layer mapping namespaced name → config dict |
| hooks | `loopplane.hooks.HookRegistry.register(point, callback)` | `(LifecyclePoint, callback)` pairs |

**Decision**: the plugin system only **collects** skill dirs and an MCP layer (the
host merges them with its own and calls the existing functions), and **registers**
hooks directly on a host-supplied `HookRegistry`. No existing unit's signature
changes — this stays additive (FR-013, avoids stop §9.5).

## R2 — Manifest shape (`plugin.json`)

A pydantic model with `extra="forbid"`, matching the existing units' style
(`MCPServerConfig`, `Skill`). Fields: `name`, `version` (required); optional
`skills` (list of directory names, resolved relative to the plugin dir),
`mcp_servers` (mapping name → MCPServerConfig-shaped dict), `hooks` (list of
`{point, target}`). The manifest is **data only** — it carries no callable and no
credential (FR-010).

## R3 — Namespacing MCP servers (FR-006)

Each plugin MCP server named `s` is collected under `"<plugin>__<server>"` so two
plugins declaring `s` cannot collide (SC-005). The namespaced mapping is one MCP
layer for `merge_layers`; the existing `MCPServerConfig` validation (transport /
command / url, `extra="forbid"`) screens malformed entries — already report-not-crash.

## R4 — Skip-the-whole-plugin and never-raise (FR-008/FR-009)

Discovery walks each root's subdirectories; a subdir with a parseable `plugin.json`
is a candidate. A missing/unparseable/schema-invalid manifest, an unreadable
directory, or a credential-bearing manifest skips that **whole** plugin (no partial
contribution) and appends a public-safe problem string — discovery returns problems,
never raises. This mirrors `load_skills` / `merge_layers`, which already skip-and-report.

## R5 — The bounded hook-import seam (Constitution IX divergence)

A JSON manifest cannot carry a Python callable, so a `hooks` entry is
`{point: "before_tool_use", target: "module:attr"}`. **Decision**: for an
**enabled** plugin only (the enable-list is the host's explicit act of trust), the
loader imports `module` via `importlib` and resolves `attr` to the callback, then
`registry.register(point, callback)`. A failed import / unknown point / missing
attr skips that hook with a public-safe diagnostic (and, per FR-008, the whole
plugin if its manifest is structurally invalid). The manifest stays pure data; the
only code execution is importing a target a trusted, enabled plugin declared — the
"opt-in code seam bounded by the plan" the spec reserves. This is a deliberate
divergence from the reference's parse-not-wired posture, justified because unit 015
hooks exist and the enable-list bounds trust.

## R6 — Name precedence across roots (FR-012)

Roots are ordered broadest-first (mirroring `load_skills` source order and
`merge_layers` layer order). When the same plugin name appears under more than one
root, the **more specific (later) root wins**; the shadowed one is reported with a
public-safe note. This matches the existing units' "more specific source wins".

## R7 — Default-inert (FR-004/FR-015)

`load_plugins([], enabled=...)` and `load_plugins(roots, enabled=())` both collect
nothing. The host wires plugins by passing roots + an enable-list; omitting them
reproduces today's behavior exactly. The plugin system touches no runtime component
directly — it returns a contribution set the host applies through the existing seams.
