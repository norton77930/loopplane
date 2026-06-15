// The Electron preload: expose a minimal, line-oriented bridge to the renderer as
// window.api (feature 019). The renderer's SidecarTransport speaks this.

import { contextBridge, type IpcRendererEvent, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("api", {
  send: (line: string) => ipcRenderer.send("sidecar:send", line),
  onLine: (handler: (line: string) => void) => {
    const listener = (_event: IpcRendererEvent, line: string) => handler(line);
    ipcRenderer.on("sidecar:line", listener);
    return () => ipcRenderer.removeListener("sidecar:line", listener);
  },
});
