# Contract: Discovery, Catalog, Plugins, Manifest, Versioning, Diagnostics

The public surface of `loopplane.toolkit`. All types are public-safe and deterministic; the layer reads
`ToolAdapter.describe()` only and never invokes a tool. Behaviour is normative; signatures are illustrative.

## Discovery & Catalog (FR-001-FR-012)

```python
@dataclass(frozen=True)
class DiscoveredTool:
    source: str
    name: str
    description: str
    read_only: bool
    concurrency_safe: bool
    input_schema: Mapping[str, object]

def discover(sources: Sequence[ToolAdapter]) -> ToolCatalog: ...

@dataclass(frozen=True)
class ToolCatalog:
    tools: tuple[DiscoveredTool, ...]       # sorted by (source, name)
    failed_sources: tuple[str, ...]         # sources whose describe() raised, sorted

    def lookup(self, name: str) -> DiscoveredTool | None: ...
    def list(self) -> tuple[DiscoveredTool, ...]: ...
    def list_by_source(self, source: str) -> tuple[DiscoveredTool, ...]: ...
    def list_by_capability(
        self, *, read_only: bool | None = None, concurrency_safe: bool | None = None
    ) -> tuple[DiscoveredTool, ...]: ...
    def collisions(self) -> tuple[str, ...]: ...
```

- `discover` calls `describe()` per source (never `invoke`); a raising source contributes no tools and is
  recorded in `failed_sources` (FR-003/FR-004, NFR-005/NFR-006). Order is by `(source, name)` (NFR-001).
- `lookup` returns the first match by `(source, name)` or `None` — never raises (FR-010). `collisions()`
  reports names that appear two or more times (the gateway registers by global name and raises on a
  duplicate, so collisions are caught here first; FR-012, SC-004). No entry is silently overwritten.

## Plugins & registration (FR-020-FR-022, FR-030)

```python
@dataclass(frozen=True)
class ToolPackage:
    name: str
    version: str
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

- `register_plugin` calls `registrar.register_adapter(adapter)` for each adapter and nothing else;
  registration flows only through the gateway's public entry point (FR-021, SC-007). The layer invokes no
  tool (FR-022, NFR-006).

## Capability Manifest (FR-031-FR-032)

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

- Derived from the tool's declared identity + the package's declared tags; deterministic, no invocation.

## Versioning (FR-040-FR-042)

```python
@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

class ToolkitError(RuntimeError): ...

def parse_version(text: str) -> Version: ...      # "X.Y.Z"; malformed -> ToolkitError
def select_by_policy(
    packages: Sequence[ToolPackage], *, policy: Literal["highest"] = "highest"
) -> ToolPackage | None: ...
```

- Total order on `(major, minor, patch)`. A malformed version is an explicit `ToolkitError`, never a silent
  default (FR-042, SC-008). Selection is deterministic; empty input yields `None` (SC-009).

## Diagnostics (FR-050-FR-051)

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
    def ok(self) -> bool: ...

def diagnose(catalog: ToolCatalog) -> DiagnosticsReport: ...
```

- `diagnose` reads catalog data only — never invokes a tool or probes liveness (FR-051). Findings are sorted
  by `(kind, subject)` for determinism and cover describe failures, name collisions, missing/malformed input
  schemas, and capability conflicts (FR-050, NFR-005).
