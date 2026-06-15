// The Electron main process: spawn the Python sidecar, open the window, and bridge
// the sidecar's stdio to the renderer over IPC (feature 019). Typechecked here; the
// GUI launch is a manual smoke (the JS gate skips the Electron binary, and packaging
// a distributable installer is a reserved, maintainer-initiated step).

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { app, BrowserWindow, ipcMain } from "electron";

const sidecarScript = fileURLToPath(new URL("../sidecar/bridge.py", import.meta.url));

function createWindow(): void {
  const sidecar = spawn("python", [sidecarScript], {
    stdio: ["pipe", "pipe", "inherit"],
  });

  const window = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      preload: fileURLToPath(new URL("./preload.cjs", import.meta.url)),
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
