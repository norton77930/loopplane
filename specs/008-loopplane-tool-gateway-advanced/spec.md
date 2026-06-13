# Feature Specification: LoopPlane Advanced Tool Gateway Layer

**Feature Branch**: `main` (main-only autopilot)

**Created**: 2026-06-14

**Status**: Draft

**Input**: User description: "Define the LoopPlane Advanced Tool Gateway layer (unit 008) on top of the Phase-1 runtime foundation, composing only its public Tool Gateway contracts (the ToolAdapter SPI, the ToolDescriptor model, and ToolGateway.register_adapter): deterministic, public-safe, offline tooling for discovering, cataloging, bundling, describing, versioning, and diagnosing tool sources — never bypassing the gateway, which remains the single chokepoint that resolves, authorizes, and executes tools (Constitution V)."

## Overview

The Advanced Tool Gateway layer (Phase-8) lets a host **understand and organize its tool ecosystem**
without touching tool execution. It discovers the tools a set of tool sources expose, catalogs them,
bundles them as named plugins, describes their capabilities, tracks their versions, and diagnoses problems
— all deterministically and offline.

It is a **composition layer** over the Phase-1 Tool Gateway: it reads tool identities through the public
**Tool Adapter** discovery surface and registers tool sources only through the gateway's public
registration entry point. It **never** invokes, resolves, authorizes, or executes a tool — the **Tool
Gateway remains the single chokepoint** for those (Constitution V — Tool Gateway Ownership). It adds no
runtime internals, starts no run, and reaches no Phase-1 internal beyond the public tool contracts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover and catalog the tools a set of sources expose (Priority: P1)

A host has several tool sources (an internal tool set, an MCP-backed source, a custom one) and wants a
single, trustworthy inventory of every tool available, with where it came from. The host points the layer
at the sources; it asks each source to **describe** its tools and assembles a deterministic, public-safe
**Tool Catalog** keyed by `(source, name)`. A source that fails to describe itself is recorded as a
diagnostic and contributes no tools — the catalog never crashes.

**Why this priority**: A reliable inventory is the foundation every other capability builds on, and it
exercises the full discover → catalog path. This is the minimum slice that delivers value.

**Independent Test**: Given scripted tool sources exposing known tool identities, assert the catalog lists
every tool with its source in a deterministic order; a source that raises on describe is skipped with a
recorded diagnostic, and no tool is invoked.

**Acceptance Scenarios**:

1. **Given** several sources exposing tools, **When** discovery runs, **Then** the catalog contains every
   tool keyed by `(source, name)` in a deterministic order.
2. **Given** the same sources, **When** discovery runs twice, **Then** the two catalogs are identical.
3. **Given** a source whose describe fails, **When** discovery runs, **Then** that source contributes no
   tools, a diagnostic records the failure, and the rest of the catalog is unaffected.

---

### User Story 2 - Look up and list catalog tools, surfacing collisions (Priority: P2)

A host wants to find a tool by name, list the tools from a given source or with a given capability, and be
warned when two sources expose the same tool name. The Tool Catalog supports deterministic lookup and
listing, and reports name **collisions** explicitly rather than silently overwriting.

**Why this priority**: Lookup and collision-awareness are what make the catalog usable and safe; independent
of bundling/versioning.

**Independent Test**: With a catalog built from two sources that share a tool name, assert lookup returns
the documented occurrence, listing by source/capability is deterministic, and the collision is reported.

**Acceptance Scenarios**:

1. **Given** a catalog, **When** a tool is looked up by name, **Then** the matching entry is returned (or a
   clear "not found", never an error).
2. **Given** two sources exposing the same tool name, **When** the catalog is built, **Then** the collision
   is reported explicitly and no entry is silently overwritten.
3. **Given** a catalog, **When** it is listed by source or capability, **Then** the result is deterministic.

---

### User Story 3 - Bundle tool sources as a named plugin and register through the gateway (Priority: P2)

A host wants to ship a related set of tools together. It groups one or more tool sources plus package
metadata into a named **Tool Plugin**, then registers the plugin with the **Tool Gateway** — and the
plugin's tools become available **only through the gateway**, which still owns their resolution,
authorization, and execution.

