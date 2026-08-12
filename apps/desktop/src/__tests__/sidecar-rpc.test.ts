/**
 * Electron main sidecar JSON-RPC supervisor (078 T027).
 */

import { describe, expect, it } from "vitest";

import { createChildProcessDouble } from "../../electron/__tests__/helpers";
import {
  ByteLineScanner,
  SidecarRpcClient,
  SidecarRpcClientError,
} from "../../electron/sidecar-rpc";

function respondInitialize(child: ReturnType<typeof createChildProcessDouble>) {
  const written = child.written[child.written.length - 1] ?? "";
  const req = JSON.parse(written.trim()) as {
    id: string;
    method: string;
  };
  expect(req.method).toBe("initialize");
  child.emitStdout(
    JSON.stringify({
      jsonrpc: "2.0",
      id: req.id,
      result: {
        protocol: "loopplane.desktop.stdio",
        version: 1,
        methods: ["session.createInteractive", "interaction.submit", "shutdown"],
        capabilities: { interaction: "available" },
      },
    }),
  );
}

describe("ByteLineScanner", () => {
  it("reassembles split multi-byte UTF-8 across chunks", () => {
    const frames: string[] = [];
    const scanner = new ByteLineScanner(
      1024,
      (f) => frames.push(f),
      () => {
        throw new Error("overflow");
      },
    );
    // € is e2 82 ac
    const euroLine = Buffer.from('{"x":"€"}\n', "utf8");
    scanner.push(euroLine.subarray(0, 8));
    scanner.push(euroLine.subarray(8));
    expect(frames).toEqual(['{"x":"€"}']);
  });

  it("accepts CRLF by stripping terminal CR", () => {
    const frames: string[] = [];
    const scanner = new ByteLineScanner(1024, (f) => frames.push(f), () => undefined);
    scanner.push(Buffer.from('{"a":1}\r\n', "utf8"));
    expect(frames).toEqual(['{"a":1}']);
  });

  it("overflows closed incomplete frames over the byte limit", () => {
    let overflow = false;
    const scanner = new ByteLineScanner(16, () => undefined, () => {
      overflow = true;
    });
    scanner.push(Buffer.from("x".repeat(20)));
    expect(overflow).toBe(true);
  });
});

