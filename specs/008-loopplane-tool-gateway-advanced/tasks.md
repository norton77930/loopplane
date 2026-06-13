---
description: "Task list for Advanced Tool Gateway Layer (008)"
---

# Tasks: Advanced Tool Gateway Layer

**Input**: Design documents from `/specs/008-loopplane-tool-gateway-advanced/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED per Constitution Principle X. Each phase writes its tests first (they must FAIL before
implementation), then implements until green.

**Organization**: Tasks are grouped by user story (US1–US5). Plan phases TA–TF map below; Foundational
(value types) blocks all stories. US1 is discovery (the MVP); US2 enriches the catalog; US3–US5 add plugins,
manifests, versioning, and diagnostics.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no incomplete-task dependency. New package: `src/loopplane/toolkit/`.

## Boundary reminder (every implementation task)

The layer composes only the **public** Phase-1 tool contracts: `ToolAdapter` (`loopplane.gateway`, read
`describe()` only — **never `invoke`**) and `ToolDescriptor` (`loopplane.model`), plus a narrow
`AdapterRegistrar` protocol the host's `ToolGateway` satisfies. It MUST NOT import the concrete `ToolGateway`,
any Phase-1 runtime internal (`loopplane.controller`, `loopplane.context`, `loopplane.approval`,
`loopplane.adapters`, `loopplane.tools`), a Phase-2 host symbol, or a sibling layer. It **never executes a
tool** and starts no run (Constitution V). See [contracts/toolkit-boundary.md](./contracts/toolkit-boundary.md).
No Phase-1/2/3 source is modified.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the `loopplane.toolkit` package skeleton: `src/loopplane/toolkit/__init__.py` with a module docstring and an empty `__all__` placeholder.
- [X] T002 [P] Add toolkit test helpers in `tests/toolkit_helpers.py`: a `tool_descriptor(name, *, source="internal", read_only=False, concurrency_safe=False, input_schema=None)` builder over the public `ToolDescriptor`; a `ScriptedToolAdapter(descriptors, *, raising=False)` whose `describe()` returns the descriptors (or raises when `raising`) and whose `invoke` raises immediately (to catch any accidental invocation); and a `RecordingRegistrar` that records each `register_adapter(adapter)` call.

---

## Phase 2: Foundational (Blocking Prerequisites — value types)

**Purpose**: The recalled tool-identity value type and the catalog container every story builds on.
**⚠️ Blocks US1–US5.**

- [X] T003 [P] Write unit tests in `tests/unit/test_toolkit_core.py` (MUST FAIL first): `DiscoveredTool` carries `source` / `name` / `description` / `read_only` / `concurrency_safe` / `input_schema`; `ToolCatalog(tools, failed_sources)` exposes `list()` returning its tools; an empty catalog lists nothing (FR-001).
- [X] T004 [P] Implement `src/loopplane/toolkit/catalog.py` value types: the frozen `DiscoveredTool` and the `ToolCatalog` dataclass (fields `tools`, `failed_sources`) with `list()` (FR-001).
- [X] T005 Populate `src/loopplane/toolkit/__init__.py` exports for `DiscoveredTool` and `ToolCatalog`.
- [X] T006 Run `pytest tests/unit/test_toolkit_core.py --basetemp=".pytmp"` → green (gate for Foundational).

**Checkpoint**: The tool-identity vocabulary and the catalog container are ready.

---

## Phase 3: User Story 1 - Discover and catalog the tools a set of sources expose (Priority: P1) 🎯 MVP

**Goal**: `discover(sources)` reads each source's `describe()` and assembles a deterministic, public-safe
catalog keyed by `(source, name)`; a source that fails to describe is recorded, never crashing the pass.

**Independent Test**: Given scripted sources exposing known identities, assert the catalog lists every tool
with its source in deterministic order; a raising source is recorded in `failed_sources`; no tool is invoked.

- [X] T007 [P] [US1] Write integration tests in `tests/integration/test_toolkit_us1.py` (MUST FAIL first): `discover([a, b])` lists every tool keyed by `(source, name)` in deterministic order; discovering twice is identical; a source whose `describe()` raises contributes no tools and is recorded in `failed_sources` with no crash; discovery never calls `invoke` (the scripted adapter's `invoke` raises if reached) (US1 scenarios 1–3; SC-001/002/003).
- [X] T008 [US1] Implement `discover(sources)` in `src/loopplane/toolkit/catalog.py`: iterate sources, call `describe()` only, build `DiscoveredTool`s, sort by `(source, name)`; a raising `describe()` records the source in `failed_sources` (fail-safe) (FR-002–FR-004, NFR-005/NFR-006).
- [X] T009 [US1] Export `discover` from `__init__.py`; run `pytest tests/integration/test_toolkit_us1.py --basetemp=".pytmp"` → green.

**Checkpoint**: MVP — a host produces a complete, deterministic tool inventory from its sources.

---

## Phase 4: User Story 2 - Look up and list catalog tools, surfacing collisions (Priority: P2)

**Goal**: Deterministic lookup by name, listing by source/capability, and explicit collision detection.

**Independent Test**: With a catalog from two sources sharing a tool name, assert lookup returns the
documented occurrence, listing is deterministic, and the collision is reported.

- [X] T010 [P] [US2] Write integration tests in `tests/integration/test_toolkit_us2.py` (MUST FAIL first): `lookup(name)` returns the first match by `(source, name)` or `None` (never raises); `list_by_source` and `list_by_capability(read_only=…, concurrency_safe=…)` are deterministic; two sources exposing the same tool name ⇒ `collisions()` reports that name and no entry is silently overwritten (US2 scenarios 1–3; SC-004, FR-010–FR-012).
- [X] T011 [US2] Extend `ToolCatalog` in `src/loopplane/toolkit/catalog.py` with `lookup`, `list_by_source`, `list_by_capability`, and `collisions` (FR-010–FR-012).
- [X] T012 [US2] Run `pytest tests/integration/test_toolkit_us2.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1 + US2 — the catalog is queryable and collision-aware.

