/**
 * Operation-specific ipcMain handlers (078 T028).
 *
 * Validates trusted sender, never accepts raw RPC method/ids from renderer,
 * generates mutation IDs on main, maps to SidecarRpcClient.
 */

import {
  backupRestoreFailure,
  backupRestoreSuccess,
  type BackupRestoreIpcEnvelope,
  type DesktopPublicError,
} from "./backup-restore-ipc";
import { IPC } from "./ipc-channels";
import type {
  ProviderConfig,
  PublicProviderView,
  SaveResult,
} from "./provider-credentials";
import {
  assertTrustedSender,
  type IpcEventLike,
} from "./window-security";
import type { SidecarRpcClient } from "./sidecar-rpc";
import { SidecarRpcClientError } from "./sidecar-rpc";

class DesktopIpcError extends Error {
  readonly desktop: DesktopPublicError;

  constructor(desktop: DesktopPublicError) {
    super(desktop.messageKey);
    this.desktop = { ...desktop };
  }
}

export type IpcMainLike = {
  handle: (
    channel: string,
    listener: (event: IpcEventLike, ...args: unknown[]) => unknown | Promise<unknown>,
  ) => void;
  removeHandler?: (channel: string) => void;
};

export type StatusProvider = () => Promise<Record<string, unknown>> | Record<string, unknown>;

function mapError(err: unknown): DesktopPublicError {
  if (err instanceof SidecarRpcClientError) {
    return {
      category: err.public.category,
      messageKey: err.public.messageKey ?? "desktop.error.internal_failure",
      retryable: err.public.retryable,
      recovery: err.public.recovery,
    };
  }
  return {
    category: "internal_failure",
    messageKey: "desktop.error.internal_failure",
    retryable: true,
    recovery: "restart_runtime",
  };
}

const BACKUP_RESTORE_FALLBACK: DesktopPublicError = {
  category: "internal_failure",
  messageKey: "desktop.error.internal_failure",
  retryable: true,
  recovery: "restart_runtime",
};

type BackupRestoreErrorRow = {
  code: number;
  category: string;
  retryable: boolean;
  recovery?: string;
  messageKey: string;
  desktop: DesktopPublicError;
};

const BACKUP_RESTORE_ERROR_ROWS: readonly BackupRestoreErrorRow[] = [
  {
    code: -32007,
    category: "unsafe_input",
    retryable: false,
    messageKey: "backup.error.unsafe_archive",
    desktop: {
      category: "unsafe_input",
      messageKey: "backup.error.unsafe_archive",
      retryable: false,
    },
  },
  {
    code: -32001,
    category: "incompatible_protocol",
    retryable: false,
    recovery: "contact_support",
    messageKey: "backup.error.incompatible",
    desktop: {
      category: "incompatible",
      messageKey: "backup.error.incompatible",
      retryable: false,
      recovery: "contact_support",
    },
  },
  {
    code: -32007,
    category: "unsafe_input",
    retryable: false,
    messageKey: "backup.error.integrity_failed",
    desktop: {
      category: "unsafe_input",
      messageKey: "backup.error.integrity_failed",
      retryable: false,
    },
  },
  {
    code: -32007,
    category: "unsafe_input",
    retryable: false,
    messageKey: "backup.error.limit_exceeded",
    desktop: {
      category: "unsafe_input",
      messageKey: "backup.error.limit_exceeded",
      retryable: false,
    },
  },
  {
    code: -32004,
    category: "busy",
    retryable: true,
    recovery: "wait",
    messageKey: "backup.error.profile_busy",
    desktop: {
      category: "busy",
      messageKey: "backup.error.profile_busy",
      retryable: true,
      recovery: "wait",
    },
  },
  {
    code: -32008,
    category: "unavailable",
    retryable: true,
    recovery: "retry",
    messageKey: "backup.error.insufficient_space",
    desktop: {
      category: "unavailable",
      messageKey: "backup.error.insufficient_space",
      retryable: true,
      recovery: "retry",
    },
  },
  {
    code: -32011,
    category: "durability_unsupported",
    retryable: false,
    recovery: "contact_support",
    messageKey: "restore.error.durability_unsupported",
    desktop: {
      category: "durability_unsupported",
      messageKey: "restore.error.durability_unsupported",
      retryable: false,
      recovery: "contact_support",
    },
  },
  {
    code: -32012,
    category: "publication_failed",
    retryable: true,
    recovery: "retry",
    messageKey: "restore.error.publication_failed_retryable",
    desktop: {
      category: "publication_failed",
      messageKey: "restore.error.publication_failed_retryable",
      retryable: true,
      recovery: "retry",
    },
  },
  {
    code: -32012,
    category: "publication_failed",
    retryable: false,
    recovery: "restart_runtime",
    messageKey: "restore.error.publication_failed_restart",
    desktop: {
      category: "publication_failed",
      messageKey: "restore.error.publication_failed_restart",
      retryable: false,
      recovery: "restart_runtime",
    },
  },
  {
    code: -32012,
    category: "publication_failed",
    retryable: true,
    recovery: "retry",
    messageKey: "restore.error.rolled_back",
    desktop: {
      category: "publication_failed",
      messageKey: "restore.error.rolled_back",
      retryable: true,
      recovery: "retry",
    },
  },
  {
    code: -32009,
    category: "cancelled",
    retryable: false,
    messageKey: "backup.error.cancelled",
    desktop: {
      category: "cancelled",
      messageKey: "backup.error.cancelled",
      retryable: false,
    },
  },
];

