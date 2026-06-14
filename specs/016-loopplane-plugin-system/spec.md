# Feature Specification: LoopPlane Plugin System

**Feature Branch**: `016-loopplane-plugin-system` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "LoopPlane plugin system (roadmap unit 016, package loopplane.plugins): a public-safe manifest bundle (plugin.json) that packages skills + namespaced MCP servers + hooks into a discoverable, host-loadable unit; enable-list gating with zero default behavior change; loads through the existing skills/MCP/hook seams with no new runtime coupling. Reuses 001 skills, 008 toolkit, 015 hooks."

## Overview

LoopPlane already lets a host contribute skills (unit 001), MCP tool servers
(units 001/008), and lifecycle hooks (unit 015) — but each must be discovered and
wired by hand, and there is no unit of distribution that bundles "a capability"
(its skills + tools + hooks) nor a switch to enable a curated set.

This feature adds a **plugin system**: a plugin is a directory described by a
public-safe **manifest** (`plugin.json`) that declares its contributions. A host
points at one or more plugin roots, names the plugins it trusts in an
**enable-list**, and the system discovers the manifests, collects each enabled
plugin's contributions, and exposes them for wiring through the **existing**
skill / MCP / hook seams — adding no new runtime coupling. With no plugin enabled,
the runtime behaves exactly as before.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover and load an enabled plugin (Priority: P1)

A platform engineer drops a plugin directory (a `plugin.json` plus its skill files)
into a plugin root, names it in the enable-list, and gets the plugin's
contributions ready to wire into the runtime — without writing glue code.

**Why this priority**: Discovery + load of one enabled plugin is the smallest
viable slice and exercises the whole pipeline (scan → parse → gate → collect). If
only this works, plugins are already usable.

**Independent Test**: Place one valid plugin under a root, enable it, run
discovery, and confirm the loaded result names the plugin and carries its declared
contributions; place an unrelated directory with no manifest and confirm it is
ignored.

**Acceptance Scenarios**:

1. **Given** a plugin root containing one valid plugin enabled by name, **When** the system loads, **Then** the result includes that plugin with its declared contributions and no error.
2. **Given** a directory under the root with no `plugin.json`, **When** the system loads, **Then** that directory is ignored (it is not a plugin).

### User Story 2 - Enable only the plugins you trust (Priority: P1)

A host wants discovered-but-not-enabled plugins to stay dormant, and wants an empty
enable-list to change nothing at all.

**Why this priority**: The enable-list is the safety gate and the zero-behavior
guarantee; it is what makes the system safe to ship on by default.

**Independent Test**: With two plugins discovered and only one enabled, confirm
only the enabled one's contributions load; with none enabled, confirm the loaded
result is empty and the runtime is unchanged.

**Acceptance Scenarios**:

1. **Given** two discovered plugins with only one named in the enable-list, **When** the system loads, **Then** only the enabled plugin's contributions are collected.
2. **Given** an empty enable-list, **When** the system loads, **Then** nothing is collected and the runtime behaves identically to having no plugin system at all.

### User Story 3 - A plugin contributes skills (Priority: P2)

A plugin author ships reusable skills inside the plugin so that enabling the plugin
makes its skills available to the agent.

**Why this priority**: Skills are the most common plugin contribution and reuse the
existing skill loader directly.

**Independent Test**: Enable a plugin whose manifest declares a skills directory and
confirm those skills load through the existing skill loader exactly as host-supplied
skills would.

**Acceptance Scenarios**:

1. **Given** an enabled plugin declaring a skills directory, **When** the system loads, **Then** the plugin's skill directories are collected for the existing skill loader.

### User Story 4 - A plugin contributes MCP servers and hooks (Priority: P2)

A plugin bundles an MCP tool server and lifecycle hooks so that enabling it both
extends the toolset and installs its observers/gates.

**Why this priority**: Tools and hooks complete the "capability bundle"; they must
compose the existing MCP and hook seams, namespaced so plugins cannot collide.

**Independent Test**: Enable a plugin declaring an MCP server and hooks; confirm the
server appears namespaced (`<plugin>__<server>`) for the existing MCP layer and the
hooks are registered on the existing hook registry.

**Acceptance Scenarios**:

1. **Given** an enabled plugin declaring an MCP server named `s`, **When** the system loads, **Then** the server is collected under the namespaced name `<plugin>__s`.
2. **Given** an enabled plugin declaring hooks, **When** the system loads, **Then** those hooks are registered on the existing hook registry (unit 015).

### User Story 5 - Malformed or unsafe plugins are handled safely (Priority: P3)

An operator with a mixed set of plugins (some broken) wants one bad plugin to never
break discovery or leak anything.

**Why this priority**: Robustness and public-safety; a plugin ecosystem must degrade
gracefully and never expose a secret.

**Independent Test**: Place a plugin with a malformed manifest and another with a
type error alongside a valid one; confirm only the valid one loads, the broken ones
are skipped with public-safe diagnostics, and the discovery call never raises.

**Acceptance Scenarios**:

1. **Given** a plugin with an invalid or unparseable manifest, **When** the system loads, **Then** that plugin is skipped whole (no partial contribution), the others still load, and a public-safe diagnostic is recorded.
2. **Given** any discovered plugin, **When** the system lists what it found, **Then** the listing carries no secret, credential, or private path.

### Edge Cases

