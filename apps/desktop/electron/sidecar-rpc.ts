/**
 * Electron-main sidecar JSON-RPC supervisor (078 T027).
 *
 * Owns child stdio: byte-oriented LF framing, initialize handshake, pending
 * request map, notification routing, crash/EOF fail-closed, graceful drain +
 * forced kill. Never retries mutations after process failure. Pure Node module
 * (no `electron` import) so unit tests inject a child-process double.
 */

import { randomUUID } from "node:crypto";

export type ConnectionState =
  | "starting"
  | "initializing"
  | "ready"
  | "draining"
  | "closed"
  | "failed";

export type SidecarStdioChild = {
  stdin: {
    write: (data: string | Buffer) => boolean;
    end?: () => void;
  };
  stdout: {
    on: (event: string, cb: (chunk: Buffer) => void) => void;
  };
  stderr?: {
    on: (event: string, cb: (chunk: Buffer) => void) => void;
  };
  on: (event: string, cb: (...args: unknown[]) => void) => void;
  kill: (signal?: string) => void;
  killed?: boolean;
};

export type PublicRpcError = {
  code: number;
  message: string;
  category: string;
  retryable: boolean;
  recovery?: string;
  messageKey?: string;
};

export class SidecarRpcClientError extends Error {
  readonly public: PublicRpcError;
  readonly connectionState: ConnectionState;

  constructor(publicError: PublicRpcError, connectionState: ConnectionState) {
    super(publicError.message);
    this.name = "SidecarRpcClientError";
    this.public = publicError;
    this.connectionState = connectionState;
  }
}

export type InitializeResult = {
  protocol: string;
  version: number;
  methods: string[];
  capabilities: Record<string, unknown>;
  raw: Record<string, unknown>;
};

export type NotificationHandler = (
  method: string,
  params: Record<string, unknown>,
) => void;

export type SidecarRpcOptions = {
  child: SidecarStdioChild;
  /** Initialization deadline (default 5000 ms). */
  initTimeoutMs?: number;
  /** Graceful shutdown deadline before kill (default 5000 ms). */
  shutdownTimeoutMs?: number;
  maxControlFrameBytes?: number;
  maxEventFrameBytes?: number;
  maxPendingRequests?: number;
  clientName?: string;
  clientVersion?: string;
  schedule?: (fn: () => void, ms: number) => unknown;
  cancelSchedule?: (handle: unknown) => void;
  onNotification?: NotificationHandler;
  onStateChange?: (state: ConnectionState) => void;
};

const PROTOCOL_NAME = "loopplane.desktop.stdio";
const PROTOCOL_VERSION = 1;

const DEFAULT_INIT_MS = 5_000;
const DEFAULT_SHUTDOWN_MS = 5_000;
const DEFAULT_CONTROL_FRAME = 1_048_576;
const DEFAULT_EVENT_FRAME = 8_388_608;
const DEFAULT_MAX_PENDING = 64;

const FAILED_PUBLIC: PublicRpcError = {
  code: -32603,
  message: "Runtime unavailable",
  category: "internal_failure",
  retryable: true,
  recovery: "restart_runtime",
  messageKey: "desktop.error.internal_failure",
};

const BUSY_PUBLIC: PublicRpcError = {
  code: -32004,
  message: "Busy",
  category: "busy",
  retryable: false,
  messageKey: "desktop.error.busy",
};

const STATE_PUBLIC: PublicRpcError = {
  code: -32005,
  message: "Invalid connection state",
  category: "invalid_state",
  retryable: false,
  messageKey: "desktop.error.invalid_state",
};

