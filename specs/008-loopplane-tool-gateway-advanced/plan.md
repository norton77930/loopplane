# Implementation Plan: Advanced Tool Gateway Layer

**Branch**: `main` (main-only autopilot) | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-loopplane-tool-gateway-advanced/spec.md`

## Summary

Build the **Advanced Tool Gateway** layer (Phase-8) that lets a host understand and organize its tool
ecosystem **without touching execution**. A new additive sub-package, `loopplane.toolkit`, discovers the
tools a set of tool sources expose (through the public `ToolAdapter.describe()` surface), catalogs them
keyed by `(source, name)`, detects name collisions **before** the gateway's hard duplicate-name error,
bundles sources as named **Tool Plugins** registered through the gateway's public `register_adapter`,
derives deterministic **Capability Manifests**, tracks **Tool Package versions** with deterministic
comparison/selection, and runs a **diagnostics** pass — all deterministic, public-safe, and offline. It
composes **only** the public Phase-1 tool contracts (`ToolAdapter` from `loopplane.gateway`,
`ToolDescriptor` from `loopplane.model`) and a narrow host-supplied registration seam; it **never** invokes,
resolves, authorizes, executes, or sandboxes a tool — the **Tool Gateway stays the single chokepoint**
(Constitution V). The deliverable is the package plus a public-safe example, a doc, and
unit/integration/contract suites. Design detail lives in [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), and [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ (matches Phases 1–7).

**Primary Dependencies**: the public Phase-1 `ToolAdapter` SPI (`loopplane.gateway`) and the `ToolDescriptor`
tool identity (`loopplane.model`), plus the stdlib. **No new third-party dependency.**

**Storage**: None. The layer owns no store and no runtime state; the catalog is an in-memory value built from
a snapshot of the host's tool sources.

**Testing**: pytest + the anyio plugin. New suites under `tests/unit/`, `tests/integration/`, and
`tests/contract/`. Scripted `ToolAdapter`s + scripted `ToolDescriptor`s + a recording registrar are the
deterministic instruments (NFR-001, SC-002) — no server, no network, no execution.

**Target Platform**: Cross-platform library embedded in a host process; a pure-composition layer with no
host, transport, or UI dependency.

**Performance Goals**: Negligible — discovery is O(tools) over `describe()`; the catalog/manifest/diagnostics
are linear passes. Determinism preserved (NFR-001).

**Constraints**: `describe()`-only reads (FR-003, FR-060); registration only through the gateway's public
`register_adapter` (FR-021, SC-007); **no tool invocation** (NFR-006, SC-005); determinism (NFR-001,
SC-002); fail-safe on every failure mode (NFR-005, SC-003/008); public-safe (NFR-002, SC-006).

**Scale/Scope**: One new package (~5 modules), one example, one doc, unit/integration/contract suites.
**No Phase-1/2/3 source is modified.**

## Dependency on Phase 1

This phase is **strictly additive** and consumes only two public Phase-1 tool contracts plus a narrow
host-supplied seam — it composes them and re-derives none of them (NFR-003, FR-062):

- **`loopplane.gateway`**: the `ToolAdapter` SPI — the layer reads only its `describe() -> Sequence[
  ToolDescriptor]` surface (never `invoke`).
- **`loopplane.model`**: the `ToolDescriptor` identity (`name`, `description`, `input_schema`,
  `concurrency_safe`, `read_only`, `source`).
- **A narrow `AdapterRegistrar` protocol** (`register_adapter(adapter: ToolAdapter) -> None`) the layer
  *defines*; the host's `ToolGateway` satisfies it structurally, so the layer registers plugins through the
  gateway **without importing the concrete `ToolGateway`** (keeping the boundary minimal).

**Non-duplication guarantee (FR-062, SC-005/007)**: the layer contains **no** tool resolution, authorization,
execution, sizing, timeout, or error-normalization logic — those remain the Tool Gateway's. It only
discovers, catalogs, bundles, describes, versions, and diagnoses, and it registers tool sources only through
`register_adapter`.

## Architecture & Boundaries

Dependency direction is strictly inward: `loopplane.toolkit` depends on the public `loopplane.gateway`
(`ToolAdapter`) and `loopplane.model` (`ToolDescriptor`); the gateway, runtime, host, and every loop-layer
sibling have **zero** knowledge of the toolkit.

```text
platform developer
     │ has tool sources (ToolAdapters) + wants an inventory / bundles / manifests
     ▼
loopplane.toolkit.discover(sources) -> ToolCatalog        (reads ToolAdapter.describe() only)
     │ lookup / list / collisions / manifest / version / diagnose
     ▼
loopplane.toolkit.register_plugin(plugin, registrar)      (registrar = host ToolGateway)
     │ calls registrar.register_adapter(adapter) per source
     ▼
