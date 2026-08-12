// Electron main: secure window + SidecarRpcClient supervisor + typed IPC (078 T027–T032).

import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable, Writable } from "node:stream";
import { fileURLToPath, pathToFileURL } from "node:url";

import { app, BrowserWindow, dialog, ipcMain, session } from "electron";

import { registerDesktopIpcHandlers } from "./ipc-handlers";
import { SidecarRpcClient } from "./sidecar-rpc";
import { resolveSidecar, type SidecarSpawn } from "./sidecar-spawn";
import {
  installDenyByDefaultPermissions,
  installNavigationGuards,
} from "./window-security";

type SidecarChildProcess = ChildProcessByStdio<Writable, Readable, null>;

type WindowRuntime = {
  window: BrowserWindow;
  child: SidecarChildProcess;
  rpc: SidecarRpcClient;
  disposeHandlers: (() => void) | null;
  started: boolean;
  shuttingDown: boolean;
};

type PackagedSmokeScenario =
  | "happy"
  | "missing-sidecar"
  | "corrupt-sidecar"
  | "incompatible-sidecar";

type PackagedSmokeOptions = {
  scenario: PackagedSmokeScenario;
  profileRoot: string;
};

const PACKAGED_SMOKE_ARGUMENT = "--loopplane-packaged-smoke=";
const PACKAGED_SMOKE_SCENARIOS = new Set<PackagedSmokeScenario>([
  "happy",
  "missing-sidecar",
  "corrupt-sidecar",
  "incompatible-sidecar",
]);

function packagedSmokeOptions(): PackagedSmokeOptions | null {
  const argument = process.argv.find((value) =>
    value.startsWith(PACKAGED_SMOKE_ARGUMENT),
  );
  if (!argument) return null;
  if (!app.isPackaged) {
    throw new Error("packaged_smoke_requires_packaged_app");
  }
  const scenario = argument.slice(PACKAGED_SMOKE_ARGUMENT.length);
  if (!PACKAGED_SMOKE_SCENARIOS.has(scenario as PackagedSmokeScenario)) {
    throw new Error("packaged_smoke_scenario_invalid");
  }
  const profileRoot = process.env.LOOPPLANE_PACKAGED_SMOKE_PROFILE;
  if (!profileRoot) {
    throw new Error("packaged_smoke_profile_required");
  }
  return {
    scenario: scenario as PackagedSmokeScenario,
    profileRoot,
  };
}

let active: WindowRuntime | null = null;
let diagnosticWindow: BrowserWindow | null = null;

async function teardownRuntime(
  runtime: WindowRuntime,
  { force = false }: { force?: boolean } = {},
): Promise<void> {
  if (runtime.shuttingDown) return;
  runtime.shuttingDown = true;
  runtime.disposeHandlers?.();
  runtime.disposeHandlers = null;
  try {
    if (runtime.started && !force) {
      await runtime.rpc.shutdown();
    } else {
      try {
        runtime.child.kill();
      } catch {
        /* ignore */
      }
    }
  } catch {
    try {
      runtime.child.kill();
    } catch {
      /* ignore */
    }
  }
}

