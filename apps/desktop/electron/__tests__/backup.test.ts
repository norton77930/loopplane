/**
 * Electron backup/restore IPC, native chooser, and error contracts (078 T071).
 */

import { describe, expect, it, vi } from "vitest";

import {
  createChildProcessDouble,
  createIpcSenderFrom,
  createWebContentsDouble,
  TRUSTED_HANDLER_OPTIONS,
} from "./helpers";
import { unwrapBackupRestoreEnvelope } from "../backup-restore-ipc";
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
          "backup.describe",
          "backup.create",
          "restore.validate",
          "restore.commit",
          "restore.cancel",
        ],
        capabilities: {},
      },
    }),
  );
  await startP;
  return rpc;
}

function ipcMap() {
  type Handler = (
    event: IpcEventLike,
    ...args: unknown[]
  ) => unknown | Promise<unknown>;
  const handlers = new Map<string, Handler>();
  const rawHandlers = new Map<string, Handler>();
  const backupChannels = new Set<string>([
    IPC.backupDescribe,
    IPC.backupCreate,
    IPC.restoreValidate,
    IPC.restoreCommit,
    IPC.restoreCancel,
  ]);
  return {
    handlers,
    rawHandlers,
    ipcMain: {
      handle(channel: string, listener: Handler) {
        rawHandlers.set(channel, listener);
        handlers.set(channel, async (event, ...args) => {
          const value = await listener(event, ...args);
          if (!backupChannels.has(channel)) return value;
          return unwrapBackupRestoreEnvelope(structuredClone(value));
        });
      },
      removeHandler(channel: string) {
        handlers.delete(channel);
        rawHandlers.delete(channel);
      },
    },
  };
}

function trustedSender(): IpcEventLike {
  return createIpcSenderFrom(
    createWebContentsDouble({ url: "file:///app/dist/index.html" }),
  );
}

type ChooserRegistration = Omit<
  Parameters<typeof registerDesktopIpcHandlers>[0],
  "expectedSenderId" | "expectedSenderUrl"
> & {
  expectedSenderId?: number;
  expectedSenderUrl?: string;
  chooseBackupDestination?: () => Promise<string | null>;
  chooseRestoreSource?: () => Promise<string | null>;
};

function registerWithChoosers(options: ChooserRegistration): void {
  registerDesktopIpcHandlers({ ...TRUSTED_HANDLER_OPTIONS, ...options });
}

function latestRequest(child: ReturnType<typeof createChildProcessDouble>) {
  return JSON.parse(child.written[child.written.length - 1]!.trim()) as {
    id: string;
    method: string;
    params: Record<string, unknown>;
  };
}

async function rejectedError(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    return error as Error & {
      desktop: {
        category: string;
        messageKey: string;
        retryable: boolean;
        recovery?: string;
      };
    };
  }
  throw new Error("expected rejection");
}

type ErrorRow = {
  name: string;
  wire: {
    code: number;
    category: string;
    retryable: boolean;
    recovery?: string;
    messageKey: string;
  };
  desktop: {
    category: string;
    retryable: boolean;
    recovery?: string;
    messageKey: string;
  };
};

