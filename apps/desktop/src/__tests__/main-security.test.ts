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
  desktopInitializeResult,
  TRUSTED_HANDLER_OPTIONS,
} from "../../electron/__tests__/helpers";
import { IPC } from "../../electron/ipc-channels";
import {
  registerDesktopIpcHandlers,
  type ProviderVaultPort,
} from "../../electron/ipc-handlers";
import { SidecarRpcClient } from "../../electron/sidecar-rpc";
import type { IpcEventLike } from "../../electron/window-security";
import {
  BUNDLED_RENDERER_CSP,
  installDenyByDefaultPermissions,
  installNavigationGuards,
  isTrustedRendererUrl,
} from "../../electron/window-security";

const FAKE_KEY = "sk-sample-value-4f2a";
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
    expect(main).toContain("const openRendererWindow = (): BrowserWindow =>");
    expect(main).toContain("const SIDECAR_WARMUP_MS = 2_500");
    expect(main).toContain("initTimeoutMs: SIDECAR_INIT_TIMEOUT_MS");
    const warmupMs = Number(
      /const SIDECAR_WARMUP_MS = ([\d_]+);/.exec(main)?.[1]?.replace(/_/g, ""),
    );
    const initMs = Number(
      /const SIDECAR_INIT_TIMEOUT_MS = ([\d_]+);/
        .exec(main)?.[1]
        ?.replace(/_/g, ""),
    );
    expect(Number.isFinite(warmupMs)).toBe(true);
    expect(Number.isFinite(initMs)).toBe(true);
    // The handshake deadline has to outlast a cold frozen sidecar unpack, yet
    // still fail inside the fixed 10s packaged-smoke acceptance window.
    expect(warmupMs + initMs).toBeGreaterThan(7_500);
    expect(warmupMs + initMs).toBeLessThan(10_000);
    expect(main).toContain("await rendererReady");
    expect(main).toContain("await waitForSidecarWarmup(spawnedAt)");
    expect(main.indexOf("await waitForSidecarWarmup(spawnedAt)")).toBeLessThan(
      main.indexOf("await rpc.start()"),
    );
    expect(main).toContain("const window = openRendererWindow()");
    expect(main).toContain("const rendererLoad = window.loadFile(entryPath)");
    // The sidecar handshake overlaps Electron/renderer startup instead of being
    // serialized after it, so one packaged-smoke deadline is not spent twice.
    expect(main).toContain("const sidecarStart = (async () => {");
    expect(main).toContain("sidecarStart.catch(() => {})");
    expect(main).toContain("await sidecarStart");
    expect(main.indexOf("const sidecarStart = (async () => {")).toBeLessThan(
      main.indexOf("await rendererReady"),
    );
    expect(main.indexOf("await rpc.start()")).toBeLessThan(
      main.indexOf("const window = openRendererWindow()"),
    );
    expect(main.indexOf("await rendererLoad")).toBeLessThan(
      main.indexOf("window.show()"),
    );
    expect(main.indexOf("window.show()")).toBeLessThan(
      main.indexOf("await sidecarStart"),
    );
    // A corrupt bundled sidecar makes spawn() throw synchronously on Windows, so
    // it must land in the same visible-diagnostic catch as a missing sidecar
    // instead of escaping as an unhandled main-process error with no renderer.
    expect(main).not.toContain("const child = spawn(");
    expect(main).toContain("child = spawn(spawnSpec.command, spawnSpec.args, {");
    expect(
      main.indexOf("const spawnSpec: SidecarSpawn = resolveSidecar({"),
    ).toBeLessThan(
      main.indexOf("child = spawn(spawnSpec.command, spawnSpec.args, {"),
    );
    expect(
      main.indexOf("child = spawn(spawnSpec.command, spawnSpec.args, {"),
    ).toBeLessThan(main.indexOf('recovery: "reinstall_application"'));
    // The packaged-smoke failure diagnostic is one shot: reloading a renderer
    // that already mounted destroys the frame holding its status subscription,
    // so the failure path only loads a window that never started one.
    expect(main).toContain("const sendFailed = (): void =>");
    expect(main).toContain("if (window.webContents.getURL()) {");
    expect(main.indexOf("const sendFailed = (): void =>")).toBeLessThan(
      main.indexOf("await window.loadFile(entryPath)"),
    );
    expect(main).toContain("createWindow(smoke, rendererReady)");
    expect(main).toContain("show: false");
    expect(main.indexOf("registerDesktopIpcHandlers({")).toBeLessThan(
      main.indexOf("await window.loadFile(entryPath)"),
    );
    expect(main).toContain("status: async () => ({ ready: rpc.connectionState === \"ready\" })");
    expect(main).toContain('method: "runtime.state"');
    expect(main).toContain('state: "ready"');
    expect(main).toContain("let rendererLoaded = false");
    expect(main).toContain("if (!rendererLoaded) return");
    expect(main).toContain("if (rendererLoaded) {");
    expect(main).toContain("rendererLoaded = true");
    expect(main).toContain("shutdownPromise: Promise<void> | null");
    expect(main).toContain("runtime.shutdownPromise ??=");
    expect(main).toContain("await runtime.shutdownPromise");
    expect(main).not.toContain("void teardownRuntime(runtime)");
    expect(main).not.toContain("active && !active.shuttingDown");
    expect(main).toContain("SidecarRpcClient");
    expect(main).toContain("pathToFileURL(entryPath).href");
    // Raw line tunnel must not remain as the privileged path.
    expect(main).not.toContain("sidecar:send");
    expect(main).not.toContain("sidecar:line");
    expect(main).toContain('method === "runtime.event"');
    expect(main).toContain('method === "runtime.outcome"');
    expect(main).toContain('method === "runtime.subscriptionClosed"');
    expect(main).toContain('method === "runtime.state"');
    expect(main).not.toContain('method.startsWith("runtime.")');
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
        result: desktopInitializeResult(),
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