**Why this priority**: Bundling is how tools are delivered and wired in; registering through the gateway is
the Constitution V guarantee made concrete.

**Independent Test**: Build a plugin from scripted sources, register it against a Tool Gateway double, and
assert each source was handed to the gateway's public registration exactly once and the layer invoked no
tool itself.

**Acceptance Scenarios**:

1. **Given** a Tool Plugin grouping sources, **When** it is registered, **Then** each source is registered
   with the Tool Gateway through its public registration entry point.
2. **Given** a registered plugin, **When** its tools are used, **Then** they execute only through the
   gateway (the layer never executes a tool).

---

### User Story 4 - Inspect what a tool or package can do without invoking it (Priority: P2)

A host wants to know a tool's capabilities — is it read-only, concurrency-safe, what source and category —
before deciding to use it. The layer derives a deterministic **Capability Manifest** for each tool and
package from the tool's declared identity plus the package metadata, inspectable without ever invoking the
tool.

**Why this priority**: Capability inspection drives safe tool selection (and feeds Phase-9 governance);
independent of versioning/diagnostics.

**Independent Test**: For a tool with known declared attributes and package metadata, assert the manifest
reflects read-only / concurrency-safe / source / declared tags deterministically, with no tool invoked.

**Acceptance Scenarios**:

1. **Given** a tool identity and its package metadata, **When** the manifest is built, **Then** it reports
   the tool's read-only and concurrency-safe attributes, its source, and the package's declared capability
   tags.
2. **Given** the same inputs, **When** the manifest is built twice, **Then** the two manifests are
   identical.

---

### User Story 5 - Version packages and diagnose the catalog (Priority: P3)

A host maintains multiple versions of a tool package and wants to choose among them deterministically, and
wants a health check over the whole catalog. **Tool Packages** carry explicit versions with deterministic
comparison and a select-by-policy helper; a **Diagnostics** pass reports duplicate names, missing or
malformed tool input schemas, capability conflicts, and malformed versions — each as an explicit,
public-safe finding, never executing a tool.

**Why this priority**: Versioning and diagnostics harden the ecosystem; lowest priority because the catalog
delivers value without them.

**Independent Test**: With packages at several versions, assert comparison/selection is deterministic and a
malformed version is flagged; run diagnostics over a catalog with a duplicate name and a malformed schema
and assert both are reported.

**Acceptance Scenarios**:

1. **Given** packages at versions, **When** a selection policy runs, **Then** it picks the documented
   version deterministically; a malformed version is flagged, never silently accepted.
2. **Given** a catalog with a duplicate name and a malformed input schema, **When** diagnostics run, **Then**
   both are reported as explicit, public-safe findings and no tool is invoked.

---

### Edge Cases

- **A source's describe fails** → that source contributes no tools; a diagnostic records it; discovery
  continues.
- **No sources / empty sources** → an empty catalog, no error.
- **Two sources expose the same tool name** → reported as a collision; never silently overwritten.
- **A tool has a missing or malformed input schema** → flagged by diagnostics; never a silent pass.
- **A malformed package version** → flagged explicitly; comparison/selection never crashes.
- **A lookup for an absent tool** → a clear "not found", never an exception.
- **Iterating an unknown future capability tag or source label** → tolerated (forward-compatible).

## Requirements *(mandatory)*

### Discovery & Catalog (US1)

- **FR-001**: The layer MUST define a **Discovered Tool** — a public-safe pairing of a tool's source label
  and its public tool identity (name, description, input schema, read-only, concurrency-safe). It MUST carry
  no secrets or domain data.
- **FR-002**: The layer MUST provide a **discovery** pass that, given an ordered set of tool sources, reads
  each source's public **describe** surface and assembles a **Tool Catalog** of Discovered Tools keyed by
  `(source, name)`, in a deterministic order.
- **FR-003**: Discovery MUST read only the describe surface; it MUST NOT invoke, resolve, authorize, or
  execute any tool (FR-060, Constitution V).
- **FR-004**: A source whose describe raises MUST be recorded as a diagnostic and contribute no tools;
  discovery MUST NOT crash (NFR-005).