const ERROR_ROWS: ErrorRow[] = [
  {
    name: "unsafe archive",
    wire: {
      code: -32007,
      category: "unsafe_input",
      retryable: false,
      messageKey: "backup.error.unsafe_archive",
    },
    desktop: {
      category: "unsafe_input",
      retryable: false,
      messageKey: "backup.error.unsafe_archive",
    },
  },
  {
    name: "incompatible backup",
    wire: {
      code: -32001,
      category: "incompatible_protocol",
      retryable: false,
      recovery: "contact_support",
      messageKey: "backup.error.incompatible",
    },
    desktop: {
      category: "incompatible",
      retryable: false,
      recovery: "contact_support",
      messageKey: "backup.error.incompatible",
    },
  },
  {
    name: "integrity failure",
    wire: {
      code: -32007,
      category: "unsafe_input",
      retryable: false,
      messageKey: "backup.error.integrity_failed",
    },
    desktop: {
      category: "unsafe_input",
      retryable: false,
      messageKey: "backup.error.integrity_failed",
    },
  },
  {
    name: "limit exceeded",
    wire: {
      code: -32007,
      category: "unsafe_input",
      retryable: false,
      messageKey: "backup.error.limit_exceeded",
    },
    desktop: {
      category: "unsafe_input",
      retryable: false,
      messageKey: "backup.error.limit_exceeded",
    },
  },
  {
    name: "profile busy",
    wire: {
      code: -32004,
      category: "busy",
      retryable: true,
      recovery: "wait",
      messageKey: "backup.error.profile_busy",
    },
    desktop: {
      category: "busy",
      retryable: true,
      recovery: "wait",
      messageKey: "backup.error.profile_busy",
    },
  },
  {
    name: "insufficient space",
    wire: {
      code: -32008,
      category: "unavailable",
      retryable: true,
      recovery: "retry",
      messageKey: "backup.error.insufficient_space",
    },
    desktop: {
      category: "unavailable",
      retryable: true,
      recovery: "retry",
      messageKey: "backup.error.insufficient_space",
    },
  },
  {
    name: "durability unsupported",
    wire: {
      code: -32011,
      category: "durability_unsupported",
      retryable: false,
      recovery: "contact_support",
      messageKey: "restore.error.durability_unsupported",
    },
    desktop: {
      category: "durability_unsupported",
      retryable: false,
      recovery: "contact_support",
      messageKey: "restore.error.durability_unsupported",
    },
  },
  {
    name: "retryable publication failure",
    wire: {
      code: -32012,
      category: "publication_failed",
      retryable: true,
      recovery: "retry",
      messageKey: "restore.error.publication_failed_retryable",
    },
    desktop: {
      category: "publication_failed",
      retryable: true,
      recovery: "retry",
      messageKey: "restore.error.publication_failed_retryable",
    },
  },
  {
    name: "restart publication failure",
    wire: {
      code: -32012,
      category: "publication_failed",
      retryable: false,
      recovery: "restart_runtime",
      messageKey: "restore.error.publication_failed_restart",
    },
    desktop: {
      category: "publication_failed",
      retryable: false,
      recovery: "restart_runtime",
      messageKey: "restore.error.publication_failed_restart",
    },
  },
  {
    name: "exact rollback",
    wire: {
      code: -32012,
      category: "publication_failed",
      retryable: true,
      recovery: "retry",
      messageKey: "restore.error.rolled_back",
    },
    desktop: {
      category: "publication_failed",
      retryable: true,
      recovery: "retry",
      messageKey: "restore.error.rolled_back",
    },
  },
  {
    name: "cancelled",
    wire: {
      code: -32009,
      category: "cancelled",
      retryable: false,
      messageKey: "backup.error.cancelled",
    },
    desktop: {
      category: "cancelled",
      retryable: false,
      messageKey: "backup.error.cancelled",
    },
  },
  {
    name: "unknown containment",
    wire: {
      code: -32603,
      category: "internal_failure",
      retryable: true,
      recovery: "restart_runtime",
      messageKey: "desktop.error.internal_failure",
    },
    desktop: {
      category: "internal_failure",
      retryable: true,
      recovery: "restart_runtime",
      messageKey: "desktop.error.internal_failure",
    },
  },
];

const FALLBACK = {
  category: "internal_failure",
  messageKey: "desktop.error.internal_failure",
  retryable: true,
  recovery: "restart_runtime",
};

const VALID_RESTORE_SUMMARY = {
  format: "loopplane.desktop.backup",
  version: { major: 1, minor: 0 },
  created_at: "2026-08-11T00:00:00Z",
  project_count: 1,
  session_count: 1,
  artifact_count: 1,
  drafts_excluded: true,
  relink_required: true,
};

