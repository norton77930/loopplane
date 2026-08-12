/**
 * Electron-main sidecar JSON-RPC supervisor (078 T027).
 *
 * Owns child stdio: byte-oriented LF framing, initialize handshake, pending
 * request map, notification routing, crash/EOF fail-closed, graceful drain +
 * forced kill. Never retries mutations after process failure. Pure Node module
 * (no `electron` import) so unit tests inject a child-process double.
 */

import { randomUUID } from "node:crypto";
import { TextDecoder } from "node:util";

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
  protocol: { name: string; major: number; minor: number };
  runtimeEventSchema: number;
  server: { name: string; version: string };
  methods: string[];
  notifications: string[];
  capabilities: Record<string, "available" | "unavailable">;
  limits: Record<string, number>;
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
const PROTOCOL_MAJOR = 1;
const PROTOCOL_MINOR = 0;
const RUNTIME_EVENT_SCHEMA = 1;
const REQUESTED_CAPABILITIES = [
  "sessions",
  "interaction",
  "projects",
  "inspection",
  "workspace",
  "backup",
] as const;
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
] as const;
const REQUIRED_NOTIFICATIONS = [
  "runtime.event",
  "runtime.outcome",
  "runtime.state",
  "runtime.subscriptionClosed",
] as const;
type RuntimeNotification = (typeof REQUIRED_NOTIFICATIONS)[number];
const RUNTIME_NOTIFICATIONS = new Set<string>(REQUIRED_NOTIFICATIONS);
const RUNTIME_STATES = new Set([
  "opened",
  "waiting",
  "cancelling",
  "draining",
]);
const RUN_OUTCOME_REASONS = new Set([
  "natural-completion",
  "turn-budget-exhausted",
  "cancelled",
  "unrecoverable-error",
  "budget-exceeded",
]);
const PUBLIC_CLOSE_REASONS = new Set([
  "completed",
  "cancelled",
  "released",
  "failed",
  "shutdown",
]);
const REQUIRED_LIMITS = {
  control_frame_bytes: 1_048_576,
  runtime_event_frame_bytes: 8_388_608,
  prompt_bytes: 65_536,
  pending_requests: 64,
  subscriptions: 8,
} as const;

const DEFAULT_INIT_MS = 5_000;
const DEFAULT_SHUTDOWN_MS = 5_000;
const DEFAULT_CONTROL_FRAME = 1_048_576;
const DEFAULT_EVENT_FRAME = 8_388_608;
const DEFAULT_MAX_PENDING = 64;
const MAX_JSON_DEPTH = 32;
const MAX_JSON_KEYS = 128;
const RUNTIME_EVENT_FRAME_PREFIX = Buffer.from(
  '{"jsonrpc":"2.0","method":"runtime.event","params":{',
  "utf8",
);

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

function exactStringArray(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    return null;
  }
  const strings = value as string[];
  return new Set(strings).size === strings.length ? strings : null;
}

function hasExactMembers(actual: string[], expected: readonly string[]): boolean {
  return (
    actual.length === expected.length &&
    expected.every((item) => actual.includes(item))
  );
}

function exactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => key in value) &&
    Object.keys(value).every((key) => allowed.has(key))
  );
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isRuntimeEventFrame(frame: Buffer): boolean {
  // The sidecar owns serialization and emits this exact deterministic prefix.
  // Unknown or reordered shapes remain control frames and fail at 1 MiB.
  return frame
    .subarray(0, RUNTIME_EVENT_FRAME_PREFIX.length)
    .equals(RUNTIME_EVENT_FRAME_PREFIX);
}

