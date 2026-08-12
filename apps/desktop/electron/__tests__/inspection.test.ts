/**
 * Electron inspection / agentControls / capabilities IPC (078 T059).
 */

import { describe, expect, it } from "vitest";

import {
  createChildProcessDouble,
  createIpcSenderFrom,
  createWebContentsDouble,
  TRUSTED_HANDLER_OPTIONS,
} from "./helpers";
import { IPC } from "../ipc-channels";
import { registerDesktopIpcHandlers } from "../ipc-handlers";
import { SidecarRpcClient } from "../sidecar-rpc";
import type { IpcEventLike } from "../window-security";

async function readyRpc(child: ReturnType<typeof createChildProcessDouble>) {
  const rpc = new SidecarRpcClient({ child });
  const startP = rpc.start();
  await Promise.resolve();
  const initReq = JSON.parse(child.written[0]!.trim()) as { id: string };
  child.emitStdout(
    JSON.stringify({
      jsonrpc: "2.0",
      id: initReq.id,
      result: {
        protocol: "loopplane.desktop.stdio",
        version: 1,
        methods: [
          "inspection.get",
          "agentControls.get",
          "capabilities.list",
          "capabilities.invokeAction",
        ],
        capabilities: {},
      },
    }),
  );
  await startP;
  return rpc;
}

function ipcMap() {
  const handlers = new Map<
    string,
    (event: IpcEventLike, ...args: unknown[]) => unknown | Promise<unknown>
  >();
  return {
    handlers,
    ipcMain: {
      handle(
        channel: string,
        listener: (event: IpcEventLike, ...args: unknown[]) => unknown | Promise<unknown>,
      ) {
        handlers.set(channel, listener);
      },
      removeHandler(channel: string) {
        handlers.delete(channel);
      },
    },
  };
}

describe("inspection IPC", () => {
  it("maps inspection.get without renderer request ids", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );
    const p = handlers.get(IPC.inspectionGet)!(sender, { sessionId: "s1" });
    await Promise.resolve();
    const req = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { session_id: string };
    };
    expect(req.method).toBe("inspection.get");
    expect(req.params.session_id).toBe("s1");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: req.id,
        result: {
          session_id: "s1",
          skills: [],
          tools: [{ name: "echo", available: true }],
          mcp: [],
          memory: [],
          unavailable: false,
        },
      }),
    );
    const result = await p;
    expect(JSON.stringify(result)).not.toMatch(/secret|password/i);
  });

  it("rejects untrusted senders for agentControls.get", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const evil = createIpcSenderFrom(
      createWebContentsDouble({ url: "https://evil.example" }),
    );
    await expect(
      handlers.get(IPC.agentControlsGet)!(evil, { sessionId: "s1" }),
    ).rejects.toThrow(/untrusted/i);
  });

  it("maps a one-run permission mode only when it is a string", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(createWebContentsDouble({ url: "file:///app/dist/index.html" }));
    const pending = handlers.get(IPC.interactionSubmit)!(sender, {
      subscriptionId: "sub-1", prompt: "run", permissionMode: "plan",
    });
    await Promise.resolve();
    const req = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string; params: { subscription_id: string; prompt: string; permission_mode?: string };
    };
    expect(req.params).toMatchObject({ subscription_id: "sub-1", prompt: "run", permission_mode: "plan" });
    child.emitStdout(JSON.stringify({ jsonrpc: "2.0", id: req.id, result: {} }));
    await expect(pending).resolves.toEqual({});
    const withoutDraft = handlers.get(IPC.interactionSubmit)!(sender, {
      subscriptionId: "sub-1", prompt: "run",
    });
    await Promise.resolve();
    const noDraftReq = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string; params: Record<string, unknown>;
    };
    expect(noDraftReq.params).toMatchObject({ subscription_id: "sub-1", prompt: "run" });
    expect(noDraftReq.params).not.toHaveProperty("permission_mode");
    child.emitStdout(JSON.stringify({ jsonrpc: "2.0", id: noDraftReq.id, result: {} }));
    await expect(withoutDraft).resolves.toEqual({});
    await expect(handlers.get(IPC.interactionSubmit)!(sender, {
      subscriptionId: "sub-1", prompt: "run", permissionMode: true,
    })).rejects.toThrow("desktop.error.invalid_params");
  });

  it("capabilities.invokeAction uses main-owned mutation id", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );
    const p = handlers.get(IPC.capabilitiesInvokeAction)!(sender, {
      capabilityId: "memory",
      action: "refresh",
    });
    await Promise.resolve();
    const req = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { capability_id: string; action: string; mutation_id: string };
    };
    expect(req.method).toBe("capabilities.invokeAction");
    expect(req.params.mutation_id).toMatch(/^mut-/);
    expect(req.params.capability_id).toBe("memory");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: req.id,
        result: { capabilities: [] },
      }),
    );
    await expect(p).resolves.toEqual({ capabilities: [] });
  });
});