const VALID_BACKUP_DESCRIPTION = {
  disclosure: [
    "This backup is unencrypted (not application-encrypted). ",
    "It preserves authorized conversation history and eligible Gateway artifacts, ",
    "which can contain sensitive user, model, or tool-produced content. ",
    "It excludes unsent drafts, device-private bindings, credentials, private ",
    "configuration, arbitrary workspace contents, and process state.",
  ].join(""),
  includes: [
    "profile_portable_json",
    "projects_and_safe_preferences",
    "session_checkpoints",
    "eligible_referenced_gateway_artifacts",
  ],
  excludes: [
    "unsent_drafts",
    "device_private_bindings",
    "profile_owner_lock",
    "capability_private_config",
    "credentials",
    "workspace_contents",
    "process_state",
  ],
  format: "loopplane.desktop.backup",
  schema_version: 1,
};

describe("backup/restore IPC handlers", () => {
  it("describes backup without a mutation or native path", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
    });
    const resultP = Promise.resolve(
      handlers.get(IPC.backupDescribe)!(trustedSender()),
    );
    await Promise.resolve();
    const request = latestRequest(child);
    expect(request.method).toBe("backup.describe");
    expect(request.params).toEqual({});
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: VALID_BACKUP_DESCRIPTION,
      }),
    );
    await expect(resultP).resolves.toEqual(VALID_BACKUP_DESCRIPTION);
  });

  it.each([
    ["disclosure", { disclosure: "C:\\Users\\person\\private.zip" }],
    ["includes", { includes: ["session_checkpoints", "Traceback: internal"] }],
    ["excludes", { excludes: ["workspace_bindings", "D:\\private\\secret"] }],
  ])(
    "contains malformed backup description %s text with the sole fallback",
    async (_field, override) => {
      const child = createChildProcessDouble();
      const rpc = await readyRpc(child);
      const { handlers, ipcMain } = ipcMap();
      registerDesktopIpcHandlers({
        ...TRUSTED_HANDLER_OPTIONS,
        ipcMain,
        rpc,
      });
      const resultP = Promise.resolve(
        handlers.get(IPC.backupDescribe)!(trustedSender()),
      );
      await Promise.resolve();
      const request = latestRequest(child);
      child.emitStdout(
        JSON.stringify({
          jsonrpc: "2.0",
          id: request.id,
          result: {
            ...VALID_BACKUP_DESCRIPTION,
            ...override,
          },
        }),
      );

      const error = await rejectedError(resultP);
      expect(error.desktop).toEqual(FALLBACK);
    },
  );

  it("requires disclosure before opening the backup destination chooser", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const chooseBackupDestination = vi.fn(async () => "X:\\private\\backup.zip");
    registerWithChoosers({ ipcMain, rpc, chooseBackupDestination });
    const writesBefore = child.written.length;

    await expect(
      handlers.get(IPC.backupCreate)!(trustedSender(), {
        acknowledgement: false,
      }),
    ).rejects.toThrow("desktop.error.invalid_params");
    expect(chooseBackupDestination).not.toHaveBeenCalled();
    expect(child.written).toHaveLength(writesBefore);
  });

  it("rejects renderer-supplied archive authority before opening a chooser", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const chooseBackupDestination = vi.fn(async () => null);
    const chooseRestoreSource = vi.fn(async () => null);
    registerWithChoosers({
      ipcMain,
      rpc,
      chooseBackupDestination,
      chooseRestoreSource,
    });
    const writesBefore = child.written.length;

    await expect(
      handlers.get(IPC.backupCreate)!(trustedSender(), {
        acknowledgement: true,
        destinationPath: "X:\\private\\injected.zip",
      }),
    ).rejects.toThrow("desktop.error.invalid_params");
    await expect(
      handlers.get(IPC.restoreValidate)!(trustedSender(), {
        sourcePath: "X:\\private\\injected.zip",
      }),
    ).rejects.toThrow("desktop.error.invalid_params");
    await expect(
      handlers.get(IPC.restoreValidate)!(trustedSender(), new Date(0)),
    ).rejects.toThrow("desktop.error.invalid_params");
    expect(chooseBackupDestination).not.toHaveBeenCalled();
    expect(chooseRestoreSource).not.toHaveBeenCalled();
    expect(child.written).toHaveLength(writesBefore);
  });

  it("cancels native backup selection without dispatch", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const chooseBackupDestination = vi.fn(async () => null);
    registerWithChoosers({ ipcMain, rpc, chooseBackupDestination });
    const writesBefore = child.written.length;

    await expect(
      handlers.get(IPC.backupCreate)!(trustedSender(), {
        acknowledgement: true,
      }),
    ).resolves.toBeNull();
    expect(chooseBackupDestination).toHaveBeenCalledOnce();
    expect(child.written).toHaveLength(writesBefore);
  });

  it("keeps the chosen backup destination private", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const secretPath = "X:\\private\\backup.zip";
    registerWithChoosers({
      ipcMain,
      rpc,
      chooseBackupDestination: async () => secretPath,
    });
    const writesBefore = child.written.length;
    const resultP = Promise.resolve(
      handlers.get(IPC.backupCreate)!(trustedSender(), {
        acknowledgement: true,
      }),
    );
    void resultP.catch(() => undefined);
    await Promise.resolve();
    expect(child.written).toHaveLength(writesBefore + 1);
    const request = latestRequest(child);
    expect(request.method).toBe("backup.create");
    expect(request.params).toMatchObject({
      acknowledgement: true,
      destination_path: secretPath,
    });
    expect(request.params.mutation_id).toMatch(/^mut-/);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          ok: true,
          finalized: true,
          entry_count: 3,
          format: "loopplane.desktop.backup",
          disclosure_applied: true,
          destination_path: secretPath,
          path: secretPath,
        },
      }),
    );
    const result = await resultP;
    expect(result).toEqual({
      ok: true,
      finalized: true,
      entry_count: 3,
      format: "loopplane.desktop.backup",
      disclosure_applied: true,
    });
    expect(JSON.stringify(result)).not.toContain(secretPath);
  });

  it("cancels native restore selection without dispatch", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const chooseRestoreSource = vi.fn(async () => null);
    registerWithChoosers({ ipcMain, rpc, chooseRestoreSource });
    const writesBefore = child.written.length;

    await expect(
      handlers.get(IPC.restoreValidate)!(trustedSender(), {}),
    ).resolves.toBeNull();
    expect(chooseRestoreSource).toHaveBeenCalledOnce();
    expect(child.written).toHaveLength(writesBefore);
  });

  it("keeps the chosen restore source private and returns only token/preview", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const secretPath = "X:\\private\\restore.zip";
    registerWithChoosers({
      ipcMain,
      rpc,
      chooseRestoreSource: async () => secretPath,
    });
    const writesBefore = child.written.length;
    const resultP = Promise.resolve(
      handlers.get(IPC.restoreValidate)!(trustedSender(), {}),
    );
    void resultP.catch(() => undefined);
    await Promise.resolve();
    expect(child.written).toHaveLength(writesBefore + 1);
    const request = latestRequest(child);
    expect(request.method).toBe("restore.validate");
    expect(request.params.source_path).toBe(secretPath);
    expect(request.params.mutation_id).toMatch(/^mut-/);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          restore_token: "opaque-token",
          summary: {
            ...VALID_RESTORE_SUMMARY,
            entry_count: 3,
            has_manifest: true,
            has_profile: true,
          },
          source_path: secretPath,
          path: secretPath,
        },
      }),
    );
    const result = await resultP;
    expect(result).toEqual({
      restore_token: "opaque-token",
      summary: VALID_RESTORE_SUMMARY,
    });
    expect(JSON.stringify(result)).not.toContain(secretPath);
  });

  it("projects every backup/restore success onto its exact public schema", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerWithChoosers({
      ipcMain,
      rpc,
      chooseBackupDestination: async () => "X:\\private\\backup.zip",
      chooseRestoreSource: async () => "X:\\private\\restore.zip",
    });

    const respond = async (
      channel: string,
      input: unknown,
      result: Record<string, unknown>,
    ): Promise<unknown> => {
      const pending = Promise.resolve(
        handlers.get(channel)!(trustedSender(), input),
      );
      await Promise.resolve();
      const request = latestRequest(child);
      child.emitStdout(
        JSON.stringify({ jsonrpc: "2.0", id: request.id, result }),
      );
      return pending;
    };

    await expect(
      respond(IPC.backupDescribe, undefined, {
        ...VALID_BACKUP_DESCRIPTION,
        source_path: "X:\\private\\leak.zip",
        nested: { destination_path: "X:\\private\\nested.zip" },
      }),
    ).resolves.toEqual(VALID_BACKUP_DESCRIPTION);

    await expect(
      respond(IPC.backupCreate, { acknowledgement: true }, {
        ok: true,
        finalized: true,
        entry_count: 3,
        format: "loopplane.desktop.backup",
        disclosure_applied: true,
        destination_path: "X:\\private\\leak.zip",
        nested: { path: "X:\\private\\nested.zip" },
      }),
    ).resolves.toEqual({
      ok: true,
      finalized: true,
      entry_count: 3,
      format: "loopplane.desktop.backup",
      disclosure_applied: true,
    });

    await expect(
      respond(IPC.restoreValidate, undefined, {
        restore_token: "opaque-token",
        summary: {
          ...VALID_RESTORE_SUMMARY,
          entry_count: 3,
          has_manifest: true,
          has_profile: true,
          source_path: "X:\\private\\leak.zip",
          nested: { path: "X:\\private\\nested.zip" },
        },
        path: "X:\\private\\leak.zip",
      }),
    ).resolves.toEqual({
      restore_token: "opaque-token",
      summary: VALID_RESTORE_SUMMARY,
    });

    await expect(
      respond(
        IPC.restoreCommit,
        { restoreToken: "opaque-token", confirmation: true },
        {
          ok: true,
          committed: true,
          relink_required: true,
          source_path: "X:\\private\\leak.zip",
        },
      ),
    ).resolves.toEqual({
      ok: true,
      committed: true,
      relink_required: true,
    });

    await expect(
      respond(IPC.restoreCancel, { restoreToken: "opaque-token" }, {
        cancelled: true,
        restore_token: "opaque-token",
        source_path: "X:\\private\\leak.zip",
      }),
    ).resolves.toBeUndefined();
  });

  it.each([
    [
      IPC.backupCreate,
      { acknowledgement: true },
      { ok: false, finalized: true, entry_count: 1, format: "loopplane.desktop.backup", disclosure_applied: true },
    ],
    [
      IPC.restoreCommit,
      { restoreToken: "opaque-token", confirmation: true },
      { ok: true, committed: false, relink_required: true },
    ],
    [
      IPC.restoreCancel,
      { restoreToken: "opaque-token" },
      { cancelled: false, restore_token: "opaque-token" },
    ],
  ])(
    "contains semantic-invalid success on %s with the sole fallback",
    async (channel, input, result) => {
      const child = createChildProcessDouble();
      const rpc = await readyRpc(child);
      const { handlers, ipcMain } = ipcMap();
      registerWithChoosers({
        ipcMain,
        rpc,
        chooseBackupDestination: async () => "X:\\private\\backup.zip",
      });
      const resultP = Promise.resolve(
        handlers.get(channel)!(trustedSender(), input),
      );
      await Promise.resolve();
      const request = latestRequest(child);
      child.emitStdout(
        JSON.stringify({ jsonrpc: "2.0", id: request.id, result }),
      );

      const error = await rejectedError(resultP);
      expect(error.desktop).toEqual(FALLBACK);
    },
  );

  it("contains a malformed sidecar restore token before it reaches renderer", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerWithChoosers({
      ipcMain,
      rpc,
      chooseRestoreSource: async () => "X:\\private\\restore.zip",
    });
    const resultP = Promise.resolve(
      handlers.get(IPC.restoreValidate)!(trustedSender()),
    );
    await Promise.resolve();
    const request = latestRequest(child);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          restore_token: "../staging/token",
          summary: {
            ...VALID_RESTORE_SUMMARY,
            entry_count: 3,
            has_manifest: true,
            has_profile: true,
          },
        },
      }),
    );

    const error = await rejectedError(resultP);
    expect(error.desktop).toEqual(FALLBACK);
  });

  it.each([
    [
      IPC.restoreCommit,
      { restoreToken: "opaque-token", confirmation: true },
      "restore.commit",
      { ok: true, committed: true, relink_required: true },
      { ok: true, committed: true, relink_required: true },
    ],
    [
      IPC.restoreCancel,
      { restoreToken: "opaque-token" },
      "restore.cancel",
      { cancelled: true, restore_token: "opaque-token" },
      undefined,
    ],
  ])("validates and privately mutates %s", async (channel, input, method, result, publicResult) => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
    });
    const resultP = Promise.resolve(
      handlers.get(channel)!(trustedSender(), input),
    );
    await Promise.resolve();
    const request = latestRequest(child);
    expect(request.method).toBe(method);
    expect(request.params.restore_token).toBe("opaque-token");
    expect(request.params.mutation_id).toMatch(/^mut-/);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        result,
      }),
    );
    await expect(resultP).resolves.toEqual(publicResult);
  });

  it.each([
    [IPC.restoreCommit, { restoreToken: "", confirmation: true }],
    [IPC.restoreCommit, { restoreToken: "opaque-token", confirmation: false }],
    [IPC.restoreCommit, { restoreToken: "a".repeat(129), confirmation: true }],
    [IPC.restoreCancel, { restoreToken: "" }],
    [IPC.restoreCancel, { restoreToken: "../staging/token" }],
    [IPC.restoreCancel, { restoreToken: "C:\\private\\token" }],
  ])("rejects invalid token/confirmation on %s before RPC", async (channel, input) => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
    });
    const writesBefore = child.written.length;

    await expect(
      handlers.get(channel)!(trustedSender(), input),
    ).rejects.toThrow("desktop.error.invalid_params");
    expect(child.written).toHaveLength(writesBefore);
  });

  it.each([
    [IPC.backupCreate, { acknowledgement: true }, "X:\\private\\backup.zip"],
    [IPC.restoreValidate, {}, "X:\\private\\restore.zip"],
  ])(
    "invalidates an in-flight privileged chooser when its handler registration ends on %s",
    async (channel, input, selectedPath) => {
      const child = createChildProcessDouble();
      const rpc = await readyRpc(child);
      const { handlers, ipcMain } = ipcMap();
      let resolveChooser: ((value: string | null) => void) | undefined;
      const chooser = () =>
        new Promise<string | null>((resolve) => {
          resolveChooser = resolve;
        });
      const unregister = registerDesktopIpcHandlers({
        ...TRUSTED_HANDLER_OPTIONS,
        ipcMain,
        rpc,
        chooseBackupDestination: chooser,
        chooseRestoreSource: chooser,
      });
      const writesBefore = child.written.length;
      const resultP = Promise.resolve(
        handlers.get(channel)!(trustedSender(), input),
      );
      await Promise.resolve();
      expect(resolveChooser).toBeTypeOf("function");

      unregister();
      resolveChooser!(selectedPath);
      await Promise.resolve();
      await Promise.resolve();

      expect(child.written).toHaveLength(writesBefore);
      const error = await rejectedError(resultP);
      expect(error.desktop).toEqual(FALLBACK);
    },
  );

  it("rejects untrusted backup/restore senders before chooser or RPC", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const chooseBackupDestination = vi.fn(async () => "X:\\private\\backup.zip");
    const chooseRestoreSource = vi.fn(async () => "X:\\private\\restore.zip");
    registerWithChoosers({
      ipcMain,
      rpc,
      chooseBackupDestination,
      chooseRestoreSource,
    });
    const evil = createIpcSenderFrom(
      createWebContentsDouble({ url: "https://evil.example" }),
    );
    const writesBefore = child.written.length;

    for (const [channel, input] of [
      [IPC.backupDescribe, undefined],
      [IPC.backupCreate, { acknowledgement: true }],
      [IPC.restoreValidate, {}],
      [IPC.restoreCommit, { restoreToken: "token", confirmation: true }],
      [IPC.restoreCancel, { restoreToken: "token" }],
    ] as const) {
      const error = await rejectedError(
        Promise.resolve(handlers.get(channel)!(evil, input)),
      );
      expect(error.message).toBe(FALLBACK.messageKey);
      expect(error.desktop).toEqual(FALLBACK);
    }
    expect(chooseBackupDestination).not.toHaveBeenCalled();
    expect(chooseRestoreSource).not.toHaveBeenCalled();
    expect(child.written).toHaveLength(writesBefore);
  });

  it("rejects subframe, stale, wrong-entry, and id-less senders before chooser", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    const trustedUrl = "file:///app/dist/index.html";
    const mainFrame = { url: trustedUrl };
    const sender = {
      id: 1,
      isDestroyed: () => false,
      getURL: () => trustedUrl,
      mainFrame,
    };
    const chooseBackupDestination = vi.fn(async () => null);
    registerWithChoosers({
      ipcMain,
      rpc,
      expectedSenderId: 1,
      expectedSenderUrl: trustedUrl,
      chooseBackupDestination,
    } as ChooserRegistration & { expectedSenderUrl: string });
    const wrongEntryFrame = { url: "file:///other/index.html" };
    const badEvents = [
      { sender, senderFrame: { url: trustedUrl } },
      {
        sender: { ...sender, id: undefined },
        senderFrame: mainFrame,
      },
      {
        sender: {
          ...sender,
          getURL: () => wrongEntryFrame.url,
          mainFrame: wrongEntryFrame,
        },
        senderFrame: wrongEntryFrame,
      },
      {
        sender: { ...sender, isDestroyed: () => true },
        senderFrame: mainFrame,
      },
      { sender, senderFrame: null },
    ] as unknown as IpcEventLike[];

    for (const event of badEvents) {
      const error = await rejectedError(
        Promise.resolve(
          handlers.get(IPC.backupCreate)!(event, { acknowledgement: true }),
        ),
      );
      expect(error.message).toBe(FALLBACK.messageKey);
      expect(error.desktop).toEqual(FALLBACK);
    }
    expect(chooseBackupDestination).not.toHaveBeenCalled();
  });
});

