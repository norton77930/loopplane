# Data Model: Desktop Packaging (unit 024)

Component shapes for the packaging pipeline. Illustrative; the authority is the spec.

## Sidecar spawn resolver — `apps/desktop/electron/sidecar-spawn.ts`

```ts
export interface SidecarSpawn {
  command: string;
  args: string[];
}

export interface ResolveOptions {
  packaged: boolean;            // app.isPackaged
  platform: NodeJS.Platform;    // process.platform
  resourcesPath: string;        // process.resourcesPath (packaged app)
  devDir: string;               // the sidecar/ dir (holds bridge.py) in development
  exists?: (path: string) => boolean;   // defaults to fs.existsSync (injectable for tests)
}

export function frozenSidecarName(platform: NodeJS.Platform): string;  // "loopplane-sidecar" (+ ".exe" on win32)
export function resolveSidecar(options: ResolveOptions): SidecarSpawn;
```

- **packaged** → `command = join(resourcesPath, "sidecar", frozenSidecarName(platform))`,
  `args = []`; **throws** a clear error if `!exists(command)`.
- **development** → `command = "python"`, `args = [join(devDir, "bridge.py")]` (the
  unchanged unit-019 behavior).

## `main.ts` change — `apps/desktop/electron/main.ts`

Replaces the hardcoded `spawn("python", [bridge.py])` with:

```ts
const { command, args } = resolveSidecar({
  packaged: app.isPackaged,
  platform: process.platform,
  resourcesPath: process.resourcesPath,
  devDir: fileURLToPath(new URL("../sidecar", import.meta.url)),
});
const sidecar = spawn(command, args, { stdio: ["pipe", "pipe", "inherit"] });
```

A `try/catch` around the resolve surfaces a missing-frozen-sidecar error (an error box) and
quits, rather than hanging.

## Freeze specification — `apps/desktop/sidecar/loopplane-sidecar.spec`

A PyInstaller spec: `Analysis(["bridge.py"], hiddenimports=collect_submodules("loopplane"))`
→ `EXE(name="loopplane-sidecar", console=True)`. Output: `sidecar/dist/loopplane-sidecar`
(+ `.exe` on Windows).

## Packaging configuration — `apps/desktop/electron-builder.yml`

| Field | Value |
|---|---|
| `appId` / `productName` | `dev.loopplane.desktop` / `LoopPlane` |
| `directories.output` | `release` (gitignored) |
| `files` | the compiled Electron main/preload + the renderer `dist/**` |
| `extraResources` | `from: sidecar/dist`, `to: sidecar`, filter `loopplane-sidecar*` |
| `win` / `mac` / `linux` | `nsis` / `dmg` / `AppImage` targets |

## package.json — `apps/desktop/package.json`

- `devDependencies` += `electron-builder` (pinned; reserved-build only).
- `scripts` += `build:sidecar` (PyInstaller) and `dist` (electron-builder); the full per-OS
  build is the reserved/documented procedure.

## Reused unchanged (unit 019)

`sidecar/bridge.py`, `src/sidecar.ts` (`SidecarTransport`), `electron/preload.ts`, the
renderer (`@web` alias → unit-018 UI), and their tests.