### Catalog lookup, listing & collisions (US2)

- **FR-010**: The Tool Catalog MUST support deterministic **lookup by name**, returning the matching
  Discovered Tool or an explicit not-found — never raising.
- **FR-011**: The Tool Catalog MUST support deterministic **listing**, including by source and by capability.
- **FR-012**: The catalog MUST detect and report a **collision** — the same tool name exposed by two
  sources — explicitly; it MUST NOT silently overwrite an entry (FR-050).

### Plugin bundles & gateway registration (US3)

- **FR-020**: The layer MUST define a **Tool Plugin**: a named bundle grouping one or more tool sources plus
  a Tool Package metadata record.
- **FR-021**: The layer MUST provide a **registration** operation that registers a plugin's sources with the
  Tool Gateway **only through the gateway's public adapter-registration entry point** — never a bypass path
  (FR-060, Constitution V).
- **FR-022**: After registration the plugin's tools MUST be available only through the gateway; the layer
  MUST NOT execute, resolve, or authorize any tool itself.

### Package metadata & capability manifest (US4)

- **FR-030**: The layer MUST define a **Tool Package** metadata record carrying a name, a version, a
  description, and a source label — all public-safe, no secrets or domain data.
- **FR-031**: The layer MUST derive a deterministic **Capability Manifest** for each tool and package from
  the tool's public identity (read-only, concurrency-safe, source) plus the package's declared capability
  tags.
- **FR-032**: A Capability Manifest MUST be produced without invoking the tool (FR-060).

### Versioning (US5)

- **FR-040**: A Tool Package MUST carry an explicit **version** with a deterministic comparison order.
- **FR-041**: The layer MUST provide a deterministic **select-by-policy** helper (e.g., the highest
  compatible version) so a host can choose among versions reproducibly.
- **FR-042**: A **malformed version** MUST map to an explicit, public-safe error; comparison and selection
  MUST NOT crash or silently accept it (NFR-005).

### Diagnostics (US5)

- **FR-050**: The layer MUST provide a deterministic **diagnostics** pass over a catalog that reports, as
  explicit public-safe findings: duplicate tool names across sources, a missing or malformed tool input
  schema, a capability conflict, and a describe/version failure.
- **FR-051**: Diagnostics MUST NOT invoke a tool or perform a live health probe; it reads catalog data only.

### Boundary, non-execution & non-duplication

- **FR-060**: The layer MUST NOT invoke, resolve, authorize, execute, or sandbox any tool, and MUST NOT
  start a Loop Run. Tool execution stays the Tool Gateway's responsibility (Constitution V).