describe("backup/restore exhaustive public error mapping", () => {
  it("returns a structured-cloneable typed error envelope from main", async () => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { rawHandlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
    });
    const resultP = Promise.resolve(
      rawHandlers.get(IPC.backupDescribe)!(trustedSender()),
    );
    await Promise.resolve();
    const request = latestRequest(child);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        error: {
          code: -32012,
          message: "raw private failure",
          data: {
            category: "publication_failed",
            retryable: false,
            recovery: "restart_runtime",
            messageKey: "restore.error.publication_failed_restart",
          },
        },
      }),
    );

    const envelope = await resultP;
    expect(structuredClone(envelope)).toEqual({
      ok: false,
      error: {
        category: "publication_failed",
        messageKey: "restore.error.publication_failed_restart",
        retryable: false,
        recovery: "restart_runtime",
      },
    });
  });

  it.each(ERROR_ROWS)("maps $name to the exact typed row", async ({ wire, desktop }) => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
    });
    const resultP = Promise.resolve(
      handlers.get(IPC.backupDescribe)!(trustedSender()),
    );
    await Promise.resolve();
    const request = latestRequest(child);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        error: {
          code: wire.code,
          message: "raw private failure X:\\private\\secret.zip",
          data: {
            category: wire.category,
            retryable: wire.retryable,
            ...(wire.recovery === undefined ? {} : { recovery: wire.recovery }),
            messageKey: wire.messageKey,
          },
        },
      }),
    );

    const error = await rejectedError(resultP);
    expect(error.message).toBe(desktop.messageKey);
    expect(error.desktop).toMatchObject(desktop);
    expect(Object.hasOwn(error.desktop, "recovery")).toBe(
      desktop.recovery !== undefined,
    );
    expect(JSON.stringify(error.desktop)).not.toContain("private");
    expect(JSON.stringify(error.desktop)).not.toContain("secret.zip");
  });

  it.each([
    {
      name: "outward internal cause category",
      wire: {
        code: -32007,
        category: "unsafe_archive",
        retryable: false,
        messageKey: "backup.error.unsafe_archive",
      },
    },
    {
      name: "unknown code/category",
      wire: {
        code: -32999,
        category: "mystery",
        retryable: true,
        recovery: "retry",
        messageKey: "backup.error.mystery",
      },
    },
    {
      name: "mismatched code/category",
      wire: {
        code: -32004,
        category: "unsafe_input",
        retryable: true,
        recovery: "wait",
        messageKey: "backup.error.profile_busy",
      },
    },
    {
      name: "missing required recovery",
      wire: {
        code: -32004,
        category: "busy",
        retryable: true,
        messageKey: "backup.error.profile_busy",
      },
    },
    {
      name: "extra recovery",
      wire: {
        code: -32007,
        category: "unsafe_input",
        retryable: false,
        recovery: "retry",
        messageKey: "backup.error.unsafe_archive",
      },
    },
    {
      name: "combined recovery",
      wire: {
        code: -32012,
        category: "publication_failed",
        retryable: true,
        recovery: "retry|restart_runtime",
        messageKey: "restore.error.publication_failed_retryable",
      },
    },
    {
      name: "mismatched retryability",
      wire: {
        code: -32011,
        category: "durability_unsupported",
        retryable: true,
        recovery: "contact_support",
        messageKey: "restore.error.durability_unsupported",
      },
    },
    {
      name: "wrong fixed message key",
      wire: {
        code: -32009,
        category: "cancelled",
        retryable: false,
        messageKey: "backup.error.unsafe_archive",
      },
    },
    {
      name: "missing fixed message key",
      wire: {
        code: -32009,
        category: "cancelled",
        retryable: false,
        messageKey: undefined,
      },
    },
  ])("contains invalid $name with the sole fallback", async ({ wire }) => {
    const child = createChildProcessDouble();
    const rpc = await readyRpc(child);
    const { handlers, ipcMain } = ipcMap();
    registerDesktopIpcHandlers({
      ...TRUSTED_HANDLER_OPTIONS,
      ipcMain,
      rpc,
    });
    const resultP = Promise.resolve(
      handlers.get(IPC.backupDescribe)!(trustedSender()),
    );
    await Promise.resolve();
    const request = latestRequest(child);
    child.emitStdout(
      JSON.stringify({
        jsonrpc: "2.0",
        id: request.id,
        error: {
          code: wire.code,
          message: "raw secret internal cause",
          data: {
            category: wire.category,
            retryable: wire.retryable,
            ...(wire.recovery === undefined ? {} : { recovery: wire.recovery }),
            ...(wire.messageKey === undefined
              ? {}
              : { messageKey: wire.messageKey }),
          },
        },
      }),
    );

    const error = await rejectedError(resultP);
    expect(error.message).toBe(FALLBACK.messageKey);
    expect(error.desktop).toEqual(FALLBACK);
    expect(JSON.stringify(error.desktop)).not.toContain("secret");
    expect(JSON.stringify(error.desktop)).not.toContain(wire.category);
  });
});