Tool Gateway  ◄── the ONLY path that resolves, authorizes, and executes tools (Constitution V)
```

Allowed interactions (everything else is prohibited reach-through, per
[contracts/toolkit-boundary.md](./contracts/toolkit-boundary.md)):

- The layer reads tools **only** through `ToolAdapter.describe()`; it never calls `invoke` and never executes
  a tool (FR-003, FR-060, NFR-006).
- It registers tool sources **only** through the gateway's public `register_adapter` (FR-021, SC-007).
- It imports only `loopplane.gateway` (`ToolAdapter`), `loopplane.model` (`ToolDescriptor`), and stdlib; it
  does **not** import `ToolGateway` concretely, any Phase-1 runtime internal (`loopplane.controller`,
  `loopplane.context`, `loopplane.approval`, `loopplane.adapters`, `loopplane.tools`), a Phase-2 host symbol,
  or a sibling layer (FR-061, NFR-003).

## Project Structure

### Documentation (this feature)

```text
specs/008-loopplane-tool-gateway-advanced/
├── spec.md / plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── catalog.md            # DiscoveredTool, ToolCatalog, discover; ToolPackage, ToolPlugin, manifest, version, diagnostics
│   └── toolkit-boundary.md   # register_plugin (AdapterRegistrar seam), the boundary + non-execution audit
├── checklists/requirements.md
└── tasks.md                  # Deferred to /speckit.tasks (NOT created by this plan)
```

### Source Code (repository root; created during implementation, not by this plan)

```text
src/loopplane/toolkit/
├── __init__.py        # public exports
├── catalog.py         # DiscoveredTool + ToolCatalog + discover (FR-001-FR-012)
├── plugin.py          # ToolPackage + ToolPlugin + AdapterRegistrar + register_plugin (FR-020-FR-022, FR-030)
├── manifest.py        # CapabilityManifest + build_manifest (FR-031-FR-032)
├── version.py         # Version + parse_version + compare + select_by_policy (FR-040-FR-042)
└── diagnostics.py     # Diagnostic + DiagnosticsReport + diagnose (FR-050-FR-051)

examples/
└── toolkit_quickstart.py  # runnable: discover -> catalog -> manifest -> diagnose -> register (public-safe)

docs/
└── tool-gateway-advanced.md  # public-safe guide: discover -> catalog -> plugin -> manifest -> version -> diagnose

tests/
├── unit/
│   └── test_toolkit_core.py        # DiscoveredTool, discover ordering, raising-describe diagnostic, version compare
├── integration/
│   ├── test_toolkit_us1.py         # US1: discover + catalog from sources, deterministic, raising source (SC-001/002/003)
│   ├── test_toolkit_us2.py         # US2: lookup, listing by source/capability, collision report (SC-004)
│   ├── test_toolkit_us3.py         # US3: plugin bundle + register through register_adapter only (SC-005/007)
│   ├── test_toolkit_us4.py         # US4: capability manifest derived without invocation (SC-005)
│   └── test_toolkit_us5.py         # US5: version select-by-policy + diagnostics over the catalog (SC-008/009)
└── contract/
    └── test_toolkit_boundary.py    # import-boundary + no-invoke audit + determinism (SC-002/005/007)
