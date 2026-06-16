// The sidecar launch resolver (unit 024): which executable the Electron main process
// spawns. In a packaged app it is the bundled, PyInstaller-frozen `loopplane-sidecar`
// (no system Python); in development it falls back to `python sidecar/bridge.py` — the
// unchanged unit-019 behavior. Pure: it imports no `electron`, so it is unit-testable;
// `main.ts` supplies the Electron-provided inputs (app.isPackaged / process.platform /
// process.resourcesPath).

import { existsSync } from "node:fs";
import path from "node:path";

export interface SidecarSpawn {
  command: string;
  args: string[];
}

export interface ResolveOptions {
  packaged: boolean;
  platform: NodeJS.Platform;
  resourcesPath: string;
  devDir: string;
  exists?: (target: string) => boolean;
}

const SIDECAR_BASENAME = "loopplane-sidecar";

/** The frozen sidecar's file name for a target platform (a `.exe` on Windows). */
export function frozenSidecarName(platform: NodeJS.Platform): string {
  return platform === "win32" ? `${SIDECAR_BASENAME}.exe` : SIDECAR_BASENAME;
}

/**
 * Resolve the sidecar command/args for the current app. Joins paths with the target
 * platform's separators (so the result is deterministic regardless of the host).
 */
export function resolveSidecar(options: ResolveOptions): SidecarSpawn {
  const p = options.platform === "win32" ? path.win32 : path.posix;
  if (options.packaged) {
    const exists = options.exists ?? existsSync;
    const executable = p.join(
      options.resourcesPath,
      "sidecar",
      frozenSidecarName(options.platform),
    );
    if (!exists(executable)) {
      throw new Error("the bundled LoopPlane sidecar executable is missing");
    }
    return { command: executable, args: [] };
  }
  // Development: spawn system Python with the bridge script (unit-019 behavior).
  return { command: "python", args: [p.join(options.devDir, "bridge.py")] };
}
