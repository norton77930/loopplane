# Desktop GUI

The desktop app (unit 019) is a local Electron application under `apps/desktop/` that
runs the agent with **no server**: it spawns a **Python sidecar** that drives a
`loopplane.host` and streams normalized events over stdio (NDJSON), and **reuses the
unit-018 web UI** as its renderer. The result is a native-feeling desktop window for
chatting with the agent — entirely on the user's machine, no port opened.

## The gates (automated)

```sh
# The Python sidecar bridge — in the repository pytest gate:
uv run pytest tests/integration/test_desktop_sidecar.py

# The TS transport + the reused-018 renderer — in apps/desktop:
cd apps/desktop
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm install
npm run typecheck                 # tsc --noEmit (incl. the Electron main/preload)
npm test                          # vitest run
```

## Launch (manual GUI smoke)

```sh
cd apps/desktop
npm run dev                       # builds the renderer and launches Electron
```

`electron/main.ts` spawns `apps/desktop/sidecar/bridge.py` (a local `loopplane.host`),
opens a window with the reused 018 UI, and bridges the sidecar's stdio to the renderer
over IPC (`window.api`). Closing the window stops the sidecar — no orphan process.

## Shape

- `sidecar/bridge.py` — the stdio NDJSON bridge over `loopplane.host` (reuses
  `serialize_event`); `collect_events(host, prompt)` is the testable core.
- `src/sidecar.ts` — the `SidecarTransport` (mirrors 018's client over `window.api`).
- `src/App.tsx` — the unit-018 view model (`reduce` + `Conversation`/`Timeline`/`Prompts`
  via the `@web` alias) over the sidecar transport — no UI is copied.
- `electron/{main,preload}.ts` — spawn the sidecar and bridge stdio ↔ IPC
  (typechecked; the GUI is verified by a manual smoke).

The app opens no network port, runs no tool itself (the host does), and embeds no
secret. The Python package and units 011/012/018 are unchanged.

## Packaging (unit 024)

To ship the app to a user with **no Python**, the sidecar is **frozen** and bundled:

- `sidecar/loopplane-sidecar.spec` — a **PyInstaller** spec freezing `bridge.py` +
  `loopplane` into a standalone `loopplane-sidecar` executable (no system Python).
- `electron-builder.yml` — bundles the Electron app + the renderer build + the frozen
  sidecar (as `extraResources` → `resources/sidecar/`) into an installer.
- `electron/sidecar-spawn.ts` — `resolveSidecar(...)` chooses what `main.ts` spawns: the
  **bundled frozen executable** in a packaged app, else **`python sidecar/bridge.py`** in
  development (unchanged). A missing bundled sidecar fails visibly, not silently.

The default gate proves the resolver and the spec↔config name consistency **offline** (a
Vitest unit test + a consistency check). Producing and signing the actual per-OS installer
is a **reserved manual / CI step**:

```sh
cd apps/desktop
pip install pyinstaller
npm run build:sidecar          # pyinstaller -> sidecar/dist/loopplane-sidecar*
npx vite build                 # renderer -> dist/  (also compile electron/*.ts -> *.js)
npm install electron-builder
npm run dist                   # electron-builder -> apps/desktop/release/<installer>
# then sign / notarize per platform (reserved)
```

The frozen sidecar (`sidecar/dist`), the renderer `dist/`, and `release/` are gitignored.