function parseStrictJson(text: string): unknown {
  let index = 0;

  const fail = (): never => {
    throw new SyntaxError("invalid strict JSON");
  };
  const skipWhitespace = (): void => {
    while (
      index < text.length &&
      (text[index] === " " ||
        text[index] === "\t" ||
        text[index] === "\r" ||
        text[index] === "\n")
    ) {
      index += 1;
    }
  };
  const readHex4 = (): number => {
    const raw = text.slice(index, index + 4);
    if (!/^[0-9a-fA-F]{4}$/.test(raw)) fail();
    index += 4;
    return Number.parseInt(raw, 16);
  };
  const readString = (): string => {
    if (text[index] !== '"') fail();
    index += 1;
    let value = "";
    while (index < text.length) {
      const char = text[index]!;
      index += 1;
      if (char === '"') return value;
      if (char.charCodeAt(0) < 0x20) fail();
      if (char !== "\\") {
        const code = char.charCodeAt(0);
        if (code >= 0xd800 && code <= 0xdbff) {
          const low = text.charCodeAt(index);
          if (low < 0xdc00 || low > 0xdfff) fail();
          value += char + text[index]!;
          index += 1;
          continue;
        }
        if (code >= 0xdc00 && code <= 0xdfff) fail();
        value += char;
        continue;
      }

      const escape = text[index];
      index += 1;
      if (escape === undefined) fail();
      const escaped = ({
        '"': '"',
        "\\": "\\",
        "/": "/",
        b: "\b",
        f: "\f",
        n: "\n",
        r: "\r",
        t: "\t",
      } as Record<string, string>)[escape];
      if (escaped !== undefined) {
        value += escaped;
        continue;
      }
      if (escape !== "u") fail();
      const code = readHex4();
      if (code >= 0xdc00 && code <= 0xdfff) fail();
      if (code >= 0xd800 && code <= 0xdbff) {
        if (text.slice(index, index + 2) !== "\\u") fail();
        index += 2;
        const low = readHex4();
        if (low < 0xdc00 || low > 0xdfff) fail();
        value += String.fromCodePoint(
          0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00),
        );
        continue;
      }
      value += String.fromCharCode(code);
    }
    return fail();
  };
  const readNumber = (): number => {
    const remaining = text.slice(index);
    const match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(remaining);
    if (match === null) return fail();
    index += match[0].length;
    const value = Number(match[0]);
    if (!Number.isFinite(value)) fail();
    return value;
  };
  const readValue = (depth: number): unknown => {
    if (depth > MAX_JSON_DEPTH) fail();
    skipWhitespace();
    const char = text[index];
    if (char === '"') return readString();
    if (char === "{") return readObject(depth);
    if (char === "[") return readArray(depth);
    if (text.startsWith("true", index)) {
      index += 4;
      return true;
    }
    if (text.startsWith("false", index)) {
      index += 5;
      return false;
    }
    if (text.startsWith("null", index)) {
      index += 4;
      return null;
    }
    return readNumber();
  };
  const readArray = (depth: number): unknown[] => {
    index += 1;
    const values: unknown[] = [];
    skipWhitespace();
    if (text[index] === "]") {
      index += 1;
      return values;
    }
    for (;;) {
      values.push(readValue(depth + 1));
      skipWhitespace();
      if (text[index] === "]") {
        index += 1;
        return values;
      }
      if (text[index] !== ",") fail();
      index += 1;
    }
  };
  const readObject = (depth: number): Record<string, unknown> => {
    index += 1;
    const value = Object.create(null) as Record<string, unknown>;
    const keys = new Set<string>();
    skipWhitespace();
    if (text[index] === "}") {
      index += 1;
      return value;
    }
    for (;;) {
      skipWhitespace();
      const key = readString();
      if (keys.has(key) || keys.size >= MAX_JSON_KEYS) fail();
      keys.add(key);
      skipWhitespace();
      if (text[index] !== ":") fail();
      index += 1;
      value[key] = readValue(depth + 1);
      skipWhitespace();
      if (text[index] === "}") {
        index += 1;
        return value;
      }
      if (text[index] !== ",") fail();
      index += 1;
    }
  };

  const value = readValue(0);
  skipWhitespace();
  if (index !== text.length) fail();
  return value;
}