- **FR-061**: The layer MUST read only the **public** Phase-1 tool contracts (the Tool Adapter describe
  surface, the Tool Descriptor identity, and the Tool Gateway's public adapter registration). It MUST NOT
  import or reference a Phase-1 runtime internal (the controller, the model/event internals beyond the
  public tool identity), a Phase-2 host symbol, or a sibling phase layer.
- **FR-062**: The layer MUST NOT re-implement tool resolution, authorization, execution, sizing, timeout, or
  error normalization; those remain the Tool Gateway's. It only discovers, catalogs, bundles, describes,
  versions, and diagnoses.

### Reserved extension points

- **FR-090** (reserved, named-not-built): a live or remote tool-registry service or remote schema fetch.
- **FR-091** (reserved): live MCP server connection and over-the-network tool discovery (the host supplies
  an already-connected source; this layer discovers only from its describe).
- **FR-092** (reserved): dynamic plugin loading from disk or a plugin marketplace.
- **FR-093** (reserved): runtime hot-reload of tool sources.
- **FR-094** (reserved): tool execution or sandboxing (the gateway's responsibility; sandboxing/governance
  is unit 009).
  Each reserved point MUST be named in docs and MUST NOT be implemented this phase.

### Non-Functional Requirements

- **NFR-001 (Determinism)**: Given a scripted set of tool sources and identities, every catalog, manifest,
  version comparison/selection, and diagnostics result MUST be identical on every run.
- **NFR-002 (Public-safety)**: No committed artifact may contain secrets, credentials, private paths,
  private project/repository names, internal names, or internal network addresses.
- **NFR-003 (Boundary)**: The layer composes only the public Phase-1 tool contracts; it references no
  Phase-2 host symbol and no runtime internal beyond the public tool identity — enforced by an import audit.
- **NFR-004 (Language & safety)**: All artifacts are English and public-safe.
- **NFR-005 (Fail-safe)**: Every failure mode — a raising describe, a missing/malformed schema, a malformed
  version, a name collision, an absent lookup — MUST map to an explicit, public-safe result (a recorded
  diagnostic, an explicit error, a clear not-found), never a crash, a hang, a silent pass, or a silent
  overwrite.
- **NFR-006 (Non-execution)**: The layer MUST invoke zero tools; tool execution is exclusively the Tool
  Gateway's, reached only through the gateway's public registration.

### Key Entities

- **Discovered Tool**: a source label + the public tool identity (name, description, input schema,
  read-only, concurrency-safe).
- **Tool Catalog / Registry**: an in-memory collection of Discovered Tools with deterministic lookup,
  listing, and collision detection.
- **Tool Plugin**: a named bundle of tool sources + a Tool Package, registerable through the gateway.
- **Tool Package**: metadata — name, version, description, source label, declared capability tags.
- **Capability Manifest**: a deterministic per-tool/per-package capability view derived without invocation.
- **Version**: an explicit package version with deterministic comparison + select-by-policy.
- **Diagnostic / Diagnostics Report**: explicit, public-safe findings over a catalog.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A host produces a complete tool inventory from a set of sources with a single discovery call,
  every tool keyed by source and name.
- **SC-002**: Discovery, catalog, manifest, versioning, and diagnostics are 100% reproducible — re-running
  over the same sources yields identical results.
- **SC-003**: A source that fails to describe never crashes discovery (0 crashes); it is always recorded as
  a diagnostic.
- **SC-004**: Tool-name collisions are always detected and reported (0 silent overwrites across the suite).
- **SC-005**: The layer invokes 0 tools; tool execution occurs only through the Tool Gateway.
- **SC-006**: No committed artifact contains secrets, private paths, internal names, or internal network
  addresses (public-safety scan green).
- **SC-007**: Plugin registration reaches the Tool Gateway only through its public adapter-registration
  entry point — no bypass path (import-boundary audit green).
- **SC-008**: A malformed input schema or version is always flagged explicitly (0 silent passes).
- **SC-009**: Version selection is deterministic — the same packages and policy yield the same chosen
  version every run.
- **SC-010**: The reserved extension points (remote registry, live MCP/network discovery, dynamic plugin
  loading, hot-reload, execution/sandboxing) are absent from the shipped surface.

## Assumptions

- The layer composes the existing public Phase-1 Tool Gateway contracts: the **Tool Adapter** discovery
  surface (`describe`), the **Tool Descriptor** identity (name, description, input schema, concurrency-safe,
  read-only, source), and the Tool Gateway's public **adapter registration**. These exist and are stable
  (unit 001 is Verified).
- **Tool sources are host-supplied.** The layer ships only public-safe in-memory reference/scripted sources
  for examples and tests; it bundles no real tool and connects to no server.
- **Discovery reads `describe` only.** For an MCP-backed or remote source, the host supplies an
  already-connected source; live connection and network discovery are a reserved extension point (FR-091).
- **Versioning uses a deterministic semantic scheme** (major.minor.patch); a malformed version is an
  explicit error, not a silent default.
- The layer **never executes tools**; execution, authorization, sizing, timeout, and error normalization
  stay the Tool Gateway's (Constitution V). Sandboxing and execution governance are unit 009.
- A discovery/diagnostics pass observes a stable set of sources for its duration (determinism is defined
  relative to that snapshot).

## Out of Scope

- Executing, resolving, authorizing, or sandboxing tools (owned by the Tool Gateway — Constitution V).
- Any network, remote, or filesystem-based plugin loading; live MCP connection; remote registries or schema
  fetch.
- Cloud deployment, web, or UI surfaces.
- Any non-deterministic discovery, ordering, or version resolution.
- Re-implementing the Tool Gateway's resolution/authorization/execution/sizing/timeout/error-normalization.
