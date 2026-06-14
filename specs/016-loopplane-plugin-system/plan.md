# Implementation Plan: LoopPlane Plugin System

**Branch**: `016-loopplane-plugin-system` (main-only) | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/016-loopplane-plugin-system/spec.md`

## Summary

Add a **manifest-bundle plugin system** (`loopplane.plugins`): discover plugins
under host-supplied roots, gate them by an enable-list, and collect each enabled
plugin's contributions for the **existing** seams — skill directories for
`loopplane.skills.load_skills` (001), namespaced MCP server configs for
`loopplane.adapters.mcp.merge_layers` (001/008), and hook registrations on a
`loopplane.hooks.HookRegistry` (015). The manifest (`plugin.json`) is declarative
and public-safe; the only code seam is a bounded, enabled-only import of a plugin's
hook-registration target. A broken plugin is skipped whole with a public-safe
diagnostic; discovery never raises. With an empty enable-list nothing is collected,
so the runtime is unchanged (FR-004/SC-002).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: standard library + `pydantic` (already core); no new dependency

**Storage**: N/A (reads plugin directories; collects in-memory)

**Testing**: pytest (unit + integration + import-boundary + public-safety)

**Project Type**: single library (`src/loopplane/`)

**Performance Goals**: discovery is O(plugins); inert with no root configured (FR-015)

**Constraints**: additive — composes existing public seams only; no change to the
skills / MCP / hook contracts; manifests metadata-only and public-safe

**Scale/Scope**: one new subpackage (~3 modules) + example + docs; no wiring change
to existing units beyond *consuming* their public functions

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS** (no violations).*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR/SC per task). | PASS |
| II — Greenfield | Fresh code; no copy from `openspec/`/legacy. | PASS |
| III — Harness before automation | Additive composition layer; adds no automation engine. | PASS |
| IV — Boundary Clarity | New component with one responsibility (discover/gate/collect); interacts only through the declared public functions of skills/MCP/hooks. | PASS |
| V — Tool Gateway Ownership | Plugins register MCP servers only as configs for the existing MCP layer behind the Gateway; the plugin system executes and authorizes no tool. | PASS (FR-006/FR-013) |
| VI — Event Bus Ownership | No event emission; the plugin system never touches the bus. | PASS |
| VII — Public-Safe | Manifests and listings are metadata-only and public-safe; a credential-bearing manifest is a public-safety failure (skipped). | PASS (FR-010/FR-011/SC-004) |
| VIII — No SDK Replacement | No framework. | PASS |
| IX — Reference, not clone | Manifest-bundle (not entry-points) re-derived for LoopPlane; the bounded hook-import seam is a recorded divergence (research R5). | PASS |
| X — Testable Evolution | Tests + rollback (rollback = drop the package; default-inert = behavior-free revert). | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/016-loopplane-plugin-system/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── plugins.md               # public API: manifest, discovery, load, listing
│   └── integration-boundary.md  # how contributions feed the existing seams
└── tasks.md                     # created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/plugins/          # NEW subpackage
├── __init__.py                 # public surface (__all__)
├── manifest.py                 # PluginManifest + HookEntry (pydantic); parse one plugin.json
├── discovery.py                # discover(roots) -> discovered plugins (dir + manifest | problem)
└── loader.py                   # load_plugins(roots, enabled, *, hook_registry) -> PluginLoadResult; list_plugins(...)

examples/plugins_quickstart.py  # credential-free walkthrough
docs/plugins.md                 # guide

tests/unit/test_plugins_manifest.py     # manifest parse + validation + public-safety
tests/integration/test_plugins_us1.py..us5  # the five user stories end-to-end
tests/integration/test_plugins_boundary.py   # import-boundary + reuse + public-safety
```

**Structure Decision**: Single library. One new subpackage `loopplane.plugins`
that *consumes* the public functions of `loopplane.skills`, `loopplane.adapters.mcp`,
and `loopplane.hooks` — it adds no parameter to and changes no contract of those
units. The host merges the collected skill dirs / MCP layer with its own and calls
the existing `load_skills` / `merge_layers`; the loader registers hooks directly on
a host-supplied `HookRegistry`.

## Phases

- **Phase 0 — Research** (`research.md`): the real signatures of `load_skills`,
  `merge_layers`/`MCPServerConfig`, and `HookRegistry`; the manifest shape; the
  bounded hook-import seam; name-precedence; skip-whole-plugin.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the
  manifest model, the discovery/load/listing API, the contribution set, and the
  integration-boundary rules.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — manifest unit first, then per-user-story
  integration, then boundary + public-safety, then example + docs.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