function mapBackupRestoreError(err: unknown): DesktopPublicError {
  if (!(err instanceof SidecarRpcClientError)) {
    return { ...BACKUP_RESTORE_FALLBACK };
  }
  const match = BACKUP_RESTORE_ERROR_ROWS.find(
    (row) =>
      row.code === err.public.code &&
      row.category === err.public.category &&
      row.retryable === err.public.retryable &&
      row.recovery === err.public.recovery &&
      row.messageKey === err.public.messageKey,
  );
  return match ? { ...match.desktop } : { ...BACKUP_RESTORE_FALLBACK };
}

function fail(err: unknown): never {
  throw new DesktopIpcError(mapError(err));
}

function failBackupRestore(err: unknown): never {
  throw new DesktopIpcError(mapBackupRestoreError(err));
}

function invalidParams(): never {
  throw new DesktopIpcError({
    category: "invalid_input",
    messageKey: "desktop.error.invalid_params",
    retryable: false,
  });
}

async function backupRestoreEnvelope<T>(
  action: () => Promise<T> | T,
): Promise<BackupRestoreIpcEnvelope<T>> {
  try {
    return backupRestoreSuccess(await action());
  } catch (err) {
    const mapped =
      err instanceof DesktopIpcError
        ? err.desktop
        : mapBackupRestoreError(err);
    return backupRestoreFailure(mapped);
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function exactInput(
  value: unknown,
  keys: readonly string[],
  { allowUndefined = false }: { allowUndefined?: boolean } = {},
): Record<string, unknown> {
  if (value === undefined && allowUndefined) return {};
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalidParams();
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    invalidParams();
  }
  const input = value as Record<string, unknown>;
  const actualKeys = Object.keys(input);
  if (
    actualKeys.length !== keys.length ||
    actualKeys.some((key) => !keys.includes(key))
  ) {
    invalidParams();
  }
  return input;
}

function requireString(obj: Record<string, unknown>, key: string): string {
  const v = obj[key];
  if (typeof v !== "string" || !v.trim()) {
    invalidParams();
  }
  return v;
}

const RESTORE_TOKEN_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;
const BACKUP_DISCLOSURE = [
  "This backup is unencrypted (not application-encrypted). ",
  "It preserves authorized conversation history and eligible Gateway artifacts, ",
  "which can contain sensitive user, model, or tool-produced content. ",
  "It excludes unsent drafts, device-private bindings, credentials, private ",
  "configuration, arbitrary workspace contents, and process state.",
].join("");
const BACKUP_INCLUDES = [
  "profile_portable_json",
  "projects_and_safe_preferences",
  "session_checkpoints",
  "eligible_referenced_gateway_artifacts",
] as const;
const BACKUP_EXCLUDES = [
  "unsent_drafts",
  "device_private_bindings",
  "profile_owner_lock",
  "capability_private_config",
  "credentials",
  "workspace_contents",
  "process_state",
] as const;

function requireRestoreToken(value: unknown): string {
  if (typeof value !== "string" || !RESTORE_TOKEN_PATTERN.test(value)) {
    invalidParams();
  }
  return value;
}

function invalidBackupRestoreResult(): never {
  failBackupRestore(new Error("invalid backup/restore result"));
}

function publicString(obj: Record<string, unknown>, key: string): string {
  const value = obj[key];
  if (typeof value !== "string" || !value.trim()) {
    invalidBackupRestoreResult();
  }
  return value;
}

function publicRestoreToken(obj: Record<string, unknown>): string {
  const token = publicString(obj, "restore_token");
  if (!RESTORE_TOKEN_PATTERN.test(token)) invalidBackupRestoreResult();
  return token;
}

function publicCount(obj: Record<string, unknown>, key: string): number {
  const value = obj[key];
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 0
  ) {
    invalidBackupRestoreResult();
  }
  return value;
}

