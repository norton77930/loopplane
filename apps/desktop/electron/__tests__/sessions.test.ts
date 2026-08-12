/**
 * Electron main session/project IPC (078 T037).
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
          "session.list",
          "session.setStarred",
          "session.delete",
          "session.fork",
          "project.list",
          "project.create",
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

describe("session/project IPC handlers", () => {
  it("lists sessions and stars without exposing mutation ids to renderer", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });

    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );

    const listP = handlers.get(IPC.sessionList)!(sender, { query: "hi" });
    await Promise.resolve();
    const listReq = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { query?: string };
    };
    expect(listReq.method).toBe("session.list");
    expect(listReq.params.query).toBe("hi");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: listReq.id,
        result: { sessions: [{ session_id: "s1", title: "One", starred: false }] },
      }),
    );
    await expect(listP).resolves.toEqual({
      sessions: [{ session_id: "s1", title: "One", starred: false }],
    });

    const starP = handlers.get(IPC.sessionSetStarred)!(sender, {
      sessionId: "s1",
      starred: true,
    });
    await Promise.resolve();
    const starReq = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { mutation_id: string; session_id: string; starred: boolean };
    };
    expect(starReq.method).toBe("session.setStarred");
    expect(starReq.params.mutation_id).toMatch(/^mut-/);
    expect(starReq.params.session_id).toBe("s1");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: starReq.id,
        result: { session_id: "s1", starred: true },
      }),
    );
    await expect(starP).resolves.toEqual({ session_id: "s1", starred: true });
  });

  it("requires confirmation for delete and fork", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );

    await expect(
      handlers.get(IPC.sessionDelete)!(sender, { sessionId: "s1" }),
    ).rejects.toThrow();

    await expect(
      handlers.get(IPC.sessionFork)!(sender, { sessionId: "s1" }),
    ).rejects.toThrow();
  });

  it("creates projects with main-owned mutation ids", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const sender = createIpcSenderFrom(
      createWebContentsDouble({ url: "file:///app/dist/index.html" }),
    );

    const createP = handlers.get(IPC.projectCreate)!(sender, { label: "Work" });
    await Promise.resolve();
    const req = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { mutation_id: string; label: string };
    };
    expect(req.method).toBe("project.create");
    expect(req.params.mutation_id).toMatch(/^mut-/);
    expect(req.params.label).toBe("Work");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: req.id,
        result: { project: { id: "p1", label: "Work" } },
      }),
    );
    await expect(createP).resolves.toEqual({
      project: { id: "p1", label: "Work" },
    });
  });

  it("rejects untrusted senders for session.list", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ipcMain, rpc });
    const evil = createIpcSenderFrom(
      createWebContentsDouble({ url: "https://evil.example" }),
    );
    await expect(handlers.get(IPC.sessionList)!(evil, {})).rejects.toThrow(
      /untrusted/i,
    );
  });
});
