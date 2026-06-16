# Quickstart: Desktop Packaging (unit 024)

Validates the packaging pipeline. The default gate is offline; the actual installer build
is a reserved manual / CI step.

## Default gate (offline, in `apps/desktop`)

```powershell
npm run typecheck   # tsc --noEmit (strict) over the renderer + electron + the resolver
npm test            # vitest run — incl. the resolver + config↔spec consistency tests
```

Also confirm the runtime is untouched (from repo root):

```powershell
uv run pytest       # unchanged
```

**Expected**: green; the resolver picks the frozen sidecar when packaged and `python
bridge.py` in development; the electron-builder config and the PyInstaller spec agree on
`loopplane-sidecar`.

## Development run (unchanged from unit 019)

```powershell
cd apps/desktop
npm run dev         # the renderer; the Electron shell spawns `python sidecar/bridge.py`
```

Requires a system Python with `loopplane` (the developer flow); unchanged by this unit.

## Reserved build — produce the installer (manual / CI, per OS)

```powershell
# 1. freeze the sidecar (no system Python needed at runtime afterwards)
cd apps/desktop
pip install pyinstaller
npm run build:sidecar          # pyinstaller sidecar/loopplane-sidecar.spec -> sidecar/dist/loopplane-sidecar*

# 2. build the renderer + electron entry, then package
npm run build                  # renderer dist + compiled electron main/preload
npm install electron-builder   # if not already installed
npm run dist                   # electron-builder -> apps/desktop/release/<installer>

# 3. (reserved) sign / notarize the installer per platform
```

**Expected**: an installer under `apps/desktop/release/` that installs a desktop app which
runs **with no system Python** (the frozen sidecar is bundled). Signing/notarization is a
reserved per-OS step. None of `sidecar/dist`, `release/`, or `dist/` is committed
(gitignored).
