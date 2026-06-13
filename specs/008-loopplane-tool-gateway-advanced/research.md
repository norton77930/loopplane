# Research: Advanced Tool Gateway Layer (Phase-8)

Phase-0 decisions for `loopplane.toolkit`. Every decision composes the public Phase-1 tool contracts and
re-derives none of them; the Tool Gateway keeps execution (Constitution V).

## Inherited context, no re-derivation (NFR-003)

The layer consumes these **public** surfaces verbatim and adds only organization above them:

| Surface | Source (public) | Used by |
|---|---|---|
| `ToolAdapter` (`describe() -> Sequence[ToolDescriptor]`, `invoke`, `shutdown`) | `loopplane.gateway` | discovery reads **`describe()` only** |
| `ToolDescriptor` (`name`, `description`, `input_schema`, `concurrency_safe`, `read_only`, `source`) | `loopplane.model` | the discovered tool identity |
| `register_adapter(adapter)` (the gateway's public registration; raises on a duplicate tool name) | host `ToolGateway` via a narrow `AdapterRegistrar` protocol | plugin registration |

The concrete `ToolGateway`, the runtime, and the concrete adapters (`InternalToolAdapter`, `MCPToolAdapter`)
are **not** imported — tools are discovered through the abstract `ToolAdapter`, and registration goes through
a host-supplied `AdapterRegistrar` (Decision 4).

## Decision 1 — Discovery reads `describe()` only; never `invoke`

- **Decision**: `discover(sources)` iterates an ordered set of `ToolAdapter`s, calls `describe()` on each,
  and collects the returned `ToolDescriptor`s into a catalog. It never calls `invoke` and never executes a
  tool.
- **Rationale**: `describe()` is the public discovery surface; execution is exclusively the gateway's
  (Constitution V, FR-060, NFR-006). Reading identities is side-effect-free and deterministic.
- **Alternatives rejected**: *Probing tools by invoking them* — violates Constitution V and determinism;
  rejected.

## Decision 2 — A `DiscoveredTool` pairs a source label with the public tool identity

- **Decision**: `DiscoveredTool` carries `source: str`, `name: str`, `description: str`, `read_only: bool`,
  `concurrency_safe: bool`, and the `input_schema` (a mapping). It is a public-safe projection of
  `ToolDescriptor` plus the source label.
- **Rationale**: the catalog needs the identity + provenance without holding adapter references or invocation
  paths (FR-001). Carrying the descriptor's own `source` *and* the discovery source label disambiguates.
- **Alternatives rejected**: *Holding the live `ToolAdapter` on each entry* — would invite invocation;
  rejected (the catalog is identity-only; registration uses the plugin's adapters).

## Decision 3 — The catalog is keyed by `(source, name)`, ordered deterministically, collision-aware

- **Decision**: `ToolCatalog` holds `DiscoveredTool`s keyed by `(source, name)` and exposes deterministic
  `lookup(name)`, `list()`, `list_by_source(source)`, `list_by_capability(...)`, and `collisions()`. Ordering
  is by `(source, name)`. A **collision** is the same `name` from two or more sources.
- **Rationale**: the gateway registers by **global** tool name and raises `ValueError` on a duplicate
  (`register_adapter` → `_add`). Detecting collisions *before* registration (FR-012, SC-004) is the catalog's
  key value — a host can resolve them rather than hitting the gateway's hard error. `(source, name)` keying
  preserves provenance while making collisions explicit.
- **Alternatives rejected**: *Keying by name only* — loses provenance and silently overwrites (the exact
  failure SC-004 forbids); rejected.

## Decision 4 — Registration through a narrow `AdapterRegistrar` protocol

- **Decision**: define `AdapterRegistrar(Protocol)` with `register_adapter(adapter: ToolAdapter) -> None`;
  the host's `ToolGateway` satisfies it structurally. `register_plugin(plugin, registrar)` calls
  `registrar.register_adapter(adapter)` for each of the plugin's adapters.
- **Rationale**: keeps the import boundary to `{loopplane.gateway, loopplane.model}` — the concrete
  `ToolGateway` is never imported (FR-061, NFR-003). Registration still flows solely through the gateway's
  public entry point (FR-021, SC-007). Mirrors how Phase-7 used a narrow `ArtifactReader`.
- **Alternatives rejected**: *Importing and depending on the concrete `ToolGateway`* — widens the boundary
  unnecessarily; the protocol suffices.

## Decision 5 — Capability manifest is derived, never probed

- **Decision**: `build_manifest(tool, package)` produces a `CapabilityManifest` from the `DiscoveredTool`'s
  declared flags (`read_only`, `concurrency_safe`, `source`) plus the `ToolPackage`'s declared capability
  tags. Deterministic; no invocation.
- **Rationale**: FR-031/FR-032 — a host inspects what a tool can do before using it, from declared identity
  only. This also feeds Phase-9 governance.
- **Alternatives rejected**: *Inferring capability by trial execution* — violates non-execution; rejected.

## Decision 6 — Versioning is a deterministic semantic scheme

- **Decision**: `Version` is `(major, minor, patch)` parsed from a `"X.Y.Z"` string by `parse_version`;
  comparison is the natural tuple order; `select_by_policy(packages, policy)` picks deterministically (default
  policy: highest version). A malformed version string raises an explicit, public-safe error.
- **Rationale**: FR-040–FR-042, SC-008/009 — deterministic, offline, model-agnostic; no network resolution.
- **Alternatives rejected**: *Full SemVer with pre-release/build metadata* — more than this phase needs;
  `major.minor.patch` is sufficient and deterministic (richer ranges are a reserved concern).

## Decision 7 — Diagnostics is a deterministic, read-only pass

- **Decision**: `diagnose(catalog)` returns a `DiagnosticsReport` of explicit `Diagnostic`s for: duplicate
  tool names across sources, a missing or malformed `input_schema` (not a mapping / empty when required), and
  a capability conflict (e.g., a tool both `read_only` and declared mutating by its package). It reads catalog
  data only.
- **Rationale**: FR-050/FR-051 — a public-safe health check that never executes a tool or probes liveness.
- **Alternatives rejected**: *Live health probes / pinging tools* — execution + non-determinism; reserved.

## Decision 8 — Determinism, fail-safe, non-execution, non-mutation are first-class

- **Determinism (NFR-001/SC-002/009)**: no I/O, network, clock, or randomness; discovery and listings sort by
  `(source, name)`; version order is total.
- **Fail-safe (NFR-005/SC-003/008)**: a raising `describe()` is caught per source and recorded as a
  diagnostic (the source contributes no tools); a malformed schema/version is flagged explicitly; a duplicate
  name is reported, never silently overwritten; an absent lookup returns a clear not-found.
- **Non-execution (NFR-006/SC-005)**: the layer never calls `invoke`; a contract test asserts zero
  invocations. The catalog holds identities, not invocation paths.
- **Non-mutation**: discovery and the passes only read; they mutate no adapter, gateway, or descriptor.

## Decision 9 — Diagnostics and findings are plain return values, not an event stream

- **Decision**: collisions and diagnostics are carried on the returned catalog/report values, not on the
  Runtime or Loop Event bus.
- **Rationale**: FR-050 + Constitution VI — the layer owns no event stream and must not compete with the
  existing buses; plain public-safe values suffice.
