# Contract: Desktop packaging pipeline

How the desktop app ships Python and what the default gate proves vs. what is reserved.

## Spawn resolver obligations

1. **Packaged → frozen (FR-004)**: in a packaged app, `resolveSidecar` returns the
   **bundled frozen sidecar** at `join(resourcesPath, "sidecar", <name>)` with empty args.
2. **Development → system Python (FR-005)**: otherwise it returns `python` +
   `join(devDir, "bridge.py")` — the unchanged unit-019 behavior.
3. **Per-platform name (FR-006)**: the frozen name is `loopplane-sidecar`, plus a `.exe`
   suffix on Windows.
4. **Missing → fail clearly (FR-008)**: in a packaged app, a missing frozen executable
   makes the resolver **throw** a clear, public-safe error (no silent hang); `main.ts`
   surfaces it and quits.
5. **Pure / testable (FR-006)**: the resolver imports no `electron`, so it is unit-tested
   directly; `main.ts` supplies the Electron-provided inputs.

## Freeze ↔ package consistency (FR-007)

- The PyInstaller spec produces `sidecar/dist/loopplane-sidecar*`; the electron-builder
  `extraResources` bundles `sidecar/dist/loopplane-sidecar*` to `resources/sidecar/`, which
  is exactly where the resolver looks. A test reads both files and asserts the shared
  `loopplane-sidecar` name, so the freeze and the package cannot drift.

## What the default gate proves vs. reserved (FR-011)

| Proven offline (default gate) | Reserved (manual / CI) |
|---|---|
| the resolver (packaged / dev / missing / per-platform) | the actual PyInstaller freeze |
| the config↔spec name consistency | the electron-builder installer artifact |
| `tsc --noEmit` + `vitest run` green; Python suite unchanged | signing / notarization; cross-OS build matrix |

## Boundaries (FR-009, FR-010)

- **Desktop-only**: no change to the runtime, hosts, web UI, CLI, or the unit-019
  bridge / transport / preload; the renderer still reuses unit 018.
- **No committed artifacts**: the frozen sidecar, the installer, and the renderer build
  output are gitignored; no secret is committed.
- **Distribution is per-surface**: the CLI (pip), the web frontend (static assets + a
  server-side Python host), and the desktop app (this frozen installer) ship differently
  and independently; this unit touches only the desktop path.

## Rollback (Constitution X)

Delete `electron/sidecar-spawn.ts`, the `.spec`, and `electron-builder.yml`, revert
`main.ts` to `spawn("python", [bridge.py])`, and drop the package.json/`.gitignore`
additions. The app, its tests, and the runtime are untouched.