- **No plugin root configured** → nothing is discovered; the system is inert.
- **Empty manifest** (valid but declares no contributions) → the plugin loads as a no-op.
- **Same plugin name under two roots** → a defined precedence resolves it (one wins; the other is shadowed with a public-safe note).
- **Enabled name with no matching discovered plugin** → ignored with a public-safe diagnostic; not an error.
- **A plugin's skills directory does not exist** → that contribution is skipped; the plugin's other contributions still load.
- **Discovery encounters an unreadable directory** → it is skipped; discovery continues and never raises.
- **A manifest tries to embed a credential** → it is treated as a public-safety failure for that plugin (skipped), never loaded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST discover plugins under one or more host-supplied plugin roots; a subdirectory is a plugin when it contains a parseable `plugin.json`.
- **FR-002**: The manifest MUST require a `name` and a `version`, and MAY declare contributions: skill directories, named MCP servers, and hooks.
- **FR-003**: The system MUST gate loading by a host-supplied enable-list: only plugins named in it are loaded; the default enable-list is empty.
- **FR-004**: With an empty enable-list, the system MUST collect nothing and exhibit zero observable behavior change versus having no plugin system.
- **FR-005**: For an enabled plugin, the system MUST collect its skill directories for the **existing** skill loader (unit 001) — it introduces no new skill mechanism.
- **FR-006**: The system MUST collect an enabled plugin's MCP servers **namespaced** as `<plugin>__<server>` for the existing MCP layer, so two plugins cannot collide.
- **FR-007**: The system MUST register an enabled plugin's hooks on the existing hook registry (unit 015).
- **FR-008**: A plugin whose manifest is missing, unparseable, schema-invalid, or type-invalid MUST be skipped **whole** (never partially); other plugins MUST still load.
- **FR-009**: Discovery MUST NOT raise on a bad or unreadable plugin; each failure MUST surface as a public-safe, metadata-only diagnostic.
- **FR-010**: Manifests and any plugin listing MUST be public-safe and metadata-only — no secret, credential, or private absolute path; a manifest that embeds a credential MUST be treated as a public-safety failure and skipped.
- **FR-011**: The system MUST provide a read-only listing of discovered plugins (name, version, enabled state, contribution counts) that leaks nothing.
- **FR-012**: When the same plugin name is found under more than one root, the system MUST apply a defined precedence and shadow the loser with a public-safe note.
- **FR-013**: Loading MUST compose only the existing public seams (skill loader, MCP configuration, hook registry); it MUST NOT change those units' contracts or add new runtime coupling.
- **FR-014**: An enabled name that matches no discovered plugin MUST be ignored with a public-safe diagnostic, not an error.
- **FR-015**: The system MUST be inert by default — with no plugin root configured, nothing is discovered and the runtime is unchanged.

### Key Entities

- **Plugin**: a directory under a plugin root, identified by its manifest's `name` and `version`, carrying zero or more contributions.
- **Manifest (`plugin.json`)**: the public-safe, data-only declaration of a plugin — its identity plus its skill directories, named MCP servers, and hooks.
- **Enable-list**: the host-supplied set of plugin names permitted to load; empty by default.
- **Contribution set**: the collected result of loading enabled plugins — skill directories (for the skill loader), namespaced MCP servers (for the MCP layer), and hook registrations (for the hook registry).
- **Plugin listing**: a read-only, metadata-only view of discovered plugins (name, version, enabled, contribution counts).

### Out of Scope

- Installing, downloading, or updating plugins from a remote index or registry.
- Executing arbitrary plugin Python at import time beyond the contracted contribution seams (the manifest is data; any code seam is opt-in and bounded by the plan).
- A CLI or GUI for managing plugins (units 017–019).
- Plugin version constraints, dependency resolution between plugins, or sandboxing of plugin code beyond the existing governance layer (unit 009).
- Hot-reloading or enabling/disabling a plugin mid-run.
- Any new third-party dependency.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A host can make an enabled plugin's contributions available by pointing at a plugin root and naming the plugin — with no change to runtime source.
- **SC-002**: With an empty enable-list, a run produces outcomes identical to the pre-feature baseline — verified by the full existing suite remaining green with zero changes to expected results.
- **SC-003**: In a set containing both valid and broken plugins, 100% of the valid enabled plugins load and 100% of the broken ones are skipped without raising.
- **SC-004**: 100% of plugin manifests and listings pass the repository public-safety scan (zero secrets, credentials, or private paths).
- **SC-005**: Two plugins each declaring an MCP server named `s` produce two distinct namespaced servers (`a__s`, `b__s`) with no collision.
- **SC-006**: Enabling a plugin's skills makes them load through the existing skill loader, indistinguishable from host-supplied skills of the same shape.

## Assumptions

- **Reuse, not reinvention**: skill directories load through the unit-001 skill loader, MCP servers through the unit-001/008 MCP configuration, and hooks through the unit-015 hook registry; this unit adds discovery + gating + collection only.
- **Manifest is data**: `plugin.json` is declarative and public-safe; MCP server entries are remote-only/public-safe and never embed a credential (credentials remain in the host environment).
- **Enabled = trusted**: naming a plugin in the enable-list is the host's explicit act of trust; the system loads only enabled plugins, and the precise mechanism for any plugin-provided hook code is bounded by the plan and remains opt-in.
- **Default-inert**: no plugin root and an empty enable-list both mean "nothing happens", so existing embeddings see no behavior change.
- **Skip-the-whole-plugin**: an invalid plugin contributes nothing (no partial load), keeping the contribution set coherent.
- **Name precedence**: when names collide across roots, a deterministic precedence (documented at plan time, e.g. project over user) selects the winner.
