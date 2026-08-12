/**
 * T019/T028: BrowserWindow security + IPC composition static/unit checks.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  createChildProcessDouble,
  createIpcSenderFrom,
  createWebContentsDouble,
  TRUSTED_HANDLER_OPTIONS,
} from "../../electron/__tests__/helpers";
import { IPC } from "../../electron/ipc-channels";
import { registerDesktopIpcHandlers } from "../../electron/ipc-handlers";
import { SidecarRpcClient } from "../../electron/sidecar-rpc";
import type { IpcEventLike } from "../../electron/window-security";
import {
  BUNDLED_RENDERER_CSP,
  installDenyByDefaultPermissions,
  installNavigationGuards,
  isTrustedRendererUrl,
} from "../../electron/window-security";

const desktopRoot = fileURLToPath(new URL("../..", import.meta.url));

describe("bundled CSP and main composition", () => {
  it("index.html ships restrictive CSP without remote script/connect", () => {
    const html = readFileSync(`${desktopRoot}/index.html`, "utf8");
    expect(html).toMatch(/Content-Security-Policy/i);
    expect(html).toContain("default-src 'self'");
    expect(html).toContain("script-src 'self'");
    expect(html).toContain("connect-src 'none'");
    expect(html).toContain("object-src 'none'");
    expect(html).toContain("base-uri 'none'");
    expect(html).toContain("frame-ancestors 'none'");
    expect(html).toContain("form-action 'none'");
    expect(html).not.toMatch(/script-src[^;]*https?:/);
    expect(html).not.toMatch(/connect-src[^;]*https?:/);
  });

  it("BUNDLED_RENDERER_CSP constant matches contract minimums", () => {
    expect(BUNDLED_RENDERER_CSP).toContain("default-src 'self'");
    expect(BUNDLED_RENDERER_CSP).toContain("connect-src 'none'");
  });

  it("main.ts preserves isolation flags and packaged load path", () => {
    const main = readFileSync(`${desktopRoot}/electron/main.ts`, "utf8");
    expect(main).toContain("contextIsolation: true");
    expect(main).toContain("sandbox: true");
    expect(main).toContain("nodeIntegration: false");
    expect(main).toContain("dist/index.html");
    expect(main).toContain("installNavigationGuards");
    expect(main).toContain("installDenyByDefaultPermissions");
    expect(main).not.toContain("function createDiagnosticWindow");
    expect(main).toContain("registerDesktopIpcHandlers");
    expect(main).toContain("SidecarRpcClient");
    expect(main).toContain("pathToFileURL(entryPath).href");
    // Raw line tunnel must not remain as the privileged path.
    expect(main).not.toContain("sidecar:send");
    expect(main).not.toContain("sidecar:line");
  });
});

describe("navigation and permission guards", () => {
  it("denies unexpected will-navigate and all window.open", () => {
    const prevented: string[] = [];
    let openHandler: ((d: { url: string }) => { action: string }) | null = null;
    const willNav: Array<
      (event: { preventDefault: () => void }, url: string) => void
    > = [];
    const wc = {
      getURL: () => "file:///app/dist/index.html",
      onWillNavigate(listener: (event: { preventDefault: () => void }, url: string) => void) {
        willNav.push(listener);
      },
      setWindowOpenHandler(handler: (d: { url: string }) => { action: string }) {
        openHandler = handler;
      },
    };
    installNavigationGuards(
      { webContents: wc },
      { entryUrl: "file:///app/dist/index.html" },
    );
    expect(willNav).toHaveLength(1);
    willNav[0]!({ preventDefault: () => prevented.push("x") }, "https://evil.example");
    expect(prevented).toEqual(["x"]);
    expect(openHandler!({ url: "https://evil.example" })).toEqual({ action: "deny" });
  });

  it("permission handlers deny by default", () => {
    let requestHandler:
      | ((wc: unknown, p: string, cb: (allow: boolean) => void) => void)
      | null = null;
    let checkHandler: (() => boolean) | null = null;
    installDenyByDefaultPermissions({
      setPermissionRequestHandler(h) {
        requestHandler = h;
      },
      setPermissionCheckHandler(h) {
        checkHandler = h as () => boolean;
      },
    });
    let allowed = true;
    requestHandler!(null, "notifications", (v) => {
      allowed = v;
    });
    expect(allowed).toBe(false);
    expect(checkHandler!()).toBe(false);
  });

  it("trusts only local renderer URLs", () => {
    expect(isTrustedRendererUrl("file:///app/dist/index.html")).toBe(true);
    expect(isTrustedRendererUrl("https://evil.example")).toBe(false);
    expect(isTrustedRendererUrl("http://localhost:5173/")).toBe(true);
  });
});

describe("typed IPC handlers", () => {
  it("rejects untrusted senders and maps createInteractive without renderer mutation ids", async () => {
    const handlers = new Map<
      string,
      (event: IpcEventLike, ...args: unknown[]) => unknown | Promise<unknown>
    >();
    const ipcMain = {
      handle(channel: string, listener: (event: IpcEventLike, ...args: unknown[]) => unknown | Promise<unknown>) {
        handlers.set(channel, listener);
      },
      removeHandler(channel: string) {
        handlers.delete(channel);
      },
    };

    const child = createChildProcessDouble();
    const rpc = new SidecarRpcClient({ child });
    const startP = rpc.start();
    await Promise.resolve();
    const initWrite = child.written[0]!;
    const initReq = JSON.parse(initWrite.trim()) as { id: string };
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: initReq.id,
        result: {
          protocol: "loopplane.desktop.stdio",
          version: 1,
          methods: ["session.createInteractive"],
          capabilities: {},
        },
      }),
    );
    await startP;

    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });

    const evil = createWebContentsDouble({ url: "https://evil.example" });
    const evilSender = createIpcSenderFrom(evil);
    await expect(
      handlers.get(IPC.sessionCreateInteractive)!(evilSender, { paneId: "p" }),
    ).rejects.toThrow(/untrusted/i);

    const good = createWebContentsDouble({ url: "file:///app/dist/index.html" });
    const goodSender = createIpcSenderFrom(good);
    const createP = handlers.get(IPC.sessionCreateInteractive)!(goodSender, {
      paneId: "pane-1",
    });
    await Promise.resolve();
    const last = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { mutation_id: string; pane_id: string };
    };
    expect(last.method).toBe("session.createInteractive");
    expect(last.params.mutation_id).toMatch(/^mut-/);
    expect(last.params.pane_id).toBe("pane-1");
    // Renderer must not control mutation ids
    expect(JSON.stringify(last.params)).not.toContain("renderer-mut");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: last.id,
        result: { session_id: "s1", subscription_id: "sub1" },
      }),
    );
    await expect(createP).resolves.toEqual({
      session_id: "s1",
      subscription_id: "sub1",
    });
  });
});
