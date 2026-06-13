# Advanced Tool Gateway (`loopplane.toolkit`)

Organize a host's tool ecosystem **above** the Phase-1 Tool Gateway: discover tools, catalog them,
bundle them as plugins, describe their capabilities, track versions, and diagnose problems —
deterministically and offline.

The layer is pure composition over the public `ToolAdapter` SPI (`loopplane.gateway`) and the
`ToolDescriptor` identity (`loopplane.model`). It **never invokes, resolves, authorizes, or executes a
tool** — the Tool Gateway stays the single chokepoint for those (Constitution V). It registers tool sources
only through the gateway's public `register_adapter`.

## The pieces

| Piece | What it does |
|---|---|
| `discover(sources)` | Reads each source's `describe()` (never `invoke`) into a `ToolCatalog` keyed by `(source, name)`; a raising source is recorded in `failed_sources`. |
| `ToolCatalog` | `lookup(name)`, `list()`, `list_by_source`, `list_by_capability(read_only=, concurrency_safe=)`, and `collisions()` (names exposed by two or more sources). |
| `ToolPackage` / `ToolPlugin` | Public-safe package metadata + a named bundle of sources. |
| `register_plugin(plugin, registrar)` | Hands each adapter to the gateway's `register_adapter` and nothing else. |
| `build_manifest(tool, package)` | A deterministic `CapabilityManifest` (read-only, concurrency-safe, source, package, tags) derived without invoking the tool. |
| `parse_version` / `Version` / `select_by_policy` | A `major.minor.patch` scheme with a total order; a malformed version raises `ToolkitError`. |
| `diagnose(catalog)` | A read-only `DiagnosticsReport`: describe failures, name collisions, capability conflicts, missing/malformed input schemas. |

## Using it

```python
from loopplane.toolkit import discover, build_manifest, diagnose, register_plugin, ToolPlugin, ToolPackage

catalog = discover([adapter_a, adapter_b])          # ToolAdapters the host already has
print(catalog.collisions())                          # pre-flight the gateway's duplicate-name error
report = diagnose(catalog)                            # explicit, public-safe findings

plugin = ToolPlugin(name="my-tools", package=ToolPackage("my-tools", "1.2.0"), adapters=(adapter_a,))
register_plugin(plugin, gateway)                      # gateway is the host's ToolGateway
```

The host's `ToolGateway` is the `registrar` — it satisfies the narrow `AdapterRegistrar` protocol, so the
toolkit never imports the concrete gateway. See [`examples/toolkit_quickstart.py`](../examples/toolkit_quickstart.py).

## Determinism, fail-safe, non-execution

- **Deterministic**: no I/O, clock, or randomness; the catalog is sorted by `(source, name)`, the version
  order is total, and diagnostics are sorted by `(kind, subject)`.
- **Fail-safe**: a raising `describe()`, a name collision, or a malformed schema/version maps to a recorded
  diagnostic / explicit error — never a crash, a silent pass, or a silent overwrite.
- **Non-execution**: the layer reads `describe()` only and **never calls `invoke`**; an import + no-invoke
  audit enforces it.

## Boundary

`loopplane.toolkit` imports only the public `loopplane.gateway` (`ToolAdapter`) and `loopplane.model`
(`ToolDescriptor`) contracts and the stdlib. It never imports the concrete `ToolGateway`, a runtime
internal, the host, or a sibling layer, and it starts no run.

## Reserved extension points (named, not built)

A live or remote tool-registry service or remote schema fetch; live MCP server connection and
over-the-network tool discovery (the host supplies an already-connected source); dynamic plugin loading from
disk or a marketplace; runtime hot-reload of tool sources; tool execution or sandboxing (the gateway's
responsibility — sandboxing and execution governance are unit 009).
