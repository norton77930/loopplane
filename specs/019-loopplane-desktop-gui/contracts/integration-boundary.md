# Contract: Desktop Integration Boundary

How the desktop app composes the existing units **without changing any of them**.

## Composes the host (units 001/011) over the bridge

- The Python sidecar drives `loopplane.host.LoopPlaneHost.run(prompt, on_event)` and
  serializes events with `loopplane.events.serialize_event` — the same streaming seam
  the web host (011) uses, but over stdio with no server.
- It runs **no tool** (tools run in the host behind the gateway — V) and re-emits no
  bus (it is a consumer of the normalized stream — VI).

## Reuses unit 018 (no copy)

- The renderer reuses 018's `RawEvent` types, the pure `reduce`, and the components via
  a `@web` path alias; the only new renderer code is the `SidecarTransport`. No legacy
  or duplicate UI is written (Constitution VII, FR-003).

## Reuses unit 012's posture

- The desktop follows unit 012's local-sidecar lifecycle (start a local host, stop
  cleanly with no orphan); it changes nothing in unit 012.

## Isolation

- `apps/desktop/` has its own toolchain; `node_modules` and build output are gitignored
  and **excluded from the Python wheel** (hatch targets `src/loopplane`).
- The Python package, `pyproject.toml`, the web API (011), unit 012, and unit 018 are
  **unchanged**. The Python sidecar is loaded by file path in tests, so it adds no
  `loopplane` package and does not affect the api-reference / packaging contracts.

## Reserved

- Packaging a signed, distributable installer (electron-builder, code signing,
  auto-update) is **out of scope** and reserved for a maintainer. The Electron shell's
  launch wiring is typechecked and verified by a manual GUI smoke; the JS gate keeps
  Electron's binary download disabled.
