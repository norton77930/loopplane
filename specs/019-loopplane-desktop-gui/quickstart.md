# Quickstart: The Desktop App

The desktop app lives under `apps/desktop/` with its own toolchain, reusing the
unit-018 UI and driving a local `loopplane.host` over a stdio bridge — no server.

## The gates (automated)

```sh
# Python sidecar bridge — in the repository pytest gate:
uv run pytest tests/integration/test_desktop_sidecar.py

# TS transport + typecheck — in apps/desktop:
cd apps/desktop
npm install                       # ELECTRON_SKIP_BINARY_DOWNLOAD=1 keeps CI binary-free
npm run typecheck                 # tsc --noEmit
npm test                          # vitest run (the sidecar transport)
```

## Launch (manual GUI smoke)

```sh
cd apps/desktop
npm run dev                       # builds the renderer and launches Electron
```

Electron's `main.ts` spawns `apps/desktop/sidecar/bridge.py` (a local
`loopplane.host`), opens a window with the reused 018 UI, and pipes the stdio bridge to
the renderer. Closing the window stops the sidecar — no orphan process.

## Shape

- `sidecar/bridge.py` — the stdio NDJSON bridge over `loopplane.host` (reuses
  `serialize_event`); `collect_events(host, prompt)` is the testable core.
- `src/sidecar.ts` — the `SidecarTransport` (mirrors 018's client over `window.api`).
- `src/App.tsx` — the unit-018 view model (`reduce` + components) over the transport.
- `electron/{main,preload}.ts` — spawn the sidecar, bridge stdio ↔ IPC (typechecked;
  GUI verified by a manual smoke).

The app opens no network port, runs no tool itself, and embeds no secret. Packaging a
signed installer is a reserved, maintainer-initiated step.
