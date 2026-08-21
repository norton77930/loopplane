import { describe, expect, it } from "vitest";

import {
  createBrowserWindowDouble,
  createChildProcessDouble,
  createIpcSenderFrom,
  createNativeDialogDouble,
  createWebContentsDouble,
} from "../../electron/__tests__/helpers";

describe("T012 electron helpers", () => {
  it("tracks webContents send and sender doubles", () => {
    const wc = createWebContentsDouble({ id: 3 });
    wc.send("app:status", { ok: true });
    expect(wc.sent).toHaveLength(1);
    const sender = createIpcSenderFrom(wc);
    expect(sender.id).toBe(3);
    expect(sender.isDestroyed()).toBe(false);
  });

  it("child process records writes and exit", () => {
    const child = createChildProcessDouble(99);
    child.stdin.write("hello\n");
    expect(child.written[0]).toContain("hello");
    let exited = false;
    child.on("exit", () => {
      exited = true;
    });
    child.emitExit(0);
    expect(exited).toBe(true);
  });

  it("native dialog open can cancel", async () => {
    const dlg = createNativeDialogDouble();
    dlg.nextOpen = { canceled: true, filePaths: [] };
    const r = await dlg.showOpenDialog({ title: "pick" });
    expect(r.canceled).toBe(true);
    expect(dlg.lastOpenOptions).toEqual({ title: "pick" });
  });

  it("browser window loadFile records path", async () => {
    const win = createBrowserWindowDouble();
    await win.loadFile("dist/index.html");
    expect(win.loaded).toContain("dist/index.html");
  });
});