function incompatibleRuntime(state: ConnectionState): SidecarRpcClientError {
  return new SidecarRpcClientError(
    {
      code: -32001,
      message: "Incompatible runtime",
      category: "incompatible_protocol",
      retryable: false,
      recovery: "contact_support",
      messageKey: "desktop.error.incompatible_runtime",
    },
    state,
  );
}

function parseInitializeResult(
  value: unknown,
  state: ConnectionState,
): InitializeResult {
  const record = asRecord(value);
  const protocol = asRecord(record?.protocol);
  const server = asRecord(record?.server);
  const capabilities = asRecord(record?.capabilities);
  const limits = asRecord(record?.limits);
  const methods = exactStringArray(record?.methods);
  const notifications = exactStringArray(record?.notifications);

  if (
    !record ||
    !protocol ||
    protocol.name !== PROTOCOL_NAME ||
    protocol.major !== PROTOCOL_MAJOR ||
    protocol.minor !== PROTOCOL_MINOR ||
    record.runtime_event_schema !== RUNTIME_EVENT_SCHEMA ||
    !server ||
    server.name !== "loopplane-desktop-sidecar" ||
    typeof server.version !== "string" ||
    !server.version.trim() ||
    !methods ||
    !hasExactMembers(methods, REQUIRED_METHODS) ||
    !notifications ||
    !hasExactMembers(notifications, REQUIRED_NOTIFICATIONS) ||
    !capabilities ||
    !limits
  ) {
    throw incompatibleRuntime(state);
  }

  const parsedCapabilities: Record<string, "available" | "unavailable"> = {};
  for (const name of REQUESTED_CAPABILITIES) {
    const status = capabilities[name];
    if (status !== "available" && status !== "unavailable") {
      throw incompatibleRuntime(state);
    }
    parsedCapabilities[name] = status;
  }
  if (Object.keys(capabilities).length !== REQUESTED_CAPABILITIES.length) {
    throw incompatibleRuntime(state);
  }

  const parsedLimits: Record<string, number> = {};
  for (const [name, expected] of Object.entries(REQUIRED_LIMITS)) {
    if (limits[name] !== expected) {
      throw incompatibleRuntime(state);
    }
    parsedLimits[name] = expected;
  }
  if (Object.keys(limits).length !== Object.keys(REQUIRED_LIMITS).length) {
    throw incompatibleRuntime(state);
  }

  return {
    protocol: {
      name: PROTOCOL_NAME,
      major: PROTOCOL_MAJOR,
      minor: PROTOCOL_MINOR,
    },
    runtimeEventSchema: RUNTIME_EVENT_SCHEMA,
    server: {
      name: "loopplane-desktop-sidecar",
      version: server.version,
    },
    methods,
    notifications,
    capabilities: parsedCapabilities,
    limits: parsedLimits,
    raw: record,
  };
}