function publicTrue(obj: Record<string, unknown>, key: string): true {
  if (obj[key] !== true) invalidBackupRestoreResult();
  return true;
}

function publicExactString(
  obj: Record<string, unknown>,
  key: string,
  expected: string,
): string {
  const value = publicString(obj, key);
  if (value !== expected) invalidBackupRestoreResult();
  return expected;
}

function publicExactStringArray(
  obj: Record<string, unknown>,
  key: string,
  expected: readonly string[],
): string[] {
  const value = obj[key];
  if (
    !Array.isArray(value) ||
    value.length !== expected.length ||
    value.some((item, index) => item !== expected[index])
  ) {
    invalidBackupRestoreResult();
  }
  return [...expected];
}

function publicBackupFormat(obj: Record<string, unknown>): string {
  const format = publicString(obj, "format");
  if (format !== "loopplane.desktop.backup") {
    invalidBackupRestoreResult();
  }
  return format;
}

function publicBackupVersion(
  obj: Record<string, unknown>,
): { major: 1; minor: 0 } {
  const version = asRecord(obj.version);
  if (
    publicCount(version, "major") !== 1 ||
    publicCount(version, "minor") !== 0
  ) {
    invalidBackupRestoreResult();
  }
  return { major: 1, minor: 0 };
}

function publicBackupCreatedAt(obj: Record<string, unknown>): string {
  const createdAt = publicString(obj, "created_at");
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(createdAt)) {
    invalidBackupRestoreResult();
  }
  return createdAt;
}

function projectBackupDescription(result: unknown): Record<string, unknown> {
  const value = asRecord(result);
  const schemaVersion = publicCount(value, "schema_version");
  if (schemaVersion !== 1) invalidBackupRestoreResult();
  return {
    disclosure: publicExactString(value, "disclosure", BACKUP_DISCLOSURE),
    includes: publicExactStringArray(value, "includes", BACKUP_INCLUDES),
    excludes: publicExactStringArray(value, "excludes", BACKUP_EXCLUDES),
    format: publicBackupFormat(value),
    schema_version: schemaVersion,
  };
}

function projectBackupCreateResult(result: unknown): Record<string, unknown> {
  const value = asRecord(result);
  return {
    ok: publicTrue(value, "ok"),
    finalized: publicTrue(value, "finalized"),
    entry_count: publicCount(value, "entry_count"),
    format: publicBackupFormat(value),
    disclosure_applied: publicTrue(value, "disclosure_applied"),
  };
}

function projectRestoreSummary(result: unknown): Record<string, unknown> {
  const value = asRecord(result);
  if (value.relink_required !== true) invalidBackupRestoreResult();
  return {
    format: publicBackupFormat(value),
    version: publicBackupVersion(value),
    created_at: publicBackupCreatedAt(value),
    project_count: publicCount(value, "project_count"),
    session_count: publicCount(value, "session_count"),
    artifact_count: publicCount(value, "artifact_count"),
    drafts_excluded: publicTrue(value, "drafts_excluded"),
    relink_required: true,
  };
}

function projectRestoreValidationResult(
  result: unknown,
): Record<string, unknown> {
  const value = asRecord(result);
  return {
    restore_token: publicRestoreToken(value),
    summary: projectRestoreSummary(value.summary),
  };
}

function projectRestoreCommitResult(result: unknown): Record<string, unknown> {
  const value = asRecord(result);
  if (value.relink_required !== true) invalidBackupRestoreResult();
  return {
    ok: publicTrue(value, "ok"),
    committed: publicTrue(value, "committed"),
    relink_required: true,
  };
}

