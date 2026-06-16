# Research: Desktop Packaging (unit 024)

Phase 0 decisions. Desktop-only; additive; the heavy build is reserved manual/CI.

## R1 — A pure, no-electron spawn resolver

- **Decision**: extract the sidecar-launch decision into `electron/sidecar-spawn.ts`,
  `resolveSidecar({ packaged, platform, resourcesPath, devDir, exists? }) → { command, args }`,
  importing **no** `electron`. `main.ts` passes `app.isPackaged` / `process.platform` /
  `process.resourcesPath` and spawns the result.
- **Rationale**: `main.ts` imports `electron` (unavailable in Vitest), so the launch logic
  must live in a pure module to be unit-tested. This is the offline-verifiable core of a
  packaging unit.

## R2 — Frozen-exe name + per-platform suffix

- **Decision**: the frozen sidecar is `loopplane-sidecar` (+ `.exe` on Windows). The
  resolver computes the name from `platform`; the PyInstaller spec's `EXE(name=...)` and
  the electron-builder `extraResources` filter use the same base name.
- **Rationale**: one shared name is what lets the freeze output and the bundle path agree;
  a test asserts it in both files.

## R3 — `extraResources` ↔ `resourcesPath` agreement

- **Decision**: electron-builder `extraResources: [{ from: sidecar/dist, to: sidecar }]`
  puts the frozen exe at `resources/sidecar/loopplane-sidecar*`. In a packaged app the
  resolver looks at `join(process.resourcesPath, "sidecar", name)`. (`process.resourcesPath`
  is the app's `resources/` dir.)
- **Rationale**: the resolver path and the bundle destination must be the same; both use
  `sidecar/<name>` under resources.

## R4 — Freezing `loopplane` (dynamic imports)

- **Decision**: the PyInstaller spec uses `collect_submodules("loopplane")` for
  `hiddenimports`, so lazily/dynamically imported subpackages (adapters, plugins, etc.) are
  bundled even though `bridge.py` imports only `loopplane.host`/`loopplane.events`/
  `loopplane.model` statically.
- **Rationale**: PyInstaller follows static imports; `collect_submodules` covers the rest so
  the frozen sidecar does not fail at runtime on a missing submodule.

## R5 — The `.spec` stays out of the Python gate

- **Decision**: the PyInstaller spec is `loopplane-sidecar.spec` (a `.spec`, not a `.py`).
- **Rationale**: ruff/mypy/pytest target `.py`; a `.spec` is invisible to them, so the spec
  (which uses PyInstaller's injected `Analysis`/`PYZ`/`EXE` globals) is neither linted,
  type-checked, nor collected — no false failures.

## R6 — Declare electron-builder without bloating the default gate

- **Decision**: add `electron-builder` to `devDependencies` (pinned), but the default gate
  (`tsc --noEmit` + `vitest run`) does **not** import or invoke it, so it need not be
  installed to pass the gate; only the reserved build (`npm run dist`) needs it.
- **Rationale**: honest version pinning for the reserved build, without making the gate
  depend on installing a large packager.

## R7 — Fail clearly on a missing frozen sidecar

- **Decision**: in packaged mode the resolver **throws** a clear error when the frozen
  executable is absent (an injectable `exists` predicate makes this testable); `main.ts`
  catches it and surfaces an error (an error box) and quits, rather than spawning a missing
  path and hanging.
- **Rationale**: FR-008 — a corrupt/incomplete install must fail visibly, not silently hang.

## R8 — Reserved-build boundary

- **Decision**: the default gate proves the resolver + the config↔spec consistency offline;
  the actual PyInstaller freeze, the electron-builder installer, and signing/notarization
  are a **reserved manual / CI step**, documented in `docs/desktop-gui.md`.
- **Rationale**: a per-OS frozen build + signed installer cannot be produced/verified in the
  default environment; unit 019 set the same precedent (manual GUI smoke, reserved signing).

## R9 — Desktop-only, reversible

- **Decision**: only `apps/desktop/` (+ `.gitignore`/docs) changes; the runtime, hosts, web
  UI, CLI, and the unit-019 bridge/transport/preload are untouched. Rollback = delete the
  resolver/spec/config and restore the dev-only `spawn("python", [bridge.py])`.