const WIRE_ERROR_ROWS: readonly PublicRpcError[] = [
  FAILED_PUBLIC,
  {
    code: -32700,
    message: "Parse error",
    category: "parse_error",
    retryable: false,
    messageKey: "desktop.error.parse_error",
  },
  {
    code: -32600,
    message: "Invalid request",
    category: "invalid_request",
    retryable: false,
    messageKey: "desktop.error.invalid_request",
  },
  {
    code: -32601,
    message: "Method not found",
    category: "method_not_found",
    retryable: false,
    messageKey: "desktop.error.method_not_found",
  },
  {
    code: -32602,
    message: "Invalid params",
    category: "invalid_params",
    retryable: false,
    messageKey: "desktop.error.invalid_params",
  },
  {
    code: -32005,
    message: "Shutting down",
    category: "invalid_state",
    retryable: false,
    messageKey: "desktop.error.shutting_down",
  },
  {
    code: -32005,
    message: "Not initialized",
    category: "invalid_state",
    retryable: false,
    messageKey: "desktop.error.not_initialized",
  },
  {
    code: -32001,
    message: "Incompatible protocol",
    category: "incompatible_protocol",
    retryable: false,
    recovery: "contact_support",
    messageKey: "desktop.error.incompatible_runtime",
  },
  {
    code: -32001,
    message: "Incompatible backup",
    category: "incompatible_protocol",
    retryable: false,
    recovery: "contact_support",
    messageKey: "backup.error.incompatible",
  },
  {
    code: -32002,
    message: "Not found",
    category: "not_found",
    retryable: false,
    messageKey: "desktop.error.not_found",
  },
  BUSY_PUBLIC,
  {
    code: -32004,
    message: "Busy",
    category: "busy",
    retryable: true,
    recovery: "wait",
    messageKey: "backup.error.profile_busy",
  },
  STATE_PUBLIC,
  {
    code: -32005,
    message: "Already initialized",
    category: "invalid_state",
    retryable: false,
    messageKey: "desktop.error.already_initialized",
  },
  {
    code: -32006,
    message: "Workspace relink required",
    category: "workspace_relink_required",
    retryable: false,
    recovery: "relink_workspace",
    messageKey: "desktop.error.workspace_relink_required",
  },
  {
    code: -32007,
    message: "Unsafe input",
    category: "unsafe_input",
    retryable: false,
    messageKey: "backup.error.unsafe_archive",
  },
  {
    code: -32007,
    message: "Unsafe input",
    category: "unsafe_input",
    retryable: false,
    messageKey: "backup.error.integrity_failed",
  },
  {
    code: -32007,
    message: "Unsafe input",
    category: "unsafe_input",
    retryable: false,
    messageKey: "backup.error.limit_exceeded",
  },
  {
    code: -32008,
    message: "Unavailable",
    category: "unavailable",
    retryable: false,
    messageKey: "desktop.error.unavailable",
  },
  {
    code: -32008,
    message: "Unavailable",
    category: "unavailable",
    retryable: true,
    recovery: "retry",
    messageKey: "backup.error.insufficient_space",
  },
  {
    code: -32009,
    message: "Cancelled",
    category: "cancelled",
    retryable: false,
    messageKey: "backup.error.cancelled",
  },
  {
    code: -32011,
    message: "Durability unsupported",
    category: "durability_unsupported",
    retryable: false,
    recovery: "contact_support",
    messageKey: "restore.error.durability_unsupported",
  },
  {
    code: -32012,
    message: "Publication failed",
    category: "publication_failed",
    retryable: true,
    recovery: "retry",
    messageKey: "restore.error.publication_failed_retryable",
  },
  {
    code: -32012,
    message: "Publication failed",
    category: "publication_failed",
    retryable: false,
    recovery: "restart_runtime",
    messageKey: "restore.error.publication_failed_restart",
  },
  {
    code: -32012,
    message: "Publication failed",
    category: "publication_failed",
    retryable: true,
    recovery: "retry",
    messageKey: "restore.error.rolled_back",
  },
];

function mapWireError(error: unknown): PublicRpcError {
  const obj = asRecord(error);
  const data = asRecord(obj?.data);
  const messageKey =
    typeof data?.messageKey === "string"
      ? data.messageKey
      : typeof data?.message_key === "string"
        ? data.message_key
        : undefined;
  if (!obj || !data || typeof obj.code !== "number" || !messageKey) {
    return { ...FAILED_PUBLIC };
  }

  const recovery =
    typeof data.recovery === "string" ? data.recovery : undefined;
  const match = WIRE_ERROR_ROWS.find(
    (row) =>
      row.code === obj.code &&
      row.category === data.category &&
      row.retryable === data.retryable &&
      row.recovery === recovery &&
      row.messageKey === messageKey,
  );
  return match ? { ...match } : { ...FAILED_PUBLIC };
}

/**
 * Byte-oriented LF frame scanner. Counts bytes before UTF-8 decode so split
 * multi-byte sequences and oversize frames fail closed without partial dispatch.
 */
export class ByteLineScanner {
  private buffer = Buffer.alloc(0);
  private readonly maxControlFrameBytes: number;
  private readonly maxEventFrameBytes: number;
  private readonly onFrame: (utf8: string, byteLength: number) => void;
  private readonly onOverflow: () => void;