function projectRestoreCancelResult(result: unknown): void {
  const value = asRecord(result);
  publicTrue(value, "cancelled");
  publicRestoreToken(value);
}

export type DirectoryChooser = () => Promise<string | null>;
export type FileChooser = () => Promise<string | null>;

export type RegisterHandlersOptions = {
  ipcMain: IpcMainLike;
  rpc: SidecarRpcClient;
  expectedSenderId: number;
  expectedSenderUrl: string;
  status?: StatusProvider;
  onShutdown?: () => Promise<void> | void;
  /** Main-owned native directory picker; returns absolute path or null. */
  chooseDirectory?: DirectoryChooser;
  /** Main-owned native save picker; the renderer never receives its path. */
  chooseBackupDestination?: FileChooser;
  /** Main-owned native open picker; the renderer never receives its path. */
  chooseRestoreSource?: FileChooser;
  /**
   * Main-owned provider credential vault. Kept behind a port so this module
   * stays free of `electron` and `node:fs`: the key is decrypted only in main,
   * and only `get()`'s public view is allowed to answer the renderer.
   */
  providerVault?: ProviderVaultPort;
};

export type ProviderVaultPort = {
  get(): PublicProviderView | null;
  save(input: ProviderConfig): SaveResult;
  clear(): void;
  /** Relaunch the app so a new provider setting reaches a fresh sidecar. */
  relaunch(): void;
};

/**
 * Register app + interactive + US2 session/project/workspace handlers.
 * Idempotent if removeHandler exists.
 */