```

**Structure Decision**: one new sub-package `loopplane.toolkit`, mirroring the Phase-1..7
one-package-per-boundary convention so the layer is a single, clearly-bounded, independently revertible
addition. It depends inward on the public `ToolAdapter` SPI and `ToolDescriptor` identity only. No
Phase-1/2/3 source is modified.

## Implementation Phases

Each phase ends with its tests green and is independently revertible (Constitution X). Detailed tasks are
deferred to [`/speckit.tasks`](./tasks.md).

| Phase | Delivers | Validation gate | Rollback |
|---|---|---|---|
| TA — Foundational + discovery (US1) | `catalog.py` (`DiscoveredTool`, `ToolCatalog`, `discover`) + package skeleton + `__init__` + scripted-adapter helpers — **blocks all stories** | `test_toolkit_core.py` + `test_toolkit_us1.py` green (SC-001/002/003) | Revert package; nothing depends on it |
| TB — Catalog lookup, listing, collisions (US2) | `ToolCatalog` lookup / list-by-source / list-by-capability / collisions | `test_toolkit_us2.py` green (SC-004) | Revert TB |
| TC — Plugin bundle + gateway registration (US3) | `plugin.py` (`ToolPackage`, `ToolPlugin`, `AdapterRegistrar`, `register_plugin`) | `test_toolkit_us3.py` green; registers only via `register_adapter`; no invoke (SC-005/007) | Revert TC |
| TD — Capability manifest (US4) | `manifest.py` (`CapabilityManifest`, `build_manifest`) | `test_toolkit_us4.py` green; built without invocation (SC-005) | Revert TD |
| TE — Versioning + diagnostics (US5) | `version.py` (`Version`, `parse_version`, `compare`, `select_by_policy`), `diagnostics.py` (`Diagnostic`, `DiagnosticsReport`, `diagnose`) | `test_toolkit_us5.py` green; malformed flagged, no invoke (SC-008/009) | Revert TE |
| TF — Example, docs, boundary | `examples/toolkit_quickstart.py`, `docs/tool-gateway-advanced.md`, `test_toolkit_boundary.py` + public-safety `PHASE8_TARGETS` | boundary + no-invoke + determinism green; example runs; scan clean (SC-002/005/006/007) | Revert per item |

## Risk & Rollback Strategy

| Risk | Mitigation |
|---|---|
| Executing or invoking a tool (Constitution V breach) | The layer reads only `describe()` and never holds a path to `invoke`; a contract test asserts no `invoke` call and the import audit forbids execution surfaces (FR-060, NFR-006, SC-005) |
| Bypassing the gateway to register tools | Registration goes only through the host-supplied `AdapterRegistrar.register_adapter`; a recording registrar test asserts each source is handed to the gateway exactly once (FR-021, SC-007) |
| Reaching a Phase-1 runtime internal or the concrete `ToolGateway` | Import-boundary audit: `loopplane.toolkit` imports only `loopplane.gateway` (`ToolAdapter`), `loopplane.model` (`ToolDescriptor`), stdlib; references no `ToolGateway` / `loopplane.controller` / host symbol (FR-061, NFR-003, SC-007) |
| A source whose `describe()` raises crashing discovery | Discovery catches per-source and records a diagnostic; the source contributes no tools (FR-004, NFR-005, SC-003) |
| A silent duplicate-name overwrite (then a gateway hard error later) | The catalog detects collisions and reports them as diagnostics **before** registration; a collision test asserts no silent overwrite (FR-012, NFR-005, SC-004) |
| A malformed version/schema silently passing | `parse_version` and the schema check map malformed input to an explicit, public-safe finding/error (FR-042, FR-050, NFR-005, SC-008) |
| Non-determinism in ordering/selection | No I/O/clock/randomness; discovery and listings sort by `(source, name)`; version order is total; a determinism test runs discovery twice (NFR-001, SC-002/009) |
| Scope creep into remote/MCP-live/dynamic-loading | Out-of-scope list + reserved extension points (FR-090–FR-094); Constitution III review gate; only deterministic, offline tooling ships |

**Rollback posture**: `loopplane.toolkit` is purely **additive** over Phase 1 — small, task-scoped commits,
each phase (TA–TF) independently revertible. The layer owns no state, executes nothing, and registers only
through the gateway, so reverting any or all leaves the gateway, runtime, and every loop layer untouched.

## Constitution Check

*GATE: evaluated against constitution v1.0.0 before Phase 0 research; re-checked after the design above.*

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| I | Spec-First Development | PASS | Plan derives from approved spec.md; every design element cites FRs; tasks deferred to `/speckit.tasks` |
| II | Greenfield Implementation | PASS | New `loopplane.toolkit` written fresh; composes the public tool contracts; no legacy code copied (FR-062) |
| III | Agent Harness Before Loop Automation | PASS | A deterministic, offline tool-ecosystem layer over the existing gateway SPI; ships **no** remote/live/dynamic loading and names every reserved extension point (FR-090–FR-094) |
| IV | Runtime Boundary Clarity | PASS | One new bounded package, single responsibility (organize the tool ecosystem above the gateway); depends inward on public tool contracts; boundary table assigns ownership; no execution logic (FR-060, FR-061) |
| V | Tool Gateway Ownership | PASS | **Central to this phase**: the layer never resolves/authorizes/executes/sandboxes a tool; it reads `describe()` only and registers solely through the gateway's public `register_adapter`; a no-invoke contract test enforces it (FR-021, FR-060, FR-062, NFR-006) |
| VI | Runtime Event Bus Ownership | PASS | Consumes and emits no Runtime/Loop Events; diagnostics are plain return values, never a competing event stream (FR-050) |
| VII | Public-Safe Documentation | PASS | No secrets/paths/private names in any artifact; catalog/manifest carry only public tool identities + host metadata; scan extended with PHASE8 targets (NFR-002, SC-006) |
| VIII | No SDK Replacement | PASS | No agent/tool framework introduced; pure stdlib composition over LoopPlane's own gateway SPI |
| IX | Reference, Not Clone | PASS | Tool-registry/manifest/versioning concepts re-derived public-safe from the spec and the public SPI; no raw reference excerpts |
| X | Testable Evolution | PASS | Each phase (TA–TF) has required tests, a validation gate, and a rollback note; the package is additive and revertible; determinism + fail-safe + non-execution first-class |

**Post-design re-check**: PASS — the entity model, contracts, and boundary introduce no violation and no
Phase-1/2/3 modification. The layer owns no mutable runtime state and executes nothing. Complexity Tracking
is empty.

## Complexity Tracking

No constitution violations to justify — table intentionally empty.