  constructor(
    maxControlFrameBytes: number,
    maxEventFrameBytesOrOnFrame:
      | number
      | ((utf8: string, byteLength: number) => void),
    onFrameOrOverflow:
      | ((utf8: string, byteLength: number) => void)
      | (() => void),
    onOverflow?: () => void,
  ) {
    this.maxControlFrameBytes = maxControlFrameBytes;
    if (typeof maxEventFrameBytesOrOnFrame === "number") {
      this.maxEventFrameBytes = maxEventFrameBytesOrOnFrame;
      this.onFrame = onFrameOrOverflow as (
        utf8: string,
        byteLength: number,
      ) => void;
      this.onOverflow = onOverflow ?? (() => undefined);
      return;
    }
    this.maxEventFrameBytes = maxControlFrameBytes;
    this.onFrame = maxEventFrameBytesOrOnFrame;
    this.onOverflow = onFrameOrOverflow as () => void;
  }

  push(chunk: Buffer): void {
    if (chunk.length === 0) return;
    this.buffer = Buffer.concat([this.buffer, chunk]);
    for (;;) {
      const nl = this.buffer.indexOf(0x0a);
      if (nl < 0) {
        if (
          this.buffer.length > this.maxControlFrameBytes &&
          (!isRuntimeEventFrame(this.buffer) ||
            this.buffer.length > this.maxEventFrameBytes)
        ) {
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
      const frameLimit = isRuntimeEventFrame(frame)
        ? this.maxEventFrameBytes
        : this.maxControlFrameBytes;
      if (frame.length > frameLimit) {
        this.onOverflow();
        return;
      }
      if (frame.length === 0) {
        this.onOverflow();
        return;
      }
      let text: string;
      try {
        text = new TextDecoder("utf-8", { fatal: true }).decode(frame);
      } catch {
        this.onOverflow();
        return;
      }
      this.onFrame(text, frame.length);
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
  private readonly subscriptionPhases = new Map<
    string,
    "events" | "outcome" | "closed"
  >();
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

    // Count to the larger event bound before decode. The callback receives the
    // original byte length so oversized control-shaped frames fail before parse.
    this.scanner = new ByteLineScanner(
      this.maxControlFrameBytes,
      this.maxEventFrameBytes,
      (line, byteLength) => this.onStdoutLine(line, byteLength),
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
        protocol: {
          name: PROTOCOL_NAME,
          major: PROTOCOL_MAJOR,
          minor: PROTOCOL_MINOR,
        },
        runtime_event_schema: RUNTIME_EVENT_SCHEMA,
        client: { name: this.clientName, version: this.clientVersion },
        requested_capabilities: [...REQUESTED_CAPABILITIES],
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
      let initialized: InitializeResult;
      try {
        initialized = parseInitializeResult(result, this.state);
      } catch (error) {
        this.failConnection("protocol_incompatible");
        if (error instanceof SidecarRpcClientError) throw error;
        throw incompatibleRuntime(this.state);
      }
      this.setState("ready");
      return initialized;
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
      if (pending.method === "system.shutdown") {
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

  private onStdoutLine(line: string, byteLength: number): void {
    if (this.failed || this.state === "closed") return;
    let msg: unknown;
    try {
      msg = parseStrictJson(line);
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
      if (!exactKeys(obj, ["jsonrpc", "method", "params"])) {
        this.failConnection("invalid_notification_envelope");
        return;
      }
      if (!RUNTIME_NOTIFICATIONS.has(obj.method)) {
        this.failConnection("notification_method_unknown");
        return;
      }
      const method = obj.method as RuntimeNotification;
      const params = asRecord(obj.params);
      if (!params) {
        this.failConnection("notification_params_invalid");
        return;
      }
      const expectedFrameLimit =
        method === "runtime.event"
          ? this.maxEventFrameBytes
          : this.maxControlFrameBytes;
      if (byteLength > expectedFrameLimit) {
        this.failConnection("notification_frame_overflow");
        return;
      }
      this.handleNotification(method, params);
      return;
    }

    // Response
    if ("id" in obj) {
      if (byteLength > this.maxControlFrameBytes) {
        this.failConnection("control_frame_overflow");
        return;
      }
      const id = obj.id;
      if (typeof id !== "string") {
        this.failConnection("invalid_id");
        return;
      }
      const hasResult = "result" in obj;
      const hasError = "error" in obj;
      const responseKeys = hasError
        ? ["jsonrpc", "id", "error"]
        : ["jsonrpc", "id", "result"];
      if (
        hasResult === hasError ||
        !exactKeys(obj, responseKeys)
      ) {
        this.failConnection("invalid_response_envelope");
        return;
      }
      const key = String(id);
      const pending = this.pending.get(key);
      if (!pending) {
        // Stale/unknown id: ignore for robustness; do not retry anything.
        return;
      }
      this.pending.delete(key);
      if (hasError) {
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
    method: RuntimeNotification,
    params: Record<string, unknown>,
  ): void {
    const rawSeq = params.notification_seq;
    if (!Number.isInteger(rawSeq) || (rawSeq as number) < 1) {
      this.failConnection("notification_seq_missing");
      return;
    }
    const seq = rawSeq as number;
    if (seq !== this.lastNotificationSeq + 1) {
      this.failConnection(
        seq <= this.lastNotificationSeq
          ? "notification_seq_regression"
          : "notification_seq_gap",
      );
      return;
    }
    if (!this.validateNotification(method, params)) {
      this.failConnection("notification_payload_invalid");
      return;
    }
    this.lastNotificationSeq = seq;
    this.onNotification?.(method, params);
  }

  private validateNotification(
    method: RuntimeNotification,
    params: Record<string, unknown>,
  ): boolean {
    if (method === "runtime.state") {
      return (
        exactKeys(params, ["notification_seq", "state"]) &&
        typeof params.state === "string" &&
        RUNTIME_STATES.has(params.state)
      );
    }

    if (!nonEmptyString(params.subscription_id)) return false;
    const subscriptionId = params.subscription_id;
    if (!nonEmptyString(params.session_id)) return false;
    const phase = this.subscriptionPhases.get(subscriptionId) ?? "events";
    if (phase === "closed") return false;

    if (method === "runtime.event") {
      if (phase !== "events") return false;
      return (
        exactKeys(
          params,
          ["notification_seq", "subscription_id", "session_id", "event"],
          ["run_id"],
        ) &&
        asRecord(params.event) !== null &&
        (params.run_id === undefined ||
          params.run_id === null ||
          nonEmptyString(params.run_id))
      );
    }

    if (method === "runtime.outcome") {
      if (phase !== "events") return false;
      const valid =
        exactKeys(
          params,
          [
            "notification_seq",
            "subscription_id",
            "session_id",
            "reason",
            "turns",
          ],
          ["run_id"],
        ) &&
        typeof params.reason === "string" &&
        RUN_OUTCOME_REASONS.has(params.reason) &&
        Number.isInteger(params.turns) &&
        (params.turns as number) >= 0 &&
        (params.run_id === undefined ||
          params.run_id === null ||
          nonEmptyString(params.run_id));
      if (valid) this.subscriptionPhases.set(subscriptionId, "outcome");
      return valid;
    }

    const valid =
      (phase === "outcome" ||
        (phase === "events" &&
          (params.reason === "released" || params.reason === "shutdown"))) &&
      exactKeys(params, [
        "notification_seq",
        "subscription_id",
        "session_id",
        "reason",
        "history_readable",
      ]) &&
      typeof params.reason === "string" &&
      PUBLIC_CLOSE_REASONS.has(params.reason) &&
      typeof params.history_readable === "boolean";
    if (valid) this.subscriptionPhases.set(subscriptionId, "closed");
    return valid;
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
