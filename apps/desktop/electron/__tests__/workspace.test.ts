/**
 * Electron main workspace IPC + native chooser (078 T037).
 */

import { describe, expect, it, vi } from "vitest";

import {
  createChildProcessDouble,
  createIpcSenderFrom,
  createWebContentsDouble,
  desktopInitializeResult,
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
      result: desktopInitializeResult(),
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

describe("workspace IPC handlers", () => {
  it("chooseAndBind cancels without RPC when picker returns null", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const chooseDirectory = vi.fn(async () => null);
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc, chooseDirectory });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );
    const writesBefore = child.written.length;
    await expect(
      handlers.get(IPC.workspaceChooseAndBind)!(sender, { label: "Docs" }),
    ).resolves.toBeNull();
    expect(chooseDirectory).toHaveBeenCalled();
    // No bind RPC after cancel
    expect(child.written.length).toBe(writesBefore);
  });

  it("chooseAndBind sends trusted path privately and returns only safe projection", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const secretPath = "C:\\\\SyntheticPrivateRoot\\\\docs";
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
      chooseDirectory: async () => secretPath,
    });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );

    const bindP = handlers.get(IPC.workspaceChooseAndBind)!(sender, {
      label: "Docs",
    });
    await Promise.resolve();
    const req = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { path: string; label: string; mutation_id: string };
    };
    expect(req.method).toBe("workspace.bind");
    expect(req.params.path).toBe(secretPath);
    expect(req.params.mutation_id).toMatch(/^mut-/);
    const safeResult = {
      workspace: {
        id: "w1",
        label: "Docs",
        availability: "available",
        actions: ["open", "relink", "remove"],
      },
    };
    child.emitStdout(
      JSON.stringify({ jsonrpc: "2.0", id: req.id, result: safeResult }),
    );
    const result = await bindP;
    expect(result).toEqual(safeResult);
    // Renderer-visible result must not echo the absolute path
    expect(JSON.stringify(result)).not.toContain("Users");
    expect(JSON.stringify(result)).not.toContain(secretPath);
  });

  it("lists workspaces without path fields", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );
    const listP = handlers.get(IPC.workspaceList)!(sender);
    await Promise.resolve();
    const req = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
    };
    expect(req.method).toBe("workspace.list");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: req.id,
        result: {
          workspaces: [
            { id: "w1", label: "Docs", availability: "available", actions: [] },
          ],
        },
      }),
    );
    const result = await listP;
    expect(JSON.stringify(result)).not.toMatch(/[A-Za-z]:\\/);
  });

  it("rejects untrusted senders for workspace.list", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const evil = createIpcSenderFrom(
      createWebContentsDouble({ url: "https://evil.example" }),
    );
    await expect(handlers.get(IPC.workspaceList)!(evil)).rejects.toThrow(
      /untrusted/i,
    );
  });
});
