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

const REQUIRED_METHODS = [
  "initialize",
  "system.status",
  "system.shutdown",
  "session.list",
  "session.history",
  "session.rename",
  "session.setStarred",
  "session.delete",
  "session.fork",
  "session.createInteractive",
  "session.resumeInteractive",
  "session.releaseInteractive",
  "interaction.submit",
  "interaction.cancel",
  "interaction.answerApproval",
  "interaction.answerQuestion",
  "project.list",
  "project.create",
  "project.rename",
  "project.remove",
  "project.assignSession",
  "inspection.get",
  "agentControls.get",
  "capabilities.list",
  "capabilities.invokeAction",
  "command.execute",
  "cost.get",
  "mcp.list",
  "mcp.get",
  "mcp.upsert",
  "mcp.reconnect",
  "mcp.delete",
  "skill.list",
  "skill.get",
  "skill.write",
  "skill.import",
  "skill.delete",
  "memory.list",
  "memory.get",
  "memory.write",
  "memory.delete",
  "schedule.list",
  "schedule.get",
  "schedule.upsert",
  "schedule.enable",
  "schedule.disable",
  "schedule.runNow",
  "schedule.delete",
  "context.list",
  "context.get",
  "context.upsert",
  "context.bind",
  "context.delete",
  "modelDefault.get",
  "modelDefault.set",
  "modelDefault.clear",
  "audit.list",
  "workspace.list",
  "workspace.bind",
  "workspace.relink",
  "workspace.remove",
  "workspace.revalidate",
  "backup.describe",
  "backup.create",
  "restore.validate",
  "restore.commit",
  "restore.cancel",
];

const REQUIRED_NOTIFICATIONS = [
  "runtime.event",
  "runtime.outcome",
  "runtime.state",
  "runtime.subscriptionClosed",
];

function initializeResult(overrides: Record<string, unknown> = {}) {
  return {
    protocol: { name: "loopplane.desktop.stdio", major: 1, minor: 0 },
    runtime_event_schema: 1,
    server: { name: "loopplane-desktop-sidecar", version: "0.4.0" },
    methods: REQUIRED_METHODS,
    notifications: REQUIRED_NOTIFICATIONS,
    capabilities: {
      sessions: "available",
      interaction: "available",
      projects: "available",
      inspection: "available",
      workspace: "available",
      backup: "available",
    },
    limits: {
      control_frame_bytes: 1_048_576,
      runtime_event_frame_bytes: 8_388_608,
      prompt_bytes: 65_536,
      pending_requests: 64,
      subscriptions: 8,
    },
    ...overrides,
  };
}

function respondInitialize(child: ReturnType<typeof createChildProcessDouble>) {
  const written = child.written[child.written.length - 1] ?? "";
  const req = JSON.parse(written.trim()) as {
    id: string;
    method: string;
    params: Record<string, unknown>;
  };
  expect(req.method).toBe("initialize");
  expect(req.params).toEqual({
    protocol: { name: "loopplane.desktop.stdio", major: 1, minor: 0 },
    runtime_event_schema: 1,
    client: { name: "loopplane-desktop-main", version: "0.0.0" },
    requested_capabilities: [
      "sessions",
      "interaction",
      "projects",
      "inspection",
      "workspace",
      "backup",
    ],
  });
  child.emitStdout(
    JSON.stringify({
      jsonrpc: "2.0",
      id: req.id,
      result: initializeResult(),
    }),
  );
}

