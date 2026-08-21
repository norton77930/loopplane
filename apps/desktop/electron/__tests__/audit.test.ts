/**
 * Electron audit IPC/preload contract (078 T068/T074).
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

describe("audit IPC handlers", () => {
  it("forwards only validated cursor pagination to audit.list", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );

    const resultP = handlers.get(IPC.auditList)!(sender, {
      sessionId: "session-1",
      cursor: "audit_opaque_cursor",
      limit: 1,
    });
    await Promise.resolve();
    const request = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: Record<string, unknown>;
    };
    expect(request.method).toBe("audit.list");
    expect(request.params).toEqual({
      session_id: "session-1",
      cursor: "audit_opaque_cursor",
      limit: 1,
    });
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          session_id: "session-1",
          entries: [],
          next_cursor: null,
        },
      }),
    );
    await expect(resultP).resolves.toEqual({
      session_id: "session-1",
      entries: [],
      next_cursor: null,
    });

    await expect(
      handlers.get(IPC.auditList)!(sender, {
        sessionId: "session-1",
        cursor: 12,
      }),
    ).rejects.toThrow("desktop.error.invalid_params");
  });

  it("rejects an untrusted audit sender before sidecar dispatch", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const evil = createIpcSenderFrom(
      createWebContentsDouble({ url: "https://evil.example" }),
    );

    await expect(
      handlers.get(IPC.auditList)!(evil, { sessionId: "session-1" }),
    ).rejects.toThrow(/untrusted/i);
    expect(child.written).toHaveLength(1);
  });

  it("keeps the preload and renderer facade cursor-only and typed", () => {
    const preload = readFileSync(
      fileURLToPath(new URL("../preload.ts", import.meta.url)),
      "utf8",
    );
    const globalDts = readFileSync(
      fileURLToPath(new URL("../../src/global.d.ts", import.meta.url)),
      "utf8",
    );

    expect(preload).toContain("audit: Object.freeze");
    expect(preload).toContain("cursor?: string");
    expect(preload).not.toContain("offset:");
    expect(globalDts).toContain("audit:");
    expect(globalDts).toContain("cursor?: string");
  });
});