describe("SidecarRpcClient", () => {
  it("handshakes initialize then serves a request", async () => {
    const child = createChildProcessDouble();
    const states: string[] = [];
    const client = new SidecarRpcClient({
      child,
      onStateChange: (s) => states.push(s),
    });

    const startP = client.start();
    // allow microtask so write lands
    await Promise.resolve();
    respondInitialize(child);
    const init = await startP;
    expect(init.protocol).toBe("loopplane.desktop.stdio");
    expect(init.methods).toContain("session.createInteractive");
    expect(client.connectionState).toBe("ready");
    expect(states).toContain("initializing");
    expect(states).toContain("ready");

    const reqP = client.request("session.createInteractive", {
      pane_id: "p1",
    }, { mutationId: "mut-1" });
    await Promise.resolve();
    const last = JSON.parse(child.written[child.written.length - 1]!.trim()) as {
      id: string;
      method: string;
      params: { mutation_id: string; pane_id: string };
    };
    expect(last.method).toBe("session.createInteractive");
    expect(last.params.mutation_id).toBe("mut-1");
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: last.id,
        result: { session_id: "s1", subscription_id: "sub1" },
      }),
    );
    await expect(reqP).resolves.toEqual({
      session_id: "s1",
      subscription_id: "sub1",
    });
  });

  it("rejects an incompatible initialize protocol before becoming ready", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    const request = JSON.parse(child.written.at(-1)!.trim()) as { id: string };
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          protocol: "loopplane.desktop.stdio",
          version: 999,
          methods: [],
          capabilities: {},
        },
      }),
    );

    await expect(startP).rejects.toMatchObject({
      public: {
        category: "incompatible_protocol",
        messageKey: "desktop.error.incompatible_runtime",
      },
    });
    expect(client.connectionState).toBe("failed");
  });

  it("routes notifications with monotonic sequence", async () => {
    const child = createChildProcessDouble();
    const notes: Array<{ method: string; params: Record<string, unknown> }> = [];
    const client = new SidecarRpcClient({
      child,
      onNotification: (method, params) => notes.push({ method, params }),
    });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: { sequence: 1, event: { type: "user-input" } },
      }),
    );
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.outcome",
        params: { sequence: 2, reason: "completed" },
      }),
    );
    expect(notes).toHaveLength(2);
    expect(notes[0]!.method).toBe("runtime.event");
    expect(notes[1]!.method).toBe("runtime.outcome");
  });

  it("fails connection on notification sequence gap without retrying writes", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;
    const writesAfterReady = child.written.length;

    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: { sequence: 1, event: {} },
      }),
    );
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: { sequence: 3, event: {} },
      }),
    );
    expect(client.connectionState).toBe("failed");
    // no auto-retry / no extra stdin traffic
    expect(child.written.length).toBe(writesAfterReady);
  });

  it("rejects pending requests on child exit and never retries", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    const reqP = client.request("interaction.submit", {
      subscription_id: "sub",
      prompt: "hi",
    }, { mutationId: "m" });
    await Promise.resolve();
    const writes = child.written.length;
    child.emitExit(1);
    await expect(reqP).rejects.toBeInstanceOf(SidecarRpcClientError);
    expect(client.connectionState).toBe("failed");
    expect(child.written.length).toBe(writes);
    await expect(
      client.request("interaction.submit", { prompt: "again" }, { mutationId: "m2" }),
    ).rejects.toBeInstanceOf(SidecarRpcClientError);
  });

  it("caps pending requests at 64", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child, maxPendingRequests: 2 });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    void client.request("a", {}, { mutationId: "1" });
    void client.request("b", {}, { mutationId: "2" });
    await Promise.resolve();
    await expect(client.request("c", {}, { mutationId: "3" })).rejects.toMatchObject({
      public: { category: "busy" },
    });
  });

  it("shutdown drains then force-kills after deadline", async () => {
    const child = createChildProcessDouble();
    const timers: Array<{ fn: () => void; ms: number }> = [];
    const client = new SidecarRpcClient({
      child,
      initTimeoutMs: 9_999,
      shutdownTimeoutMs: 50,
      schedule: (fn, ms) => {
        timers.push({ fn, ms });
        return timers.length;
      },
      cancelSchedule: () => undefined,
    });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    const shutP = client.shutdown();
    await Promise.resolve();
    // Force-kill path after graceful deadline (child never exits on its own).
    const killTimer = timers.find((t) => t.ms === 50);
    expect(killTimer).toBeDefined();
    killTimer!.fn();
    await shutP;
    expect(child.killed).toBe(true);
    expect(client.connectionState).toBe("closed");
    // No mutation replay after shutdown/kill.
    await expect(
      client.request("interaction.submit", { prompt: "x" }, { mutationId: "z" }),
    ).rejects.toBeInstanceOf(SidecarRpcClientError);
  });

  it("init timeout kills child and surfaces unavailable", async () => {
    const child = createChildProcessDouble();
    let initTimer: (() => void) | null = null;
    const client = new SidecarRpcClient({
      child,
      initTimeoutMs: 10,
      schedule: (fn, ms) => {
        if (ms === 10) initTimer = fn;
        return 1;
      },
      cancelSchedule: () => undefined,
    });
    const startP = client.start();
    await Promise.resolve();
    expect(initTimer).not.toBeNull();
    initTimer!();
    await expect(startP).rejects.toBeInstanceOf(SidecarRpcClientError);
    expect(child.killed).toBe(true);
    expect(client.connectionState).toBe("failed");
  });

  it("generates main-owned mutation ids", () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const a = client.newMutationId();
    const b = client.newMutationId();
    expect(a).toMatch(/^mut-/);
    expect(a).not.toBe(b);
  });
});