export function registerDesktopIpcHandlers(options: RegisterHandlersOptions): () => void {
  const { ipcMain, rpc } = options;
  let registrationActive = true;
  const channels = [
    IPC.appStatus,
    IPC.appShutdown,
    IPC.sessionCreateInteractive,
    IPC.sessionResumeInteractive,
    IPC.sessionReleaseInteractive,
    IPC.sessionList,
    IPC.sessionHistory,
    IPC.sessionRename,
    IPC.sessionSetStarred,
    IPC.sessionDelete,
    IPC.sessionFork,
    IPC.projectList,
    IPC.projectCreate,
    IPC.projectRename,
    IPC.projectRemove,
    IPC.projectAssignSession,
    IPC.workspaceList,
    IPC.workspaceChooseAndBind,
    IPC.workspaceChooseAndRelink,
    IPC.workspaceRemove,
    IPC.workspaceRevalidate,
    IPC.interactionSubmit,
    IPC.interactionCancel,
    IPC.interactionAnswerApproval,
    IPC.interactionAnswerQuestion,
    IPC.inspectionGet,
    IPC.agentControlsGet,
    IPC.capabilitiesList,
    IPC.capabilitiesInvokeAction,
    IPC.auditList,
    IPC.backupDescribe,
    IPC.backupCreate,
    IPC.restoreValidate,
    IPC.restoreCommit,
    IPC.restoreCancel,
    IPC.providersGet,
    IPC.providersSave,
    IPC.providersClear,
    IPC.providersRestart,
  ];

  for (const ch of channels) {
    ipcMain.removeHandler?.(ch);
  }

  const guard = (event: IpcEventLike) => {
    if (!registrationActive) throw new Error("stale IPC registration");
    assertTrustedSender(
      event,
      options.expectedSenderId,
      options.expectedSenderUrl,
    );
  };

  ipcMain.handle(IPC.appStatus, async (event) => {
    guard(event);
    if (options.status) {
      return options.status();
    }
    try {
      return await rpc.request("system.status", {});
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.appShutdown, async (event) => {
    guard(event);
    try {
      if (options.onShutdown) {
        await options.onShutdown();
      } else {
        await rpc.shutdown();
      }
      return { ok: true };
    } catch (err) {
      fail(err);
    }
  });

  // Provider settings (Unit A). These four never reach the sidecar over RPC:
  // main owns the credential, and the sidecar receives it as spawn environment
  // on the next launch. Nothing here returns the key.
  ipcMain.handle(IPC.providersGet, async (event) => {
    guard(event);
    return options.providerVault ? options.providerVault.get() : null;
  });

  ipcMain.handle(IPC.providersSave, async (event, raw) => {
    guard(event);
    const input = exactInput(raw, ["provider", "modelId", "apiKey"]);
    const provider = requireString(input, "provider");
    const modelId = requireString(input, "modelId");
    const apiKey = typeof input.apiKey === "string" ? input.apiKey : null;
    if (!options.providerVault) {
      return { ok: false, reason: "encryption_unavailable" } satisfies SaveResult;
    }
    return options.providerVault.save({ provider, modelId, apiKey });
  });

  ipcMain.handle(IPC.providersClear, async (event) => {
    guard(event);
    options.providerVault?.clear();
    return { ok: true };
  });

  ipcMain.handle(IPC.providersRestart, async (event) => {
    guard(event);
    // A provider change only takes effect in a fresh sidecar, and the sidecar
    // holds the profile ownership lock; relaunching the app is the one path
    // that releases it without a partial teardown.
    options.providerVault?.relaunch();
    return { ok: true };
  });

  ipcMain.handle(IPC.sessionCreateInteractive, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    try {
      return await rpc.request(
        "session.createInteractive",
        {
          pane_id: typeof params.paneId === "string" ? params.paneId : params.pane_id,
          workspace_id:
            typeof params.workspaceId === "string"
              ? params.workspaceId
              : typeof params.workspace_id === "string"
                ? params.workspace_id
                : undefined,
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionResumeInteractive, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    try {
      return await rpc.request(
        "session.resumeInteractive",
        {
          session_id: sessionId,
          pane_id: typeof params.paneId === "string" ? params.paneId : params.pane_id,
          workspace_id:
            typeof params.workspaceId === "string"
              ? params.workspaceId
              : typeof params.workspace_id === "string"
                ? params.workspace_id
                : undefined,
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionReleaseInteractive, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const subscriptionId = requireString(
      {
        subscription_id:
          typeof params.subscriptionId === "string"
            ? params.subscriptionId
            : params.subscription_id,
      },
      "subscription_id",
    );
    try {
      return await rpc.request(
        "session.releaseInteractive",
        { subscription_id: subscriptionId },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.interactionSubmit, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const subscriptionId = requireString(
      {
        subscription_id:
          typeof params.subscriptionId === "string"
            ? params.subscriptionId
            : params.subscription_id,
      },
      "subscription_id",
    );
    const prompt = requireString(params, "prompt");
    if (params.permissionMode !== undefined && typeof params.permissionMode !== "string") {
      invalidParams();
    }
    try {
      return await rpc.request(
        "interaction.submit",
        {
          subscription_id: subscriptionId,
          prompt,
          ...(params.permissionMode === undefined
            ? {}
            : { permission_mode: params.permissionMode }),
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.interactionCancel, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const subscriptionId = requireString(
      {
        subscription_id:
          typeof params.subscriptionId === "string"
            ? params.subscriptionId
            : params.subscription_id,
      },
      "subscription_id",
    );
    try {
      return await rpc.request(
        "interaction.cancel",
        { subscription_id: subscriptionId },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.interactionAnswerApproval, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const subscriptionId = requireString(
      {
        subscription_id:
          typeof params.subscriptionId === "string"
            ? params.subscriptionId
            : params.subscription_id,
      },
      "subscription_id",
    );
    const requestId = requireString(
      {
        request_id:
          typeof params.requestId === "string"
            ? params.requestId
            : params.request_id,
      },
      "request_id",
    );
    if (typeof params.allow !== "boolean") {
      invalidParams();
    }
    try {
      return await rpc.request(
        "interaction.answerApproval",
        {
          subscription_id: subscriptionId,
          request_id: requestId,
          allow: params.allow,
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.interactionAnswerQuestion, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const subscriptionId = requireString(
      {
        subscription_id:
          typeof params.subscriptionId === "string"
            ? params.subscriptionId
            : params.subscription_id,
      },
      "subscription_id",
    );
    const requestId = requireString(
      {
        request_id:
          typeof params.requestId === "string"
            ? params.requestId
            : params.request_id,
      },
      "request_id",
    );
    const answers = params.answers;
    if (!Array.isArray(answers) || !answers.every((a) => typeof a === "string")) {
      invalidParams();
    }
    try {
      return await rpc.request(
        "interaction.answerQuestion",
        {
          subscription_id: subscriptionId,
          request_id: requestId,
          answers,
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  // --- US2: sessions / projects / workspaces (no paths to renderer) ---

  ipcMain.handle(IPC.sessionList, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    try {
      return await rpc.request("session.list", {
        query: typeof params.query === "string" ? params.query : undefined,
      });
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionHistory, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    try {
      return await rpc.request("session.history", { session_id: sessionId });
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionRename, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    const title = requireString(params, "title");
    try {
      return await rpc.request(
        "session.rename",
        { session_id: sessionId, title },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionSetStarred, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    if (typeof params.starred !== "boolean") invalidParams();
    try {
      return await rpc.request(
        "session.setStarred",
        { session_id: sessionId, starred: params.starred },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionDelete, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    if (!params.confirmation) invalidParams();
    try {
      return await rpc.request(
        "session.delete",
        { session_id: sessionId, confirmation: params.confirmation },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.sessionFork, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    if (!params.confirmation) invalidParams();
    try {
      return await rpc.request(
        "session.fork",
        {
          session_id: sessionId,
          confirmation: params.confirmation,
          source_sequence:
            typeof params.sourceSequence === "number"
              ? params.sourceSequence
              : 0,
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.projectList, async (event) => {
    guard(event);
    try {
      return await rpc.request("project.list", {});
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.projectCreate, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const label = requireString(params, "label");
    try {
      return await rpc.request(
        "project.create",
        { label },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.projectRename, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const projectId = requireString(
      {
        project_id:
          typeof params.projectId === "string"
            ? params.projectId
            : params.project_id,
      },
      "project_id",
    );
    const label = requireString(params, "label");
    try {
      return await rpc.request(
        "project.rename",
        { project_id: projectId, label },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.projectRemove, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const projectId = requireString(
      {
        project_id:
          typeof params.projectId === "string"
            ? params.projectId
            : params.project_id,
      },
      "project_id",
    );
    try {
      return await rpc.request(
        "project.remove",
        { project_id: projectId },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.projectAssignSession, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    const projectId =
      params.projectId === null || params.project_id === null
        ? null
        : typeof params.projectId === "string"
          ? params.projectId
          : typeof params.project_id === "string"
            ? params.project_id
            : null;
    try {
      return await rpc.request(
        "project.assignSession",
        { session_id: sessionId, project_id: projectId },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.workspaceList, async (event) => {
    guard(event);
    try {
      return await rpc.request("workspace.list", {});
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.workspaceChooseAndBind, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    if (!options.chooseDirectory) {
      fail(new Error("directory chooser unavailable"));
    }
    const path = await options.chooseDirectory();
    if (path === null) return null;
    try {
      // Path stays main-private; renderer only receives safe reference.
      return await rpc.request(
        "workspace.bind",
        {
          path,
          label: typeof params.label === "string" ? params.label : "Workspace",
        },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.workspaceChooseAndRelink, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const workspaceId = requireString(
      {
        workspace_id:
          typeof params.workspaceId === "string"
            ? params.workspaceId
            : params.workspace_id,
      },
      "workspace_id",
    );
    if (!options.chooseDirectory) {
      fail(new Error("directory chooser unavailable"));
    }
    const path = await options.chooseDirectory();
    if (path === null) return null;
    try {
      return await rpc.request(
        "workspace.relink",
        { workspace_id: workspaceId, path },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.workspaceRemove, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const workspaceId = requireString(
      {
        workspace_id:
          typeof params.workspaceId === "string"
            ? params.workspaceId
            : params.workspace_id,
      },
      "workspace_id",
    );
    try {
      return await rpc.request(
        "workspace.remove",
        { workspace_id: workspaceId },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.workspaceRevalidate, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const workspaceId = requireString(
      {
        workspace_id:
          typeof params.workspaceId === "string"
            ? params.workspaceId
            : params.workspace_id,
      },
      "workspace_id",
    );
    try {
      return await rpc.request(
        "workspace.revalidate",
        { workspace_id: workspaceId },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  // --- US4: inspection / agent controls / capabilities ---

  ipcMain.handle(IPC.inspectionGet, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    try {
      return await rpc.request("inspection.get", {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id ?? null,
      });
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.agentControlsGet, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    try {
      return await rpc.request("agentControls.get", {
        session_id: sessionId,
      });
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.capabilitiesList, async (event) => {
    guard(event);
    try {
      return await rpc.request("capabilities.list", {});
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.capabilitiesInvokeAction, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const capabilityId = requireString(
      {
        capability_id:
          typeof params.capabilityId === "string"
            ? params.capabilityId
            : params.capability_id,
      },
      "capability_id",
    );
    const action = requireString(params, "action");
    try {
      return await rpc.request(
        "capabilities.invokeAction",
        { capability_id: capabilityId, action },
        { mutationId: rpc.newMutationId() },
      );
    } catch (err) {
      fail(err);
    }
  });

  // --- US5: audit + backup/restore (paths stay main-private) ---

  ipcMain.handle(IPC.auditList, async (event, raw) => {
    guard(event);
    const params = asRecord(raw);
    const sessionId = requireString(
      {
        session_id:
          typeof params.sessionId === "string"
            ? params.sessionId
            : params.session_id,
      },
      "session_id",
    );
    const cursor = params.cursor;
    const limit = params.limit;
    if (
      (cursor !== undefined && (typeof cursor !== "string" || !cursor)) ||
      (limit !== undefined &&
        (typeof limit !== "number" ||
          !Number.isInteger(limit) ||
          limit < 1 ||
          limit > 100))
    ) {
      invalidParams();
    }
    try {
      return await rpc.request("audit.list", {
        session_id: sessionId,
        ...(cursor === undefined ? {} : { cursor }),
        ...(limit === undefined ? {} : { limit }),
      });
    } catch (err) {
      fail(err);
    }
  });

  ipcMain.handle(IPC.backupDescribe, async (event, raw) => {
    return backupRestoreEnvelope(async () => {
      guard(event);
      exactInput(raw, [], { allowUndefined: true });
      return projectBackupDescription(await rpc.request("backup.describe", {}));
    });
  });

  ipcMain.handle(IPC.backupCreate, async (event, raw) => {
    return backupRestoreEnvelope(async () => {
      guard(event);
      const params = exactInput(raw, ["acknowledgement"]);
      if (params.acknowledgement !== true) invalidParams();
      const chooser = options.chooseBackupDestination;
      if (chooser === undefined) {
        failBackupRestore(new Error("backup chooser unavailable"));
      }
      const dest = await chooser();
      guard(event);
      if (dest === null) return null;
      if (!dest.trim()) invalidParams();
      return projectBackupCreateResult(
        await rpc.request(
          "backup.create",
          {
            acknowledgement: true,
            destination_path: dest,
          },
          { mutationId: rpc.newMutationId() },
        ),
      );
    });
  });

  ipcMain.handle(IPC.restoreValidate, async (event, raw) => {
    return backupRestoreEnvelope(async () => {
      guard(event);
      exactInput(raw, [], { allowUndefined: true });
      const chooser = options.chooseRestoreSource;
      if (chooser === undefined) {
        failBackupRestore(new Error("restore chooser unavailable"));
      }
      const source = await chooser();
      guard(event);
      if (source === null) return null;
      if (!source.trim()) invalidParams();
      return projectRestoreValidationResult(
        await rpc.request(
          "restore.validate",
          { source_path: source },
          { mutationId: rpc.newMutationId() },
        ),
      );
    });
  });

  ipcMain.handle(IPC.restoreCommit, async (event, raw) => {
    return backupRestoreEnvelope(async () => {
      guard(event);
      const params = exactInput(raw, ["restoreToken", "confirmation"]);
      const token = requireRestoreToken(params.restoreToken);
      if (params.confirmation !== true) invalidParams();
      return projectRestoreCommitResult(
        await rpc.request(
          "restore.commit",
          { restore_token: token, confirmation: true },
          { mutationId: rpc.newMutationId() },
        ),
      );
    });
  });

  ipcMain.handle(IPC.restoreCancel, async (event, raw) => {
    return backupRestoreEnvelope(async () => {
      guard(event);
      const params = exactInput(raw, ["restoreToken"]);
      const token = requireRestoreToken(params.restoreToken);
      return projectRestoreCancelResult(
        await rpc.request(
          "restore.cancel",
          { restore_token: token },
          { mutationId: rpc.newMutationId() },
        ),
      );
    });
  });

  return () => {
    registrationActive = false;
    for (const ch of channels) {
      ipcMain.removeHandler?.(ch);
    }
  };
}