describe("ByteLineScanner", () => {
  it("reassembles split multi-byte UTF-8 across chunks", () => {
    const frames: string[] = [];
    const scanner = new ByteLineScanner(
      1024,
      8192,
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
    const scanner = new ByteLineScanner(
      1024,
      8192,
      (f) => frames.push(f),
      () => undefined,
    );
    scanner.push(Buffer.from('{"a":1}\r\n', "utf8"));
    expect(frames).toEqual(['{"a":1}']);
  });

  it("rejects empty frames instead of silently resynchronizing", () => {
    let rejected = false;
    const scanner = new ByteLineScanner(
      1024,
      8192,
      () => undefined,
      () => {
        rejected = true;
      },
    );
    scanner.push(Buffer.from("\n", "utf8"));
    expect(rejected).toBe(true);
  });

  it("overflows closed incomplete frames over the byte limit", () => {
    let overflow = false;
    const scanner = new ByteLineScanner(16, 32, () => undefined, () => {
      overflow = true;
    });
    scanner.push(Buffer.from("x".repeat(20)));
    expect(overflow).toBe(true);
  });

  it("counts the frame kind before decode and allows only runtime events to use 8 MiB", () => {
    const frames: string[] = [];
    let overflow = false;
    const scanner = new ByteLineScanner(
      128,
      4096,
      (frame) => frames.push(frame),
      () => {
        overflow = true;
      },
    );
    const event = JSON.stringify({
      jsonrpc: "2.0",
      method: "runtime.event",
      params: {
        notification_seq: 1,
        subscription_id: "sub-1",
        session_id: "session-1",
        event: { chunk: "x".repeat(256) },
      },
    });
    expect(event.startsWith('{"jsonrpc":"2.0","method":"runtime.event","params":{')).toBe(
      true,
    );
    scanner.push(Buffer.from(`${event}\n`, "utf8"));

    expect(overflow).toBe(false);
    expect(frames).toEqual([event]);
  });

  it("does not grant the event frame limit to a spoofed control frame", () => {
    let overflow = false;
    const scanner = new ByteLineScanner(
      128,
      4096,
      () => undefined,
      () => {
        overflow = true;
      },
    );
    const spoof = JSON.stringify({
      jsonrpc: "2.0",
      method: "runtime.state",
      params: {
        marker: "runtime.event",
        padding: "x".repeat(256),
      },
    });
    scanner.push(Buffer.from(`${spoof}\n`, "utf8"));

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
    expect(init.protocol).toEqual({
      name: "loopplane.desktop.stdio",
      major: 1,
      minor: 0,
    });
    expect(init.runtimeEventSchema).toBe(1);
    expect(init.methods).toEqual(REQUIRED_METHODS);
    expect(init.notifications).toEqual(REQUIRED_NOTIFICATIONS);
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
        result: initializeResult({
          protocol: { name: "loopplane.desktop.stdio", major: 999, minor: 0 },
        }),
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

  it("rejects abbreviated initialize metadata before becoming ready", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    const request = JSON.parse(child.written.at(-1)!.trim()) as { id: string };
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: initializeResult({
          methods: REQUIRED_METHODS.filter((method) => method !== "backup.create"),
        }),
      }),
    );

    await expect(startP).rejects.toMatchObject({
      public: { category: "incompatible_protocol" },
    });
    expect(client.connectionState).toBe("failed");
  });

  it("fails closed when a response error contains untrusted public strings", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    const requestP = client.request("session.list", {});
    await Promise.resolve();
    const request = JSON.parse(child.written.at(-1)!.trim()) as { id: string };
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        error: {
          code: -32999,
          message: "C:\\private\\token-secret.txt",
          data: {
            category: "private_category_token-secret",
            retryable: false,
            recovery: "retry|restart_runtime",
            messageKey: "desktop.error.token-secret",
          },
        },
      }),
    );

    const error = await requestP.catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(SidecarRpcClientError);
    expect((error as SidecarRpcClientError).public).toEqual({
      code: -32603,
      message: "Runtime unavailable",
      category: "internal_failure",
      retryable: true,
      recovery: "restart_runtime",
      messageKey: "desktop.error.internal_failure",
    });
    expect(JSON.stringify((error as SidecarRpcClientError).public)).not.toContain(
      "token-secret",
    );
    expect((error as Error).message).not.toContain("private");
  });

  it("accepts valid non-BMP UTF-8 content in runtime events", async () => {
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
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: { type: "assistant-output-increment", text: "😀" },
        },
      }),
    );

    expect(client.connectionState).toBe("ready");
    expect(notes).toHaveLength(1);
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
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: { type: "user-input" },
        },
      }),
    );
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.outcome",
        params: {
          notification_seq: 2,
          subscription_id: "sub-1",
          session_id: "session-1",
          reason: "natural-completion",
          turns: 1,
        },
      }),
    );
    expect(notes).toHaveLength(2);
    expect(notes[0]!.method).toBe("runtime.event");
    expect(notes[1]!.method).toBe("runtime.outcome");
  });

  it.each([
    [
      "unknown method",
      "runtime.private",
      { notification_seq: 1, private_field: "lp-synth-sensitive" },
    ],
    [
      "string event payload",
      "runtime.event",
      {
        notification_seq: 1,
        subscription_id: "sub-1",
        session_id: "session-1",
        event: "token-secret",
      },
    ],
    [
      "missing event correlation",
      "runtime.event",
      { notification_seq: 1, event: { type: "user-input" } },
    ],
    [
      "malformed outcome",
      "runtime.outcome",
      {
        notification_seq: 1,
        subscription_id: "sub-1",
        session_id: "session-1",
        reason: "natural-completion",
        turns: "token-secret",
      },
    ],
    [
      "malformed state",
      "runtime.state",
      { notification_seq: 1, state: "ready" },
    ],
    [
      "malformed subscription close",
      "runtime.subscriptionClosed",
      {
        notification_seq: 1,
        subscription_id: "sub-1",
        session_id: "session-1",
        reason: "completed",
        history_readable: "token-secret",
      },
    ],
  ])("fails closed on %s notification", async (_label, method, params) => {
    const child = createChildProcessDouble();
    const notes: unknown[] = [];
    const client = new SidecarRpcClient({
      child,
      onNotification: (...args) => notes.push(args),
    });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(JSON.stringify({ jsonrpc: "2.0", method, params }));

    expect(client.connectionState).toBe("failed");
    expect(notes).toEqual([]);
  });

  it("fails closed on extra notification envelope fields", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: {},
        },
        private_token: "token-secret",
      }),
    );

    expect(client.connectionState).toBe("failed");
  });

  it.each([
    [
      "duplicate object keys",
      '{"jsonrpc":"2.0","method":"runtime.state","params":{"notification_seq":1,"state":"opened","state":"draining"}}',
    ],
    [
      "more than 128 keys in a nested object",
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: Object.fromEntries(
            Array.from({ length: 129 }, (_, index) => [`k${index}`, index]),
          ),
        },
      }),
    ],
    [
      "more than 32 nested JSON levels",
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: Array.from({ length: 33 }).reduce<unknown>(
            (value) => [value],
            {},
          ),
        },
      }),
    ],
    [
      "a non-finite number",
      '{"jsonrpc":"2.0","method":"runtime.outcome","params":{"notification_seq":1,"subscription_id":"sub-1","session_id":"session-1","reason":"natural-completion","turns":1e400}}',
    ],
    [
      "an unpaired surrogate",
      '{"jsonrpc":"2.0","method":"runtime.state","params":{"notification_seq":1,"state":"\\ud800"}}',
    ],
    [
      "prototype-backed notification fields",
      '{"jsonrpc":"2.0","method":"runtime.state","params":{"__proto__":{"notification_seq":1,"state":"opened"}}}',
    ],
  ])("fails closed on strict JSON violation: %s", async (_label, frame) => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(frame);

    expect(client.connectionState).toBe("failed");
  });

  it("enforces outcome and subscription-close ordering per subscription", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.outcome",
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          reason: "natural-completion",
          turns: 1,
        },
      }),
    );
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: {
          notification_seq: 2,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: { type: "assistant-output-increment" },
        },
      }),
    );
    expect(client.connectionState).toBe("failed");
  });

  it("accepts release as the final notification without requiring a run outcome", async () => {
    const child = createChildProcessDouble();
    const notes: string[] = [];
    const client = new SidecarRpcClient({
      child,
      onNotification: (method) => notes.push(method),
    });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.subscriptionClosed",
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          reason: "released",
          history_readable: true,
        },
      }),
    );

    expect(client.connectionState).toBe("ready");
    expect(notes).toEqual(["runtime.subscriptionClosed"]);
  });

  it("rejects a control response above the control limit", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({
      child,
      maxControlFrameBytes: 2_048,
      maxEventFrameBytes: 8_192,
    });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    const requestP = client.request("session.list", {});
    await Promise.resolve();
    const request = JSON.parse(child.written.at(-1)!.trim()) as { id: string };
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: { sessions: [], padding: "x".repeat(4_096) },
      }),
    );

    await expect(requestP).rejects.toBeInstanceOf(SidecarRpcClientError);
    expect(client.connectionState).toBe("failed");
  });

  it.each([
    {
      label: "success with error",
      response: { result: { sessions: [] }, error: {} },
    },
    {
      label: "success without result",
      response: {},
    },
    {
      label: "response with extra field",
      response: {
        result: { sessions: [] },
        private_field: "lp-synth-sensitive",
      },
    },
  ])("fails closed on an invalid $label envelope", async ({ response }) => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    const requestP = client.request("session.list", {});
    await Promise.resolve();
    const request = JSON.parse(child.written.at(-1)!.trim()) as { id: string };
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        ...response,
      }),
    );

    await expect(requestP).rejects.toBeInstanceOf(SidecarRpcClientError);
    expect(client.connectionState).toBe("failed");
  });

  it("fails connection when a notification omits notification_seq", async () => {
    const child = createChildProcessDouble();
    const client = new SidecarRpcClient({ child });
    const startP = client.start();
    await Promise.resolve();
    respondInitialize(child);
    await startP;

    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: { event: {} },
      }),
    );
    expect(client.connectionState).toBe("failed");
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
        params: {
          notification_seq: 1,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: {},
        },
      }),
    );
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        method: "runtime.event",
        params: {
          notification_seq: 3,
          subscription_id: "sub-1",
          session_id: "session-1",
          event: {},
        },
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
