// Electron main: secure window + SidecarRpcClient supervisor + typed IPC (078 T027–T032).

import { spawn, type ChildProcessByStdio } from "node:child_process";
import { join } from "node:path";
import type { Readable, Writable } from "node:stream";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  safeStorage,
  session,
  shell,
} from "electron";

import { registerDesktopIpcHandlers } from "./ipc-handlers";
import {
  McpMaterialSyncCoordinator,
  McpOAuthController,
  mcpNotificationMayRefresh,
} from "./mcp-oauth-controller";
import { runAuthorization } from "./mcp-oauth-flow";
import {
  clearProviderConfig,
  nodeCredentialFileIo,
  providerSpawnEnv,
  publicProviderView,
  readProviderConfig,
  writeProviderConfig,
  type VaultDeps,
} from "./provider-credentials";
import { SidecarRpcClient } from "./sidecar-rpc";
import { resolveSidecar, type SidecarSpawn } from "./sidecar-spawn";
import {
  installDenyByDefaultPermissions,
  installNavigationGuards,
} from "./window-security";

type SidecarChildProcess = ChildProcessByStdio<Writable, Readable, null>;

type WindowRuntime = {
  window: BrowserWindow | null;
  child: SidecarChildProcess;
  rpc: SidecarRpcClient;
  disposeHandlers: (() => void) | null;
  started: boolean;
  shuttingDown: boolean;
  shutdownPromise: Promise<void> | null;
  flushBeforeShutdown: (() => Promise<void>) | null;
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
const SIDECAR_WARMUP_MS = 2_500;
const SIDECAR_INIT_TIMEOUT_MS = 7_000;

async function waitForSidecarWarmup(spawnedAt: number): Promise<void> {
  if (!app.isPackaged) return;
  const remaining = SIDECAR_WARMUP_MS - (Date.now() - spawnedAt);
  if (remaining <= 0) return;
  await new Promise<void>((resolve) => setTimeout(resolve, remaining));
}

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

const packagedSmokeRequested = process.argv.some((value) =>
  value.startsWith(PACKAGED_SMOKE_ARGUMENT),
);
if (app.isPackaged && packagedSmokeRequested) {
  app.commandLine.appendSwitch("enable-features", "UiaProvider");
}

let active: WindowRuntime | null = null;
let diagnosticWindow: BrowserWindow | null = null;

async function teardownRuntime(
  runtime: WindowRuntime,
  { force = false }: { force?: boolean } = {},
): Promise<void> {
  runtime.shutdownPromise ??= (async () => {
    runtime.disposeHandlers?.();
    runtime.disposeHandlers = null;
    if (!force) await runtime.flushBeforeShutdown?.();
    runtime.shuttingDown = true;
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
  })();
  await runtime.shutdownPromise;
}

/**
 * The credential vault's Electron-provided inputs. Built per call because
 * `app.getPath` is only meaningful once the app is ready.
 */
function vaultDeps(): VaultDeps {
  return {
    vault: safeStorage,
    io: nodeCredentialFileIo(),
    userDataDir: app.getPath("userData"),
  };
}

function createWindow(
  smoke: PackagedSmokeOptions | null,
  rendererReady: Promise<void> = Promise.resolve(),
): void {
  const entryPath = app.isPackaged
    ? join(app.getAppPath(), "dist", "index.html")
    : fileURLToPath(new URL("../dist/index.html", import.meta.url));
  const entryUrl = pathToFileURL(entryPath).href;
  let spawnedAt: number;
  let child: SidecarChildProcess;
  try {
    const spawnSpec: SidecarSpawn = resolveSidecar({
      packaged: app.isPackaged,
      platform: process.platform,
      resourcesPath: process.resourcesPath,
      devDir: fileURLToPath(new URL("../sidecar", import.meta.url)),
    });
    spawnedAt = Date.now();
    // spawn() throws synchronously on Windows when the bundled executable is
    // present but not loadable, so a corrupt sidecar has to reach the same
    // visible diagnostic instead of escaping as an unhandled main-process error.
    child = spawn(spawnSpec.command, spawnSpec.args, {
      stdio: ["pipe", "pipe", "inherit"],
      env: {
        ...process.env,
        // The in-app provider setting, decrypted here and handed to the sidecar
        // for this process only. A packaged smoke run stays on its scripted
        // model, so it never reads a real credential.
        ...(smoke ? {} : providerSpawnEnv(readProviderConfig(vaultDeps()))),
        LOOPPLANE_PROFILE_ROOT:
          smoke?.profileRoot ??
          (app.isPackaged
            ? join(app.getPath("userData"), "profile")
            : process.env.LOOPPLANE_PROFILE_ROOT ??
              join(app.getPath("userData"), "profile")),
        LOOPPLANE_PACKAGED_SMOKE_SCENARIO: smoke?.scenario,
      },
    });
  } catch {
    void rendererReady.then(() => {
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
              diagnostic:
                "The bundled sidecar could not be started. Reinstall LoopPlane.",
              recovery: "reinstall_application",
            },
          });
        });
        void window.loadFile(entryPath);
        return;
      }
      dialog.showErrorBox(
        "LoopPlane",
        "The bundled sidecar executable is missing; the installation may be corrupt.",
      );
      app.quit();
    });
    return;
  }

  if (!child.stdin || !child.stdout) {
    void rendererReady.then(() => {
      dialog.showErrorBox("LoopPlane", "Failed to open sidecar stdio.");
      app.quit();
    });
    return;
  }

  const runtime: WindowRuntime = {
    window: null,
    child,
    rpc: null as unknown as SidecarRpcClient,
    disposeHandlers: null,
    started: false,
    shuttingDown: false,
    shutdownPromise: null,
    flushBeforeShutdown: null,
  };

  let mcpOAuth: McpOAuthController | null = null;
  let materialSync: McpMaterialSyncCoordinator | null = null;
  const syncMcpMaterial = (): void => {
    if (mcpOAuth === null || materialSync === null || runtime.shuttingDown) return;
    materialSync.trigger();
  };

  const rpc = new SidecarRpcClient({
    // A cold packaged start unpacks the frozen sidecar before it can answer
    // initialize; the default 5s deadline plus the warmup expires first and
    // reports a healthy runtime as unavailable. Failure scenarios never reach
    // this timer: missing/corrupt fail at spawn and incompatible answers at once.
    initTimeoutMs: SIDECAR_INIT_TIMEOUT_MS,
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
      if (runtime.shuttingDown) return;
      if (mcpNotificationMayRefresh(method, params)) syncMcpMaterial();
      const window = runtime.window;
      if (!window || window.isDestroyed()) return;
      // Never start new durable work during shutdown; route only exact V1 methods.
      if (
        method === "runtime.event" ||
        method === "runtime.outcome" ||
        method === "runtime.subscriptionClosed"
      ) {
        window.webContents.send("lp:interaction:event", { method, params });
        return;
      }
      if (method === "runtime.state") {
        window.webContents.send("lp:app:statusEvent", { method, params });
      }
    },
    onStateChange: (state) => {
      const window = runtime.window;
      if (
        state === "failed" &&
        !runtime.shuttingDown &&
        window &&
        !window.isDestroyed()
      ) {
        window.webContents.send("lp:app:statusEvent", {
          method: "runtime.state",
          params: { state: "failed", recovery: "restart_runtime" },
        });
      }
    },
  });
  runtime.rpc = rpc;
  mcpOAuth = new McpOAuthController({
    rpc,
    vault: vaultDeps(),
    authorize: (begin) =>
      runAuthorization(
        {
          openExternal: async (url) => {
            await shell.openExternal(url);
          },
        },
        begin,
      ),
  });
  materialSync = new McpMaterialSyncCoordinator(() => mcpOAuth!.syncAll());
  runtime.flushBeforeShutdown = () => materialSync!.flush();
  active = runtime;

  const openRendererWindow = (): BrowserWindow => {
    if (runtime.window && !runtime.window.isDestroyed()) return runtime.window;

    const window = new BrowserWindow({
      width: 1000,
      height: 700,
      show: false,
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        preload: fileURLToPath(new URL("./preload.cjs", import.meta.url)),
        sandbox: true,
      },
    });
    runtime.window = window;

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

    const bindHandlers = (): (() => void) =>
      registerDesktopIpcHandlers({
        ipcMain,
        rpc,
        expectedSenderId: window.webContents.id,
        expectedSenderUrl: entryUrl,
        status: async () => ({ ready: rpc.connectionState === "ready" }),
        onShutdown: async () => {
          await teardownRuntime(runtime);
          app.quit();
        },
        chooseDirectory,
        chooseBackupDestination,
        chooseRestoreSource,
        providerVault: {
          get: () => publicProviderView(readProviderConfig(vaultDeps())),
          save: (input) => writeProviderConfig(vaultDeps(), input),
          clear: () => {
            clearProviderConfig(vaultDeps());
          },
          relaunch: () => {
            app.relaunch();
            app.quit();
          },
        },
        mcpOAuth,
      });

    runtime.disposeHandlers = bindHandlers();

    // Renderer reload: keep initial handlers available through the first load,
    // then drop registrations for an old frame and re-bind after later loads.
    let rendererLoaded = false;
    window.webContents.on("did-start-navigation", () => {
      if (!rendererLoaded) return;
      // Local bindings only — no new durable sidecar work during reload.
      runtime.disposeHandlers?.();
      runtime.disposeHandlers = null;
    });
    window.webContents.on("did-finish-load", () => {
      if (runtime.shuttingDown || window.isDestroyed()) return;
      if (rendererLoaded) {
        runtime.disposeHandlers = bindHandlers();
      } else {
        rendererLoaded = true;
      }
      if (rpc.connectionState === "ready") {
        window.webContents.send("lp:app:statusEvent", {
          method: "runtime.state",
          params: { state: "ready" },
        });
      }
    });

    window.on("closed", () => {
      if (runtime.window === window) runtime.window = null;
      void (async () => {
        await teardownRuntime(runtime);
        if (active === runtime) active = null;
        app.quit();
      })();
    });

    return window;
  };

  // Overlap the sidecar handshake with Electron/renderer startup: one packaged
  // smoke deadline covers window + accessible locators + a usable runtime, and a
  // handshake serialized after the renderer load spends that budget twice.
  const sidecarStart = (async () => {
    await waitForSidecarWarmup(spawnedAt);
    await rpc.start();
    // Restoration is intentionally background work: an unreachable remote MCP
    // server must not hold the Desktop window behind the adapter's human-sized
    // interactive authorization budget.
    void mcpOAuth?.restoreAll().catch(() => {});
  })();
  // Keep the rejection handled until the join below re-raises it in context.
  sidecarStart.catch(() => {});

  void (async () => {
    try {
      await rendererReady;
      const window = openRendererWindow();
      const rendererLoad = window.loadFile(entryPath);
      await rendererLoad;
      window.show();
      await sidecarStart;
      if (runtime.shuttingDown) return;
      runtime.started = true;
      window.webContents.send("lp:app:statusEvent", {
        method: "runtime.state",
        params: { state: "ready" },
      });
    } catch (error) {
      if (runtime.shuttingDown) return;
      const diagnostic =
        error instanceof Error &&
        "public" in error &&
        (error as { public?: { category?: string } }).public?.category ===
          "incompatible_protocol"
          ? "The local runtime is incompatible."
          : "The local runtime is unavailable.";
      if (smoke) {
        const window = openRendererWindow();
        const sendFailed = (): void => {
          if (window.isDestroyed()) return;
          window.webContents.send("lp:app:statusEvent", {
            method: "runtime.state",
            params: {
              state: "failed",
              diagnostic,
              recovery: "restart_runtime",
            },
          });
        };
        // Reloading a renderer that already mounted drops its status
        // subscription, so this one-shot diagnostic would be delivered to a
        // frame that no longer exists. Only load a window that never started.
        if (window.webContents.getURL()) {
          sendFailed();
        } else {
          window.webContents.once("did-finish-load", sendFailed);
          await window.loadFile(entryPath);
        }
        window.show();
        return;
      }
      dialog.showErrorBox("LoopPlane", diagnostic);
      await teardownRuntime(runtime, { force: true });
      app.quit();
    }
  })();
}

let smoke: PackagedSmokeOptions | null = null;
let smokeInvalid = false;
try {
  smoke = packagedSmokeOptions();
} catch {
  smokeInvalid = true;
}

const rendererReady = app.whenReady().then(() => {
  if (smokeInvalid) {
    dialog.showErrorBox("LoopPlane", "Packaged smoke configuration is invalid.");
    app.quit();
    return;
  }
  if (smoke) {
    app.setAccessibilitySupportEnabled(true);
  }
});

if (!smokeInvalid) {
  if (smoke) {
    createWindow(smoke, rendererReady);
  } else {
    void rendererReady.then(() => createWindow(null));
  }
}

app.on("window-all-closed", () => {
  if (!active) app.quit();
});

// Last-chance: no orphan sidecar after app quit.
app.on("before-quit", (event) => {
  if (!active) return;
  event.preventDefault();
  const runtime = active;
  void (async () => {
    await teardownRuntime(runtime);
    if (active === runtime) active = null;
    app.quit();
  })();
});
