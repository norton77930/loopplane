# Implementation Plan: Desktop Packaging

**Branch**: `024-desktop-packaging` (main-only) | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/024-desktop-packaging/spec.md`

## Summary

Make the unit-019 Electron desktop app distributable. A **PyInstaller spec**
(`apps/desktop/sidecar/loopplane-sidecar.spec`) freezes `sidecar/bridge.py` + `loopplane`
into a standalone `loopplane-sidecar` executable (no system Python). An **electron-builder
config** (`apps/desktop/electron-builder.yml`) bundles the Electron app + the built
renderer (unit-018 UI) + that frozen executable (as `extraResources`) into an installer. A
new **pure resolver** (`apps/desktop/electron/sidecar-spawn.ts`) — importing **no**
`electron` so it is unit-testable — chooses what `main.ts` spawns: in a packaged app the
bundled `loopplane-sidecar` (per-platform name; **throws if missing**), and in development
`python sidecar/bridge.py` (the unchanged unit-019 behavior). `main.ts` calls the resolver.
A Vitest suite covers the resolver and asserts the **config↔spec consistency** (both name
`loopplane-sidecar`). Desktop-app only — the runtime, hosts, web UI, CLI, and the unit-019
bridge / transport / preload are unchanged. The actual frozen build + signed per-OS
installer stay a **reserved manual / CI step** (consistent with unit 019).

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (Electron app) + Python 3.12 (frozen
sidecar). The freeze tool is **PyInstaller**; the packager is **electron-builder**.

**Primary Dependencies**: add **electron-builder** (devDependency, declared/pinned) — used
only by the reserved build, not by the default gate. PyInstaller is a build-time tool the
maintainer/CI installs; it is not a runtime dependency. No runtime (Python) dependency
changes.

**Storage**: N/A (packaging).

**Testing**: Vitest (node env) — a unit test of the spawn resolver (packaged → frozen exe;
dev → `python bridge.py`; missing frozen → throws; per-platform name) and a config↔spec
consistency test (reads `electron-builder.yml` + the `.spec`, asserts both name
`loopplane-sidecar`). The desktop gate stays `tsc --noEmit` + `vitest run`; the actual
freeze/installer build is **not** in the gate.

**Target Platform**: a packaged desktop application (Windows/macOS/Linux), built per-OS by
the maintainer/CI.

**Project Type**: desktop app — additive packaging config + a freeze spec + a spawn
resolver under `apps/desktop/`. The Python package is untouched.

**Performance Goals**: unchanged.

**Constraints**: desktop-only; no runtime/backend change; the spawn change is additive (a
dev fallback preserves unit-019 dev); the resolver imports no `electron` (testable); built
artifacts (frozen sidecar, installer, dist) are gitignored; the desktop gate stays green
and the Python suite is unchanged; producing/signing the installer is reserved manual/CI.

**Scale/Scope**: one new resolver module + its test, a PyInstaller spec, an
electron-builder config, a small `main.ts` edit, package.json scripts + devDep, `.gitignore`
entries, and a docs/changelog/board touch.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–012). | PASS |
| II — Greenfield | The resolver, spec, and config are written fresh; no legacy copied. | PASS |
| III — Harness before automation | Packaging only; no loop automation. | PASS |
| IV — Boundary Clarity | The app still reaches the runtime only through the sidecar bridge over `loopplane.host`; packaging adds no new coupling. | PASS |
| V — Tool Gateway Ownership | Untouched — the sidecar runs no tool itself. | PASS |
| VI — Event Bus Ownership | Untouched — the bridge is a normalized-stream consumer. | PASS |
| VII — Public-Safe | No secret/credential committed; built artifacts gitignored; the frozen exe carries only public-safe code. | PASS (FR-010) |
| VIII — No SDK Replacement | No framework swap; the runtime core is unchanged. | PASS |
| IX — Reference, not clone | Conventional Electron+PyInstaller packaging, derived for this app. | PASS |
| X — Testable Evolution | The resolver + consistency are unit-tested; rollback = drop the config/spec/resolver and restore the dev-only spawn. | PASS |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/024-desktop-packaging/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   └── packaging-pipeline.md        # the resolver contract + config↔spec consistency + reserved-build boundary
├── checklists/requirements.md
└── tasks.md                          # created by /speckit.tasks
```

### Source Code (repository root)

```text
apps/desktop/
├── electron/
│   ├── sidecar-spawn.ts    # NEW — pure resolver (no electron import): packaged frozen exe vs dev python+bridge; throws if frozen missing
│   └── main.ts             # EDIT — spawn via resolveSidecar(...); surface a clear error on a missing frozen sidecar
├── sidecar/
│   ├── bridge.py           # unchanged (the frozen entry point)
│   └── loopplane-sidecar.spec   # NEW — PyInstaller spec: freeze bridge.py + loopplane -> loopplane-sidecar
├── electron-builder.yml    # NEW — packaging config: bundle app + dist + sidecar/dist/loopplane-sidecar* (extraResources)
├── package.json            # EDIT — + electron-builder devDep; + build:sidecar / dist scripts
└── src/__tests__/
    └── sidecar-spawn.test.ts    # NEW — resolver (packaged/dev/missing/per-platform) + config↔spec consistency

.gitignore                  # EDIT — ignore apps/desktop/sidecar/{build,dist}/ and apps/desktop/release/
docs/desktop-gui.md         # EDIT — a Packaging section (freeze, build, what ships, reserved signing)
CHANGELOG.md                # EDIT — a 024 entry
docs/loopplane-agent-board.md  # EDIT — 024 row + audit; §4 → roadmap COMPLETE
```

**Structure Decision**: The sidecar-launch decision moves out of `main.ts` into a **pure**
`electron/sidecar-spawn.ts` (`resolveSidecar({ packaged, platform, resourcesPath, devDir,
exists? }) → { command, args }`) so it is unit-testable without the Electron runtime;
`main.ts` only supplies `app.isPackaged` / `process.platform` / `process.resourcesPath` and
spawns the result. The frozen executable is named `loopplane-sidecar` (+ `.exe` on
Windows); the PyInstaller spec produces it under `sidecar/dist/`, and electron-builder
`extraResources` bundles `sidecar/dist/loopplane-sidecar*` to `resources/sidecar/`, which is
exactly where the resolver looks in a packaged app (`join(process.resourcesPath, "sidecar",
name)`). A test reads both files and asserts the shared name, so the freeze and the package
cannot drift.

## Phases

- **Phase 0 — Research** (`research.md`): the pure resolver (no-electron) for testability;
  the frozen-exe name + per-platform suffix; the `extraResources` ↔ `resourcesPath` path
  agreement; PyInstaller `collect_submodules("loopplane")` for the lazy/dynamic imports; why
  the `.spec` stays out of ruff/mypy/pytest (a `.spec`, not `.py`); declaring
  electron-builder without bloating the default gate; the missing-binary fail-clear; and the
  reserved-build boundary (what the gate proves vs. the manual/CI smoke).
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the resolver
  signature + result; the freeze spec and packaging config shapes; the packaging-pipeline
  contract; and a build quickstart (freeze → package → run with no Python).
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — write the resolver + consistency tests first
  (FAIL), then the resolver, then `main.ts`, then the PyInstaller spec + electron-builder
  config + package.json + `.gitignore`, then docs/changelog/board; run the desktop gate +
  the Python suite.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