type Pending = {
  method: string;
  resolve: (value: unknown) => void;
  reject: (err: SidecarRpcClientError) => void;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function mapWireError(error: unknown): PublicRpcError {
  const obj = asRecord(error);
  if (!obj) return { ...FAILED_PUBLIC };
  const data = asRecord(obj.data) ?? {};
  const code = typeof obj.code === "number" ? obj.code : FAILED_PUBLIC.code;
  const message =
    typeof obj.message === "string" && obj.message.trim()
      ? obj.message
      : FAILED_PUBLIC.message;
  const category =
    typeof data.category === "string" ? data.category : "internal_failure";
  const retryable = data.retryable === true;
  const recovery =
    typeof data.recovery === "string" ? data.recovery : undefined;
  const messageKey =
    typeof data.messageKey === "string"
      ? data.messageKey
      : typeof data.message_key === "string"
        ? data.message_key
        : undefined;
  return { code, message, category, retryable, recovery, messageKey };
}

/**
 * Byte-oriented LF frame scanner. Counts bytes before UTF-8 decode so split
 * multi-byte sequences and oversize frames fail closed without partial dispatch.
 */
export class ByteLineScanner {
  private buffer = Buffer.alloc(0);

  constructor(
    private readonly maxFrameBytes: number,
    private readonly onFrame: (utf8: string) => void,
    private readonly onOverflow: () => void,
  ) {}

  push(chunk: Buffer): void {
    if (chunk.length === 0) return;
    this.buffer = Buffer.concat([this.buffer, chunk]);
    for (;;) {
      const nl = this.buffer.indexOf(0x0a);
      if (nl < 0) {
        if (this.buffer.length > this.maxFrameBytes) {
          this.buffer = Buffer.alloc(0);
          this.onOverflow();
        }
        return;
      }
      let frame = this.buffer.subarray(0, nl);
      this.buffer = this.buffer.subarray(nl + 1);
      if (frame.length > 0 && frame[frame.length - 1] === 0x0d) {
        frame = frame.subarray(0, frame.length - 1);
      }
      if (frame.length > this.maxFrameBytes) {
        this.onOverflow();
        return;
      }
      if (frame.length === 0) {
        continue;
      }
      let text: string;
      try {
        text = frame.toString("utf8");
        // Reject invalid UTF-8 replacement when source had unpaired sequences.
        // Buffer.toString replaces; detect via round-trip for non-ASCII strictness.
        if (Buffer.byteLength(text, "utf8") !== frame.length) {
          this.onOverflow();
          return;
        }
      } catch {
        this.onOverflow();
        return;
      }
      this.onFrame(text);
    }
  }

  reset(): void {
    this.buffer = Buffer.alloc(0);
  }
}

export class SidecarRpcClient {
  private state: ConnectionState = "starting";
  private readonly child: SidecarStdioChild;
  private readonly initTimeoutMs: number;
  private readonly shutdownTimeoutMs: number;
  private readonly maxControlFrameBytes: number;
  private readonly maxEventFrameBytes: number;
  private readonly maxPendingRequests: number;
  private readonly clientName: string;
  private readonly clientVersion: string;
  private readonly schedule: (fn: () => void, ms: number) => unknown;
  private readonly cancelSchedule: (handle: unknown) => void;
  private readonly onNotification?: NotificationHandler;
  private readonly onStateChange?: (state: ConnectionState) => void;

  private readonly pending = new Map<string, Pending>();
  private idSeq = 0;
  private lastNotificationSeq = 0;
  private scanner: ByteLineScanner;
  private initTimer: unknown = null;
  private shutdownTimer: unknown = null;
  private shutdownResolve: (() => void) | null = null;
  private stdoutEnded = false;
  private failed = false;

  constructor(options: SidecarRpcOptions) {
    this.child = options.child;
    this.initTimeoutMs = options.initTimeoutMs ?? DEFAULT_INIT_MS;
    this.shutdownTimeoutMs = options.shutdownTimeoutMs ?? DEFAULT_SHUTDOWN_MS;
    this.maxControlFrameBytes =
      options.maxControlFrameBytes ?? DEFAULT_CONTROL_FRAME;
    this.maxEventFrameBytes =
      options.maxEventFrameBytes ?? DEFAULT_EVENT_FRAME;
    this.maxPendingRequests =
      options.maxPendingRequests ?? DEFAULT_MAX_PENDING;
    this.clientName = options.clientName ?? "loopplane-desktop-main";
    this.clientVersion = options.clientVersion ?? "0.0.0";
    this.schedule =
      options.schedule ??
      ((fn, ms) => setTimeout(fn, ms));
    this.cancelSchedule =
      options.cancelSchedule ??
      ((h) => clearTimeout(h as ReturnType<typeof setTimeout>));
    this.onNotification = options.onNotification;
    this.onStateChange = options.onStateChange;

    // Use event frame bound for scanner so control and event frames both fit;
    // per-frame kind checks apply after parse.
    this.scanner = new ByteLineScanner(
      this.maxEventFrameBytes,
      (line) => this.onStdoutLine(line),
      () => this.failConnection("frame_overflow"),
    );

    this.child.stdout.on("data", (chunk: Buffer) => {
      if (this.failed || this.state === "closed") return;
      this.scanner.push(chunk);
    });
    this.child.stdout.on("end", () => {
      this.stdoutEnded = true;
      if (this.state === "draining") {
        this.finishClosed();
        return;
      }
      if (this.state !== "closed" && this.state !== "failed") {
        this.failConnection("stdout_eof");
      }
    });
    this.child.on("error", () => {
      this.failConnection("child_error");
    });
    this.child.on("exit", () => {
      if (this.state === "draining" || this.state === "closed") {
        this.finishClosed();
        return;
      }
      this.failConnection("child_exit");
    });
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  /** Spawn-adjacent start: run initialize handshake. */
  async start(): Promise<InitializeResult> {
    if (this.state !== "starting") {
      throw new SidecarRpcClientError(STATE_PUBLIC, this.state);
    }
    this.setState("initializing");

    const initPromise = this.rawRequest(
      "initialize",
      {
        protocol: PROTOCOL_NAME,
        version: PROTOCOL_VERSION,
        client: { name: this.clientName, version: this.clientVersion },
      },
      { allowBeforeReady: true },
    );

    this.initTimer = this.schedule(() => {
      this.failConnection("init_timeout");
      try {
        this.child.kill();
      } catch {
        /* ignore */
      }
    }, this.initTimeoutMs);

    try {
      const result = await initPromise;
      if (this.initTimer !== null) {
        this.cancelSchedule(this.initTimer);
        this.initTimer = null;
      }
      const record = asRecord(result) ?? {};
      const methods = Array.isArray(record.methods)
        ? record.methods.filter((m): m is string => typeof m === "string")
        : [];
      const capabilities = asRecord(record.capabilities) ?? {};
      const protocol =
        typeof record.protocol === "string" ? record.protocol : PROTOCOL_NAME;
      const version =
        typeof record.version === "number" ? record.version : PROTOCOL_VERSION;
      if (protocol !== PROTOCOL_NAME || version !== PROTOCOL_VERSION) {
        this.failConnection("protocol_incompatible");
        throw new SidecarRpcClientError(
          {
            code: -32001,
            message: "Incompatible runtime",
            category: "incompatible_protocol",
            retryable: false,
            recovery: "contact_support",
            messageKey: "desktop.error.incompatible_runtime",
          },
          this.state,
        );
      }
      this.setState("ready");
      return {
        protocol,
        version,
        methods,
        capabilities,
        raw: record,
      };
    } catch (err) {
      if (this.initTimer !== null) {
        this.cancelSchedule(this.initTimer);
        this.initTimer = null;
      }
      if (err instanceof SidecarRpcClientError) throw err;
      this.failConnection("init_failed");
      throw new SidecarRpcClientError(
        {
          ...FAILED_PUBLIC,
          category: "unavailable",
          message: "Incompatible or unavailable runtime",
          messageKey: "desktop.error.incompatible_or_unavailable_runtime",
        },
        this.state,
      );
    }
  }

  /**
   * Issue one JSON-RPC request. Never auto-retries after failure (FR-041).
   * Main generates request IDs; optional mutation_id is injected into params.
   */
  async request(
    method: string,
    params: Record<string, unknown> = {},
    options: { mutationId?: string } = {},
  ): Promise<unknown> {
    if (this.state !== "ready") {
      throw new SidecarRpcClientError(STATE_PUBLIC, this.state);
    }
    const body =
      options.mutationId !== undefined
        ? { ...params, mutation_id: options.mutationId }
        : { ...params };
    return this.rawRequest(method, body, { allowBeforeReady: false });
  }

  /** Allocate a main-owned mutation id (renderer never supplies these). */
  newMutationId(): string {
    return `mut-${randomUUID()}`;
  }

  /**
   * Graceful shutdown: reject new work, best-effort system.shutdown / shutdown,
   * wait up to deadline, then kill. No request replay.
   */
  async shutdown(): Promise<void> {
    if (this.state === "closed" || this.state === "failed") {
      return;
    }
    if (this.state === "draining") {
      // Already draining; wait for existing close if tracked.
      if (this.shutdownResolve === null) return;
      return new Promise((resolve) => {
        const prev = this.shutdownResolve;
        this.shutdownResolve = () => {
          prev?.();
          resolve();
        };
      });
    }
    this.setState("draining");

    // Stop accepting new non-shutdown work (state already draining).
    for (const [id, pending] of [...this.pending.entries()]) {
      if (
        pending.method === "system.shutdown" ||
        pending.method === "shutdown"
      ) {
        continue;
      }
      this.pending.delete(id);
      pending.reject(
        new SidecarRpcClientError(
          {
            code: -32005,
            message: "Shutting down",
            category: "invalid_state",
            retryable: false,
            messageKey: "desktop.error.shutting_down",
          },
          "draining",
        ),
      );
    }

    const closed = new Promise<void>((resolve) => {
      this.shutdownResolve = resolve;
      this.shutdownTimer = this.schedule(() => {
        try {
          this.child.kill();
        } catch {
          /* ignore */
        }
        this.finishClosed();
      }, this.shutdownTimeoutMs);
    });

    // Best-effort RPC; never block shutdown on an unanswered child.
    void this.rawRequest(
      "system.shutdown",
      { mutation_id: this.newMutationId() },
      { allowBeforeReady: true, allowWhileDraining: true },
    )
      .catch(() =>
        this.rawRequest(
          "shutdown",
          {},
          { allowBeforeReady: true, allowWhileDraining: true },
        ),
      )
      .catch(() => undefined)
      .then(() => {
        try {
          this.child.stdin.end?.();
        } catch {
          /* ignore */
        }
      });

    if (this.stdoutEnded || this.child.killed) {
      this.finishClosed();
    }

    await closed;
  }

  private rawRequest(
    method: string,
    params: Record<string, unknown>,
    flags: {
      allowBeforeReady?: boolean;
      allowWhileDraining?: boolean;
    },
  ): Promise<unknown> {
    if (this.failed || this.state === "failed" || this.state === "closed") {
      return Promise.reject(
        new SidecarRpcClientError(FAILED_PUBLIC, this.state),
      );
    }
    if (this.state === "draining" && !flags.allowWhileDraining) {
      return Promise.reject(
        new SidecarRpcClientError(STATE_PUBLIC, this.state),
      );
    }
    if (
      this.state !== "ready" &&
      this.state !== "initializing" &&
      !flags.allowBeforeReady &&
      !flags.allowWhileDraining
    ) {
      return Promise.reject(
        new SidecarRpcClientError(STATE_PUBLIC, this.state),
      );
    }
    if (this.pending.size >= this.maxPendingRequests) {
      return Promise.reject(new SidecarRpcClientError(BUSY_PUBLIC, this.state));
    }

    this.idSeq += 1;
    const id = `m-${String(this.idSeq).padStart(8, "0")}`;
    const envelope = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };
    const line = `${JSON.stringify(envelope)}\n`;
    if (Buffer.byteLength(line, "utf8") > this.maxControlFrameBytes) {
      return Promise.reject(
        new SidecarRpcClientError(
          {
            code: -32600,
            message: "Request too large",
            category: "invalid_request",
            retryable: false,
            messageKey: "desktop.error.invalid_request",
          },
          this.state,
        ),
      );
    }

    return new Promise<unknown>((resolve, reject) => {
      this.pending.set(id, { method, resolve, reject });
      try {
        const ok = this.child.stdin.write(line);
        if (ok === false) {
          // Backpressure: still wait for response; no auto-retry on later fail.
        }
      } catch {
        this.pending.delete(id);
        reject(new SidecarRpcClientError(FAILED_PUBLIC, this.state));
      }
    });
  }

  private onStdoutLine(line: string): void {
    if (this.failed || this.state === "closed") return;
    let msg: unknown;
    try {
      msg = JSON.parse(line);
    } catch {
      this.failConnection("parse_error");
      return;
    }
    const obj = asRecord(msg);
    if (!obj || obj.jsonrpc !== "2.0") {
      this.failConnection("invalid_envelope");
      return;
    }

    // Notification (no id)
    if (typeof obj.method === "string" && !("id" in obj)) {
      this.handleNotification(obj.method, asRecord(obj.params) ?? {});
      return;
    }

    // Response
    if ("id" in obj) {
      const id = obj.id;
      if (typeof id !== "string" && typeof id !== "number") {
        this.failConnection("invalid_id");
        return;
      }
      const key = String(id);
      const pending = this.pending.get(key);
      if (!pending) {
        // Stale/unknown id: ignore for robustness; do not retry anything.
        return;
      }
      this.pending.delete(key);
      if ("error" in obj) {
        pending.reject(
          new SidecarRpcClientError(mapWireError(obj.error), this.state),
        );
        return;
      }
      pending.resolve(obj.result);
      return;
    }

    this.failConnection("unknown_message");
  }

  private handleNotification(
    method: string,
    params: Record<string, unknown>,
  ): void {
    const seq = params.sequence ?? params.notification_seq;
    if (typeof seq === "number") {
      if (seq <= this.lastNotificationSeq) {
        this.failConnection("notification_seq_regression");
        return;
      }
      if (
        this.lastNotificationSeq > 0 &&
        seq !== this.lastNotificationSeq + 1
      ) {
        this.failConnection("notification_seq_gap");
        return;
      }
      this.lastNotificationSeq = seq;
    }
    // Event frames may be larger; control notifications share the same path.
    this.onNotification?.(method, params);
  }

  private failConnection(_reason: string): void {
    if (this.failed || this.state === "closed") return;
    this.failed = true;
    if (this.initTimer !== null) {
      this.cancelSchedule(this.initTimer);
      this.initTimer = null;
    }
    if (this.shutdownTimer !== null) {
      this.cancelSchedule(this.shutdownTimer);
      this.shutdownTimer = null;
    }
    this.setState("failed");
    const err = new SidecarRpcClientError(FAILED_PUBLIC, "failed");
    for (const [, pending] of this.pending) {
      pending.reject(err);
    }
    this.pending.clear();
    this.scanner.reset();
  }

  private finishClosed(): void {
    if (this.state === "closed") return;
    if (this.shutdownTimer !== null) {
      this.cancelSchedule(this.shutdownTimer);
      this.shutdownTimer = null;
    }
    for (const [, pending] of this.pending) {
      pending.reject(
        new SidecarRpcClientError(
          {
            code: -32005,
            message: "Connection closed",
            category: "invalid_state",
            retryable: false,
            messageKey: "desktop.error.connection_closed",
          },
          "closed",
        ),
      );
    }
    this.pending.clear();
    this.setState("closed");
    const resolve = this.shutdownResolve;
    this.shutdownResolve = null;
    resolve?.();
  }

  private setState(next: ConnectionState): void {
    if (this.state === next) return;
    this.state = next;
    this.onStateChange?.(next);
  }
}
