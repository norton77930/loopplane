/**
 * Electron IPC / window / child-process / native-dialog test doubles (078 T012).
 */

export type IpcSender = {
  id: number;
  url: string;
  isDestroyed: () => boolean;
};

export type WebContentsDouble = {
  id: number;
  getURL: () => string;
  isDestroyed: () => boolean;
  send: (channel: string, ...args: unknown[]) => void;
  sent: Array<{ channel: string; args: unknown[] }>;
};

export function createWebContentsDouble(
  opts: { id?: number; url?: string; destroyed?: boolean } = {},
): WebContentsDouble {
  const sent: Array<{ channel: string; args: unknown[] }> = [];
  let destroyed = opts.destroyed ?? false;
  return {
    id: opts.id ?? 1,
    getURL: () => opts.url ?? "file:///app/dist/index.html",
    isDestroyed: () => destroyed,
    send(channel: string, ...args: unknown[]) {
      if (destroyed) throw new Error("webContents destroyed");
      sent.push({ channel, args });
    },
    sent,
  };
}

export function createIpcSenderFrom(
  contents: WebContentsDouble,
): IpcSender & { senderFrame?: { url: string } } {
  return {
    id: contents.id,
    url: contents.getURL(),
    isDestroyed: () => contents.isDestroyed(),
    senderFrame: { url: contents.getURL() },
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