---

## Phase 5: User Story 3 - Bundle tool sources as a plugin and register through the gateway (Priority: P2)

**Goal**: A named Tool Plugin groups sources + package metadata and registers only through the gateway's
public `register_adapter`; the layer invokes no tool.

**Independent Test**: Register a plugin against a recording registrar; assert each source was handed to
`register_adapter` exactly once and no tool was invoked.

- [X] T013 [P] [US3] Write integration tests in `tests/integration/test_toolkit_us3.py` (MUST FAIL first): `register_plugin(plugin, RecordingRegistrar())` calls `register_adapter` once per adapter in order; the layer never invokes a tool; `ToolPackage`/`ToolPlugin` carry their metadata (US3 scenarios 1–2; SC-005/007, FR-020–FR-022).
- [X] T014 [US3] Implement `src/loopplane/toolkit/plugin.py`: `ToolPackage`, `ToolPlugin`, the `AdapterRegistrar` Protocol, and `register_plugin(plugin, registrar)` (calls `registrar.register_adapter` per adapter and nothing else) (FR-020–FR-022, FR-030).
- [X] T015 [US3] Export `ToolPackage`, `ToolPlugin`, `AdapterRegistrar`, `register_plugin`; run `pytest tests/integration/test_toolkit_us3.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US3 — tools can be inventoried and bundled, executing only through the gateway.

---

## Phase 6: User Story 4 - Inspect what a tool or package can do without invoking it (Priority: P2)

**Goal**: A deterministic Capability Manifest derived from a tool's declared identity + package metadata,
built without invocation.

**Independent Test**: For a tool with known declared attributes and package metadata, assert the manifest
reflects read-only / concurrency-safe / source / package / tags deterministically, with no tool invoked.

- [X] T016 [P] [US4] Write integration tests in `tests/integration/test_toolkit_us4.py` (MUST FAIL first): `build_manifest(tool, package)` reflects `read_only` / `concurrency_safe` / `source` / package name+version / `tags`; identical inputs ⇒ identical manifest; no tool is invoked (US4 scenarios 1–2; SC-005, FR-031/FR-032).
- [X] T017 [US4] Implement `src/loopplane/toolkit/manifest.py`: `CapabilityManifest` and `build_manifest(tool, package)` deriving from the declared identity + package tags (FR-031–FR-032).
- [X] T018 [US4] Export `CapabilityManifest`, `build_manifest`; run `pytest tests/integration/test_toolkit_us4.py --basetemp=".pytmp"` → green.

**Checkpoint**: US1–US4 — tools are inventoried, bundled, and capability-inspectable.

---

## Phase 7: User Story 5 - Version packages and diagnose the catalog (Priority: P3)

**Goal**: Explicit, deterministic versioning + a read-only diagnostics pass.

**Independent Test**: With packages at versions, assert comparison/selection is deterministic and a malformed
version is flagged; run diagnostics over a catalog with a duplicate name and a malformed schema and assert
both are reported.

- [X] T019 [P] [US5] Write integration tests in `tests/integration/test_toolkit_us5.py` (MUST FAIL first): `parse_version("1.2.3")` ⇒ `Version(1,2,3)`; a malformed version ⇒ `ToolkitError`; `Version` order is total; `select_by_policy(packages)` picks the highest deterministically and an empty input ⇒ `None`; `diagnose(catalog)` reports `name_collision`, `missing_schema`/`malformed_schema`, and `describe_failed`, sorted by `(kind, subject)`, invoking no tool (US5 scenarios 1–2; SC-008/009, FR-040–FR-042, FR-050/FR-051).
- [X] T020 [US5] Implement `src/loopplane/toolkit/version.py`: `Version` (`order=True`), `parse_version` (malformed ⇒ `ToolkitError`), `select_by_policy`, and `ToolkitError` (FR-040–FR-042).
- [X] T021 [US5] Implement `src/loopplane/toolkit/diagnostics.py`: `DiagnosticKind`, `Diagnostic`, `DiagnosticsReport`, and `diagnose(catalog)` (reads catalog data only; never invokes) (FR-050–FR-051).
- [X] T022 [US5] Export the version + diagnostics types; run `pytest tests/integration/test_toolkit_us5.py --basetemp=".pytmp"` → green.

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T023 [P] Write contract tests in `tests/contract/test_toolkit_boundary.py`: an import-boundary audit (every `src/loopplane/toolkit/*.py` imports only `loopplane.gateway` / `loopplane.model` / `loopplane.toolkit` + stdlib, and references no `ToolGateway` / `loopplane.controller` / `loopplane.context` / `loopplane.approval` / `loopplane.adapters` / `loopplane.tools` / `loopplane.host` / sibling-layer token); a **no-invoke** audit (no `.invoke(` reference in any toolkit module); determinism (`discover` twice ⇒ identical); registration reaches the gateway only through `register_adapter` (FR-060/FR-061, NFR-003/NFR-006, SC-002/005/007).
- [X] T024 [P] Extend `tests/contract/test_public_safety.py` with `PHASE8_TARGETS` (`src/loopplane/toolkit`, `examples/toolkit_quickstart.py`, `docs/tool-gateway-advanced.md`, `specs/008-loopplane-tool-gateway-advanced`) and a `test_phase8_toolkit_files_are_public_safe` scan.
- [X] T025 [P] Create `examples/toolkit_quickstart.py`: a public-safe, credential-free runnable `discover → catalog → build_manifest → diagnose → register_plugin` over scripted adapters + a recording registrar, invoking no tool (per [quickstart.md](./quickstart.md)).
- [X] T026 [P] Create `docs/tool-gateway-advanced.md`: a public-safe guide — `discover → catalog → plugin → manifest → version → diagnose`, Constitution V (the gateway owns execution), and the reserved extension points (FR-090–FR-094).
- [X] T027 Finalize `src/loopplane/toolkit/__init__.py` public `__all__`; run `ruff format` + `ruff check` + `mypy` (strict) → clean.
- [X] T028 Run the full suite `pytest --basetemp=".pytmp"` → green; run `python examples/toolkit_quickstart.py`; confirm the public-safety scan is green (SC-006); update the board status to **Verified**.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — **blocks US1–US5** (the value types).
- **US1 (Phase 3)**: depends on Foundational. MVP (discovery).
- **US2 (Phase 4)**: depends on US1 (extends the catalog).
- **US3 (Phase 5)**, **US4 (Phase 6)**, **US5 (Phase 7)**: depend on Foundational (US4 also on `DiscoveredTool`
  from US1); independent of each other.
- **Polish (Phase 8)**: depends on all desired user stories.

### Within each phase

- Tests are written first and MUST FAIL before implementation.
- Value types before discovery; discovery before catalog queries (US2); each phase ends on its pytest gate.
- Commit per stable phase; push after each safe commit.

## Parallel Opportunities

- T002 (helpers) runs alongside the Phase-2 test authoring.
- Within Foundational: T003 (test) and T004 (value types) are `[P]`.
- Across stories: US3/US4/US5 modules (`plugin.py`, `manifest.py`, `version.py`/`diagnostics.py`) are
  independent files — their `[P]` test-authoring and implementation can proceed in parallel once Foundational
  + US1 are green.
- Polish: T023–T026 are independent files (`[P]`); T027/T028 are the final serial gates.

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → Phase 2 Foundational (value types) → Phase 3 US1 (discovery).
2. **STOP and VALIDATE**: a host produces a deterministic, public-safe tool inventory from its sources, with
   a raising source recorded and no tool invoked.

### Incremental Delivery

Foundational → US1 (MVP) → US2 (queries) → US3 (plugins) → US4 (manifests) → US5 (versioning + diagnostics)
→ Polish. Each phase is an independently testable, revertible increment; no Phase-1/2/3 source is modified.

## Notes

- `[P]` = different files, no incomplete-task dependency. `[Story]` maps a task to its user story.
- The layer reads `describe()` only and **never invokes a tool**; tests assert no invocation and that
  registration flows solely through `register_adapter`.
- Commit after each stable phase (board §11); push after each safe commit.
- Avoid: importing the concrete `ToolGateway` / runtime internals / sibling layers; calling `invoke`;
  silently overwriting a colliding tool name; a silent malformed-version/schema pass.
