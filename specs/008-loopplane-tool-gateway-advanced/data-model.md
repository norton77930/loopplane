# Data Model: Advanced Tool Gateway Layer (Phase-8)

All types are public-safe value types or narrow protocols. The layer owns no mutable runtime state and
executes nothing. Types mirror the existing Phase-1/3 style: frozen dataclasses + `Protocol`,
`from __future__ import annotations`, `TYPE_CHECKING` imports to keep the boundary tight.

## 1. Discovered Tool (FR-001)

```python
@dataclass(frozen=True)
class DiscoveredTool:
    source: str                       # provenance (the ToolDescriptor.source)
    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    input_schema: Mapping[str, object]
```

- A public-safe projection of a `ToolDescriptor` plus its provenance. Carries no adapter reference and no
  invocation path (the catalog is identity-only).

## 2. Tool Catalog & discovery (FR-002-FR-012)

```python
def discover(sources: Sequence[ToolAdapter]) -> ToolCatalog: ...

@dataclass(frozen=True)
class ToolCatalog:
    tools: tuple[DiscoveredTool, ...]       # sorted by (source, name)
    failed_sources: tuple[str, ...]         # sources whose describe() raised, sorted

    def lookup(self, name: str) -> DiscoveredTool | None: ...      # first by (source, name); None if absent
    def list(self) -> tuple[DiscoveredTool, ...]: ...
    def list_by_source(self, source: str) -> tuple[DiscoveredTool, ...]: ...
    def list_by_capability(
        self, *, read_only: bool | None = None, concurrency_safe: bool | None = None
    ) -> tuple[DiscoveredTool, ...]: ...
    def collisions(self) -> tuple[str, ...]: ...      # tool names with >= 2 entries, sorted
```

- `discover` iterates sources, calls `describe()` on each (never `invoke`), and builds `DiscoveredTool`s from
  the returned `ToolDescriptor`s. A source whose `describe()` raises contributes no tools and its label is
  recorded in `failed_sources` (fail-safe; FR-004, NFR-005).
- `tools` is sorted by `(source, name)` for determinism (NFR-001). `lookup` returns the first match by that
  order or `None` (never raises; FR-010). `collisions()` reports names that appear two or more times — the
  exact case that would make the gateway's `register_adapter` raise (FR-012, SC-004).
- The catalog holds **no** adapter reference and offers **no** execution path.

## 3. Tool Package, Plugin & registration (FR-020-FR-022, FR-030)

```python
@dataclass(frozen=True)
class ToolPackage:
    name: str
    version: str                              # "X.Y.Z" (see §5)
    description: str = ""
    source: str = ""
    capability_tags: tuple[str, ...] = ()

@dataclass(frozen=True)
class ToolPlugin:
    name: str
    package: ToolPackage
    adapters: tuple[ToolAdapter, ...]

class AdapterRegistrar(Protocol):
    def register_adapter(self, adapter: ToolAdapter) -> None: ...

def register_plugin(plugin: ToolPlugin, registrar: AdapterRegistrar) -> None: ...
```

- `register_plugin` calls `registrar.register_adapter(adapter)` for each of the plugin's adapters and nothing
  else — registration flows solely through the gateway's public entry point (FR-021, SC-007). The host's
  `ToolGateway` satisfies `AdapterRegistrar` structurally, so the layer never imports the concrete gateway.
- The layer never invokes a tool; after registration the plugin's tools execute only through the gateway
  (FR-022, NFR-006).

## 4. Capability Manifest (FR-031-FR-032)

```python
@dataclass(frozen=True)
class CapabilityManifest:
    tool_name: str
    source: str
    read_only: bool
    concurrency_safe: bool
    package: str
    package_version: str
    tags: tuple[str, ...]

def build_manifest(tool: DiscoveredTool, package: ToolPackage) -> CapabilityManifest: ...
```

- `build_manifest` derives the manifest from the tool's declared identity (`read_only`, `concurrency_safe`,
  `source`) plus the package's declared `capability_tags` — deterministically and **without invoking** the
  tool (FR-031, FR-032, NFR-006).

## 5. Versioning (FR-040-FR-042)

```python
@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

def parse_version(text: str) -> Version: ...      # "X.Y.Z"; malformed -> ToolkitError
def select_by_policy(
    packages: Sequence[ToolPackage], *, policy: Literal["highest"] = "highest"
) -> ToolPackage | None: ...

class ToolkitError(RuntimeError):
    """A public-safe error for a malformed version or input."""
```

- `Version` is `(major, minor, patch)` with a total order (`order=True`). `parse_version` maps a malformed
  string to an explicit `ToolkitError`, never a silent default (FR-042, SC-008).
- `select_by_policy` chooses deterministically (default: the highest version); an empty input yields `None`.
  Determinism is total (NFR-001, SC-009).

## 6. Diagnostics (FR-050-FR-051)

```python
DiagnosticKind = Literal[
    "describe_failed", "name_collision", "missing_schema", "malformed_schema", "capability_conflict"
]

@dataclass(frozen=True)
class Diagnostic:
    kind: DiagnosticKind
    subject: str
    detail: str

@dataclass(frozen=True)
class DiagnosticsReport:
    findings: tuple[Diagnostic, ...]

    def ok(self) -> bool: ...      # True when there are no findings

def diagnose(catalog: ToolCatalog) -> DiagnosticsReport: ...
```

- `diagnose` reads catalog data only (no invocation, no live probe; FR-051) and returns ordered, public-safe
  findings for: a source whose `describe()` failed (`describe_failed`), a tool name appearing from two or more
  sources (`name_collision`), a missing or non-mapping `input_schema` (`missing_schema` / `malformed_schema`),
  and a capability conflict (`capability_conflict`). Findings are sorted deterministically by `(kind, subject)`.

## Relationships

```text
ToolAdapter.describe() ──► ToolDescriptor[]
        │ discover (describe only; per-source fail-safe)
        ▼
   DiscoveredTool[]  ──► ToolCatalog (sorted, collision-aware, query methods)
        │                         │ diagnose
        │ build_manifest          ▼
        ▼                  DiagnosticsReport
   CapabilityManifest

ToolPlugin(package, adapters) ──register_plugin──► AdapterRegistrar.register_adapter (host ToolGateway)
ToolPackage.version ──parse_version──► Version ──select_by_policy──► ToolPackage
```

## Validation & invariants

- **Determinism (NFR-001)**: every function is pure over its inputs; ordering is by `(source, name)` /
  `(kind, subject)` / version order; no I/O, clock, or randomness.
- **Non-execution (NFR-006)**: no `invoke` call anywhere; the catalog holds identities, not invocation paths.
- **Fail-safe (NFR-005)**: a raising `describe()`, a malformed schema/version, a name collision, or an absent
  lookup maps to a recorded diagnostic / explicit error / clear not-found — never a crash, hang, silent pass,
  or silent overwrite.
- **Public-safe (NFR-002)**: entries carry public tool identities + host-declared metadata only — no secrets,
  paths, or private names.
