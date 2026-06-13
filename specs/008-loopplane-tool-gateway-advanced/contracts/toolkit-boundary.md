# Contract: Registration Seam & the Layer Boundary

The toolkit organizes the tool ecosystem **above** the Tool Gateway; the gateway keeps execution
(Constitution V). This contract pins the registration seam and the import/non-execution boundary.

## Registration seam (FR-021, FR-022)

```python
class AdapterRegistrar(Protocol):
    def register_adapter(self, adapter: ToolAdapter) -> None: ...

def register_plugin(plugin: ToolPlugin, registrar: AdapterRegistrar) -> None: ...
```

- `register_plugin` hands each of the plugin's adapters to `registrar.register_adapter` and does nothing
  else. The host's `ToolGateway` is the registrar; the layer never imports the concrete `ToolGateway`.
- Registration is the **only** way the layer touches the gateway, and the gateway remains the only thing that
  resolves, authorizes, and executes the registered tools (FR-021, FR-022, SC-007).

## Boundary (FR-060, FR-061, NFR-003, NFR-006)

```text
loopplane.toolkit  ──imports──►  loopplane.gateway   (ToolAdapter)
                   ──imports──►  loopplane.model     (ToolDescriptor)
                   ──imports──►  (stdlib only otherwise)
```

Prohibited (asserted by the import + no-invoke audit, `test_toolkit_boundary.py`):

- The layer **never invokes or executes a tool**: it reads `ToolAdapter.describe()` only and never calls
  `invoke`; the audit asserts no `.invoke(` reference and no execution surface (FR-060, NFR-006, SC-005).
- It imports **no** concrete `ToolGateway`, **no** Phase-1 runtime internal (`loopplane.controller`,
  `loopplane.context`, `loopplane.approval`, `loopplane.gateway.gateway`, `loopplane.adapters`,
  `loopplane.tools`), **no** Phase-2 host symbol, and **no** sibling layer (`engineering`, `scheduling`,
  `packs`, `review`, `recall`) (FR-061, NFR-003).
- It **starts no Loop Run** and **mutates nothing** — no adapter, gateway, descriptor, or catalog after
  construction.

Allowed `loopplane.*` import prefixes: `loopplane.gateway`, `loopplane.model`, `loopplane.toolkit`.
Everything else is a boundary violation.

## Non-duplication (FR-062, SC-005)

The layer contains no tool resolution, authorization, execution, sizing, timeout, or error-normalization
logic — those stay the Tool Gateway's. It only discovers (via `describe()`), catalogs, bundles, describes
(manifests), versions, and diagnoses, and it registers tool sources only through `register_adapter`.
