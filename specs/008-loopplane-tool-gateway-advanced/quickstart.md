# Quickstart & Validation: Advanced Tool Gateway Layer (Phase-8)

A validation guide for `loopplane.toolkit`. It proves the layer discovers, catalogs, bundles, describes,
versions, and diagnoses tool sources deterministically — over scripted `ToolAdapter`s, with no server,
network, or tool execution. Implementation detail lives in [data-model.md](./data-model.md) and
[contracts/](./contracts); these are runnable scenarios.

## Prerequisites

- The repo installed editable with dev tools: `python -m pip install -e .` and `pytest` + `anyio`.
- Phase 1 is Verified (the public `loopplane.gateway` `ToolAdapter` SPI and the `loopplane.model`
  `ToolDescriptor` identity this layer composes).

## What the example shows

`examples/toolkit_quickstart.py` (public-safe, credential-free):

1. Defines two scripted `ToolAdapter`s exposing known `ToolDescriptor`s (one read-only, one not).
2. `discover([...])` → a `ToolCatalog`; prints the inventory, `list_by_capability(read_only=True)`, and
   `collisions()`.
3. `build_manifest(tool, package)` for a tool → prints the capability manifest.
4. `diagnose(catalog)` → prints findings (e.g., a name collision or a malformed schema).
5. `register_plugin(plugin, gateway)` against a recording registrar → prints which adapters were registered
   (no tool is ever invoked).

Run:

```bash
python examples/toolkit_quickstart.py
```

Expected: a deterministic catalog sorted by `(source, name)`, a capability manifest, an explicit diagnostics
report, and a registration log — with no secrets, no paths, and zero tool invocations.

## Validation scenarios (map to user stories & success criteria)

| Scenario | How to validate | Proves |
|---|---|---|
| US1 — discover + catalog | `discover([a, b])` lists every tool keyed by `(source, name)` in deterministic order | SC-001, FR-002 |
| Determinism | `discover(...)` twice yields identical catalogs | SC-002, NFR-001 |
| Raising source | a source whose `describe()` raises ⇒ no tools + recorded in `failed_sources`, no crash | SC-003, FR-004 |
| US2 — lookup / list / collisions | `lookup`, `list_by_source`, `list_by_capability` are deterministic; a shared name ⇒ `collisions()` reports it, no overwrite | SC-004, FR-010-FR-012 |
| US3 — plugin registration | `register_plugin(plugin, recording_registrar)` calls `register_adapter` once per adapter; no `invoke` | SC-005, SC-007, FR-021/FR-022 |
| US4 — capability manifest | `build_manifest(tool, package)` reflects read-only / concurrency-safe / source / tags, no invocation | SC-005, FR-031/FR-032 |
| US5 — versioning | `parse_version` rejects a malformed string; `select_by_policy` picks the highest deterministically | SC-008, SC-009, FR-040-FR-042 |
| US5 — diagnostics | `diagnose(catalog)` reports collisions + missing/malformed schema, no invocation | SC-008, FR-050/FR-051 |
| No execution | contract audit: no `.invoke(` reference anywhere in the layer | SC-005, NFR-006 |
| Boundary | import audit: imports only `loopplane.gateway` / `loopplane.model` + stdlib | SC-007, FR-061 |
| Public-safety | scan committed files + `PHASE8_TARGETS` | SC-006, NFR-002 |

## Test commands

```bash
python -m pytest tests/unit/test_toolkit_core.py tests/integration -k toolkit --basetemp=".pytmp" -q
python -m pytest tests/contract/test_toolkit_boundary.py --basetemp=".pytmp" -q

# Full gates (run before any commit touching source/tests)
python -m ruff format && python -m ruff check && python -m mypy
python -m pytest --basetemp=".pytmp" -q
```

Expected: all toolkit suites green; ruff + mypy(strict) clean; public-safety scan green.

## What this layer does NOT do

It never invokes, resolves, authorizes, executes, or sandboxes a tool (the Tool Gateway owns those —
Constitution V). No remote/live MCP discovery, no remote registry, no dynamic plugin loading, no hot-reload,
no execution governance (reserved — FR-090-FR-094). It only organizes the tool ecosystem above the gateway.