function createWindow(smoke: PackagedSmokeOptions | null): void {
  const entryPath = fileURLToPath(new URL("../dist/index.html", import.meta.url));
  const entryUrl = pathToFileURL(entryPath).href;
  let spawnSpec: SidecarSpawn;
  try {
    spawnSpec = resolveSidecar({
      packaged: app.isPackaged,
      platform: process.platform,
      resourcesPath: process.resourcesPath,
      devDir: fileURLToPath(new URL("../sidecar", import.meta.url)),
    });
  } catch {
    if (smoke) {
      const window = new BrowserWindow({
        width: 1000,
        height: 700,
        webPreferences: {
          contextIsolation: true,
          nodeIntegration: false,
          preload: fileURLToPath(new URL("./preload.cjs", import.meta.url)),
          sandbox: true,
        },
      });
      diagnosticWindow = window;
      window.on("closed", () => {
        if (diagnosticWindow === window) diagnosticWindow = null;
      });
      installNavigationGuards(
        {
          webContents: {
            onWillNavigate(listener) {
              window.webContents.on("will-navigate", listener);
            },
            setWindowOpenHandler(handler) {
              window.webContents.setWindowOpenHandler(handler);
            },
            getURL() {
              return window.webContents.getURL();
            },
          },
        },
        { entryUrl },
      );
      installDenyByDefaultPermissions(session.defaultSession);
      window.webContents.once("did-finish-load", () => {
        if (window.isDestroyed()) return;
        window.webContents.send("lp:app:statusEvent", {
          method: "runtime.state",
          params: {
            state: "failed",
            diagnostic: "The bundled sidecar is missing. Reinstall LoopPlane.",
            recovery: "reinstall_application",
          },
        });
      });
      void window.loadFile(entryPath);
    } else {
      dialog.showErrorBox(
        "LoopPlane",
        "The bundled sidecar executable is missing; the installation may be corrupt.",
      );
      app.quit();
    }
    return;
  }

  const child = spawn(spawnSpec.command, spawnSpec.args, {
    stdio: ["pipe", "pipe", "inherit"],
    env: {
      ...process.env,
      LOOPPLANE_PROFILE_ROOT:
        smoke?.profileRoot ??
        process.env.LOOPPLANE_PROFILE_ROOT ??
        fileURLToPath(new URL("../.desktop-profile", import.meta.url)),
      LOOPPLANE_PACKAGED_SMOKE_SCENARIO: smoke?.scenario,
    },
  });

  if (!child.stdin || !child.stdout) {
    dialog.showErrorBox("LoopPlane", "Failed to open sidecar stdio.");
    app.quit();
    return;
  }

  const window = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: fileURLToPath(new URL("./preload.cjs", import.meta.url)),
      sandbox: true,
    },
  });

  const chooseDirectory = async (): Promise<string | null> => {
    const result = await dialog.showOpenDialog(window, {
      properties: ["openDirectory"],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0] ?? null;
  };

  const chooseBackupDestination = async (): Promise<string | null> => {
    const result = await dialog.showSaveDialog(window, {
      defaultPath: "loopplane-backup.zip",
      filters: [{ name: "LoopPlane backup", extensions: ["zip"] }],
    });
    if (result.canceled || !result.filePath) return null;
    return result.filePath;
  };

  const chooseRestoreSource = async (): Promise<string | null> => {
    const result = await dialog.showOpenDialog(window, {
      properties: ["openFile"],
      filters: [{ name: "LoopPlane backup", extensions: ["zip"] }],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0] ?? null;
  };

  installNavigationGuards(
    {
      webContents: {
        onWillNavigate(listener) {
          window.webContents.on("will-navigate", listener);
        },
        setWindowOpenHandler(handler) {
          window.webContents.setWindowOpenHandler(handler);
        },
        getURL() {
          return window.webContents.getURL();
        },
      },
    },
    { entryUrl },
  );
  installDenyByDefaultPermissions(session.defaultSession);

  const runtime: WindowRuntime = {
    window,
    child,
    rpc: null as unknown as SidecarRpcClient,
    disposeHandlers: null,
    started: false,
    shuttingDown: false,
  };

  const rpc = new SidecarRpcClient({
    child: {
      stdin: child.stdin,
      stdout: child.stdout,
      on: (event, cb) => {
        child.on(event, cb);
      },
      kill: (signal) => {
        child.kill(signal as NodeJS.Signals | undefined);
      },
      get killed() {
        return child.killed;
      },
    },
    onNotification: (method, params) => {
      if (window.isDestroyed() || runtime.shuttingDown) return;
      // Never start new durable work during shutdown.
      if (method.startsWith("runtime.")) {
        window.webContents.send("lp:interaction:event", { method, params });
      } else {
        window.webContents.send("lp:app:statusEvent", { method, params });
      }
    },
    onStateChange: (state) => {
      if (state === "failed" && !runtime.shuttingDown && !window.isDestroyed()) {
        window.webContents.send("lp:app:statusEvent", {
          method: "runtime.state",
          params: { state: "failed", recovery: "restart_runtime" },
        });
      }
    },
  });
  runtime.rpc = rpc;
  active = runtime;

  void (async () => {
    try {
      await rpc.start();
      if (runtime.shuttingDown) return;
      runtime.started = true;
      runtime.disposeHandlers = registerDesktopIpcHandlers({
        ipcMain,
        rpc,
        expectedSenderId: window.webContents.id,
        expectedSenderUrl: entryUrl,
        onShutdown: async () => {
          await teardownRuntime(runtime);
          app.quit();
        },
        chooseDirectory,
        chooseBackupDestination,
        chooseRestoreSource,
      });
    } catch (error) {
      const diagnostic =
        error instanceof Error &&
        "public" in error &&
        (error as { public?: { category?: string } }).public?.category ===
          "incompatible_protocol"
          ? "The local runtime is incompatible."
          : "The local runtime is unavailable.";
      if (smoke && !window.isDestroyed()) {
        window.webContents.once("did-finish-load", () => {
          if (window.isDestroyed()) return;
          window.webContents.send("lp:app:statusEvent", {
            method: "runtime.state",
            params: {
              state: "failed",
              diagnostic,
              recovery: "restart_runtime",
            },
          });
        });
        await window.loadFile(entryPath);
      } else if (!window.isDestroyed()) {
        dialog.showErrorBox("LoopPlane", diagnostic);
      }
      await teardownRuntime(runtime, { force: true });
      if (!smoke) app.quit();
    }
  })();

  // Renderer reload: drop IPC registrations for the old frame; re-bind after load.
  window.webContents.on("did-start-navigation", () => {
    // Local bindings only — no new durable sidecar work during reload.
    runtime.disposeHandlers?.();
    runtime.disposeHandlers = null;
  });
  window.webContents.on("did-finish-load", () => {
    if (runtime.shuttingDown || !runtime.started || window.isDestroyed()) return;
    if (rpc.connectionState !== "ready") return;
    runtime.disposeHandlers = registerDesktopIpcHandlers({
      ipcMain,
      rpc,
      expectedSenderId: window.webContents.id,
      expectedSenderUrl: entryUrl,
      onShutdown: async () => {
        await teardownRuntime(runtime);
        app.quit();
      },
      chooseDirectory,
      chooseBackupDestination,
      chooseRestoreSource,
    });
  });

  window.on("closed", () => {
    void teardownRuntime(runtime);
    if (active === runtime) active = null;
  });

  void window.loadFile(entryPath);
}

void app.whenReady().then(() => {
  let smoke: PackagedSmokeOptions | null;
  try {
    smoke = packagedSmokeOptions();
  } catch {
    dialog.showErrorBox("LoopPlane", "Packaged smoke configuration is invalid.");
    app.quit();
    return;
  }
  if (smoke) {
    app.setAccessibilitySupportEnabled(true);
  }
  createWindow(smoke);
});

app.on("window-all-closed", () => {
  app.quit();
});

// Last-chance: no orphan sidecar after app quit.
app.on("before-quit", (event) => {
  if (active && !active.shuttingDown) {
    event.preventDefault();
    void (async () => {
      await teardownRuntime(active!);
      active = null;
      app.quit();
    })();
  }
});
