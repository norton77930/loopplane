// The Electron main process: spawn the Python sidecar, open the window, and bridge
// the sidecar's stdio to the renderer over IPC (feature 019). Typechecked here; the
// GUI launch is a manual smoke (the JS gate skips the Electron binary, and packaging
// a distributable installer is a reserved, maintainer-initiated step).

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { app, BrowserWindow, dialog, ipcMain } from "electron";

import { resolveSidecar, type SidecarSpawn } from "./sidecar-spawn";

function createWindow(): void {
  let spawnSpec: SidecarSpawn;
  try {
    // Packaged: the bundled frozen sidecar; development: `python sidecar/bridge.py`.
    spawnSpec = resolveSidecar({
      packaged: app.isPackaged,
      platform: process.platform,
      resourcesPath: process.resourcesPath,
      devDir: fileURLToPath(new URL("../sidecar", import.meta.url)),
    });
  } catch {
    // A missing bundled sidecar must fail visibly, not hang (FR-008).
    dialog.showErrorBox(
      "LoopPlane",
      "The bundled sidecar executable is missing; the installation may be corrupt.",
    );
    app.quit();
    return;
  }
  const sidecar = spawn(spawnSpec.command, spawnSpec.args, {
    stdio: ["pipe", "pipe", "inherit"],
  });

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

  // Forward each complete NDJSON line from the sidecar to the renderer.
  let buffer = "";
  sidecar.stdout?.on("data", (chunk: Buffer) => {
    buffer += chunk.toString();
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      window.webContents.send("sidecar:line", buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
    }
  });

  ipcMain.on("sidecar:send", (_event, line: string) => {
    sidecar.stdin?.write(`${line}\n`);
  });

  // Closing the window stops the sidecar — no orphan process (FR-008).
  window.on("closed", () => {
    sidecar.kill();
  });

  void window.loadFile(fileURLToPath(new URL("../dist/index.html", import.meta.url)));
}

void app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  app.quit();
});
