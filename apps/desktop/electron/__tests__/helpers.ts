/**
 * Electron IPC / window / child-process / native-dialog test doubles (078 T012).
 */

export const TRUSTED_RENDERER_ID = 1;
export const TRUSTED_RENDERER_URL = "file:///app/dist/index.html";
export const TRUSTED_HANDLER_OPTIONS = {
  expectedSenderId: TRUSTED_RENDERER_ID,
  expectedSenderUrl: TRUSTED_RENDERER_URL,
} as const;

export const DESKTOP_RPC_METHODS = [
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

export function desktopInitializeResult() {
  return {
    protocol: { name: "loopplane.desktop.stdio", major: 1, minor: 0 },
    runtime_event_schema: 1,
    server: { name: "loopplane-desktop-sidecar", version: "0.4.0" },
    methods: [...DESKTOP_RPC_METHODS],
    notifications: [
      "runtime.event",
      "runtime.outcome",
      "runtime.state",
      "runtime.subscriptionClosed",
    ],
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
  };
}

export type FrameDouble = { url: string };

export type IpcSender = {
  id: number;
  url: string;
  isDestroyed: () => boolean;
  sender: {
    id: number;
    getURL: () => string;
    isDestroyed: () => boolean;
    mainFrame: FrameDouble;
  };
  senderFrame: FrameDouble;
};

export type WebContentsDouble = {
  id: number;
  getURL: () => string;
  isDestroyed: () => boolean;
  mainFrame: FrameDouble;
  send: (channel: string, ...args: unknown[]) => void;
  sent: Array<{ channel: string; args: unknown[] }>;
};

export function createWebContentsDouble(
  opts: { id?: number; url?: string; destroyed?: boolean } = {},
): WebContentsDouble {
  const sent: Array<{ channel: string; args: unknown[] }> = [];
  let destroyed = opts.destroyed ?? false;
  const url = opts.url ?? TRUSTED_RENDERER_URL;
  const mainFrame = { url };
  return {
    id: opts.id ?? TRUSTED_RENDERER_ID,
    getURL: () => url,
    isDestroyed: () => destroyed,
    mainFrame,
    send(channel: string, ...args: unknown[]) {
      if (destroyed) throw new Error("webContents destroyed");
      sent.push({ channel, args });
    },
    sent,
  };
}

export function createIpcSenderFrom(
  contents: WebContentsDouble,
): IpcSender {
  return {
    id: contents.id,
    url: contents.getURL(),
    isDestroyed: () => contents.isDestroyed(),
    sender: {
      id: contents.id,
      getURL: () => contents.getURL(),
      isDestroyed: () => contents.isDestroyed(),
      mainFrame: contents.mainFrame,
    },
    senderFrame: contents.mainFrame,
  };
}

export type ChildProcessDouble = {
  pid: number;
  killed: boolean;
  stdin: { write: (data: string | Buffer) => boolean; end: () => void };
  stdout: { on: (event: string, cb: (chunk: Buffer) => void) => void };
  stderr: { on: (event: string, cb: (chunk: Buffer) => void) => void };
  on: (event: string, cb: (...args: unknown[]) => void) => void;
  kill: (signal?: string) => void;
  /** Test controls */
  emitStdout: (line: string) => void;
  emitExit: (code: number | null, signal?: string | null) => void;
  emitError: (err: Error) => void;
  written: string[];
};

export function createChildProcessDouble(pid = 4242): ChildProcessDouble {
  const written: string[] = [];
  const handlers = new Map<string, Array<(...args: unknown[]) => void>>();
  const stdoutHandlers: Array<(chunk: Buffer) => void> = [];
  const stderrHandlers: Array<(chunk: Buffer) => void> = [];

  const on = (event: string, cb: (...args: unknown[]) => void) => {
    const list = handlers.get(event) ?? [];
    list.push(cb);
    handlers.set(event, list);
  };

  const emit = (event: string, ...args: unknown[]) => {
    for (const cb of handlers.get(event) ?? []) cb(...args);
  };

  return {
    pid,
    killed: false,
    written,
    stdin: {
      write(data: string | Buffer) {
        written.push(typeof data === "string" ? data : data.toString("utf8"));
        return true;
      },
      end() {
        /* no-op */
      },
    },
    stdout: {
      on(event: string, cb: (chunk: Buffer) => void) {
        if (event === "data") stdoutHandlers.push(cb);
      },
    },
    stderr: {
      on(event: string, cb: (chunk: Buffer) => void) {
        if (event === "data") stderrHandlers.push(cb);
      },
    },
    on,
    kill(signal?: string) {
      this.killed = true;
      emit("exit", null, signal ?? "SIGTERM");
    },
    emitStdout(line: string) {
      const chunk = Buffer.from(line.endsWith("\n") ? line : `${line}\n`, "utf8");
      for (const cb of stdoutHandlers) cb(chunk);
    },
    emitExit(code: number | null, signal: string | null = null) {
      emit("exit", code, signal);
    },
    emitError(err: Error) {
      emit("error", err);
    },
  };
}

export type NativeDialogDouble = {
  showOpenDialog: (options: unknown) => Promise<{ canceled: boolean; filePaths: string[] }>;
  showSaveDialog: (options: unknown) => Promise<{ canceled: boolean; filePath?: string }>;
  showMessageBox: (options: unknown) => Promise<{ response: number }>;
  lastOpenOptions: unknown;
  lastSaveOptions: unknown;
  nextOpen: { canceled: boolean; filePaths: string[] };
  nextSave: { canceled: boolean; filePath?: string };
};

export function createNativeDialogDouble(): NativeDialogDouble {
  const d: NativeDialogDouble = {
    lastOpenOptions: undefined,
    lastSaveOptions: undefined,
    nextOpen: { canceled: true, filePaths: [] },
    nextSave: { canceled: true },
    async showOpenDialog(options: unknown) {
      d.lastOpenOptions = options;
      return { ...d.nextOpen };
    },
    async showSaveDialog(options: unknown) {
      d.lastSaveOptions = options;
      return { ...d.nextSave };
    },
    async showMessageBox() {
      return { response: 0 };
    },
  };
  return d;
}

export type BrowserWindowDouble = {
  webContents: WebContentsDouble;
  loadFile: (path: string) => Promise<void>;
  loadURL: (url: string) => Promise<void>;
  on: (event: string, cb: (...args: unknown[]) => void) => void;
  close: () => void;
  isDestroyed: () => boolean;
  loaded: string[];
};

export function createBrowserWindowDouble(): BrowserWindowDouble {
  const webContents = createWebContentsDouble();
  const handlers = new Map<string, Array<(...args: unknown[]) => void>>();
  let destroyed = false;
  const loaded: string[] = [];
  return {
    webContents,
    loaded,
    async loadFile(path: string) {
      loaded.push(path);
    },
    async loadURL(url: string) {
      loaded.push(url);
    },
    on(event: string, cb: (...args: unknown[]) => void) {
      const list = handlers.get(event) ?? [];
      list.push(cb);
      handlers.set(event, list);
    },
    close() {
      destroyed = true;
      for (const cb of handlers.get("closed") ?? []) cb();
    },
    isDestroyed: () => destroyed,
  };
}