describe("provider settings IPC", () => {
  const PROVIDER_CHANNELS = [
    IPC.providersGet,
    IPC.providersSave,
    IPC.providersClear,
    IPC.providersRestart,
  ] as const;

  function registerWithVault(vault?: ProviderVaultPort) {
    const handlers = new Map<
      string,
      (event: IpcEventLike, ...args: unknown[]) => unknown | Promise<unknown>
    >();
    const ipcMain = {
      handle(
        channel: string,
        listener: (
          event: IpcEventLike,
          ...args: unknown[]
        ) => unknown | Promise<unknown>,
      ) {
        handlers.set(channel, listener);
      },
      removeHandler(channel: string) {
        handlers.delete(channel);
      },
    };
    // The provider handlers never reach the sidecar, so an unstarted client is
    // enough: touching it at all would be the defect this asserts against.
    const rpc = new SidecarRpcClient({ child: createChildProcessDouble() });
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
      ...(vault ? { providerVault: vault } : {}),
    });
    return handlers;
  }

  const trusted = () =>
    createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );
  const untrusted = () =>
    createIpcSenderFrom(createWebContentsDouble({ url: "https://evil.example" }));

  it.each(PROVIDER_CHANNELS)("rejects an untrusted sender on %s", async (channel) => {
    const handlers = registerWithVault(stubVault());

    await expect(
      handlers.get(channel)!(untrusted(), {
        provider: "anthropic",
        modelId: "m",
        apiKey: FAKE_KEY,
      }),
    ).rejects.toThrow(/untrusted/i);
  });

  it("answers get with a public view that carries no key", async () => {
    const handlers = registerWithVault(stubVault());

    const view = await handlers.get(IPC.providersGet)!(trusted());

    expect(view).toEqual({
      provider: "anthropic",
      modelId: "claude-x",
      hasKey: true,
      keyHint: "…4f2a",
    });
    expect(JSON.stringify(view)).not.toContain(FAKE_KEY);
  });

  it("passes a validated save through to the vault", async () => {
    const vault = stubVault();
    const handlers = registerWithVault(vault);

    await expect(
      handlers.get(IPC.providersSave)!(trusted(), {
        provider: "anthropic",
        modelId: "claude-x",
        apiKey: FAKE_KEY,
      }),
    ).resolves.toEqual({ ok: true });
    expect(vault.saved).toEqual([
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    ]);
  });

  it.each([
    ["an unexpected extra key", { provider: "a", modelId: "m", apiKey: null, x: 1 }],
    ["a missing key field", { provider: "a", modelId: "m" }],
    ["a blank provider", { provider: "  ", modelId: "m", apiKey: null }],
  ])("rejects a save with %s", async (_label, payload) => {
    const handlers = registerWithVault(stubVault());

    await expect(
      handlers.get(IPC.providersSave)!(trusted(), payload),
    ).rejects.toThrow();
  });

  it("relaunches only when asked", async () => {
    const vault = stubVault();
    const handlers = registerWithVault(vault);

    await handlers.get(IPC.providersGet)!(trusted());
    expect(vault.relaunches).toBe(0);

    await handlers.get(IPC.providersRestart)!(trusted());
    expect(vault.relaunches).toBe(1);
  });

  it("degrades safely when no vault is wired", async () => {
    const handlers = registerWithVault();

    await expect(handlers.get(IPC.providersGet)!(trusted())).resolves.toBeNull();
    await expect(
      handlers.get(IPC.providersSave)!(trusted(), {
        provider: "anthropic",
        modelId: "claude-x",
        apiKey: FAKE_KEY,
      }),
    ).resolves.toEqual({ ok: false, reason: "encryption_unavailable" });
  });
});

function stubVault(): ProviderVaultPort & {
  saved: unknown[];
  relaunches: number;
} {
  const saved: unknown[] = [];
  return {
    saved,
    relaunches: 0,
    get: () => ({
      provider: "anthropic",
      modelId: "claude-x",
      hasKey: true,
      keyHint: "…4f2a",
    }),
    save(input) {
      saved.push(input);
      return { ok: true };
    },
    clear() {
      /* nothing stored in the stub */
    },
    relaunch() {
      this.relaunches += 1;
    },
  };
}
