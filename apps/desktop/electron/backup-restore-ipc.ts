/**
 * Serializable backup/restore IPC result envelope and preload-side validation.
 */

export type DesktopPublicError = {
  category: string;
  messageKey: string;
  retryable: boolean;
  recovery?: string;
};

export type BackupRestoreIpcEnvelope<T = unknown> =
  | { ok: true; value: T }
  | { ok: false; error: DesktopPublicError };

const INTERNAL_FALLBACK: DesktopPublicError = {
  category: "internal_failure",
  messageKey: "desktop.error.internal_failure",
  retryable: true,
  recovery: "restart_runtime",
};

const PUBLIC_ERROR_ROWS: readonly DesktopPublicError[] = [
  {
    category: "invalid_input",
    messageKey: "desktop.error.invalid_params",
    retryable: false,
  },
  {
    category: "unsafe_input",
    messageKey: "backup.error.unsafe_archive",
    retryable: false,
  },
  {
    category: "incompatible",
    messageKey: "backup.error.incompatible",
    retryable: false,
    recovery: "contact_support",
  },
  {
    category: "unsafe_input",
    messageKey: "backup.error.integrity_failed",
    retryable: false,
  },
  {
    category: "unsafe_input",
    messageKey: "backup.error.limit_exceeded",
    retryable: false,
  },
  {
    category: "busy",
    messageKey: "backup.error.profile_busy",
    retryable: true,
    recovery: "wait",
  },
  {
    category: "unavailable",
    messageKey: "backup.error.insufficient_space",
    retryable: true,
    recovery: "retry",
  },
  {
    category: "durability_unsupported",
    messageKey: "restore.error.durability_unsupported",
    retryable: false,
    recovery: "contact_support",
  },
  {
    category: "publication_failed",
    messageKey: "restore.error.publication_failed_retryable",
    retryable: true,
    recovery: "retry",
  },
  {
    category: "publication_failed",
    messageKey: "restore.error.publication_failed_restart",
    retryable: false,
    recovery: "restart_runtime",
  },
  {
    category: "publication_failed",
    messageKey: "restore.error.rolled_back",
    retryable: true,
    recovery: "retry",
  },
  {
    category: "cancelled",
    messageKey: "backup.error.cancelled",
    retryable: false,
  },
  INTERNAL_FALLBACK,
];

function exactRecord(
  value: unknown,
  keys: readonly string[],
): Record<string, unknown> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const actual = Object.keys(record);
  if (
    actual.length !== keys.length ||
    actual.some((key) => !keys.includes(key))
  ) {
    return null;
  }
  return record;
}

function projectPublicError(value: unknown): DesktopPublicError | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  const hasRecovery = Object.prototype.hasOwnProperty.call(
    candidate,
    "recovery",
  );
  const record = exactRecord(
    value,
    hasRecovery
      ? ["category", "messageKey", "retryable", "recovery"]
      : ["category", "messageKey", "retryable"],
  );
  if (record === null) return null;
  const matched = PUBLIC_ERROR_ROWS.find(
    (row) =>
      row.category === record.category &&
      row.messageKey === record.messageKey &&
      row.retryable === record.retryable &&
      Object.prototype.hasOwnProperty.call(row, "recovery") === hasRecovery &&
      (!hasRecovery || row.recovery === record.recovery),
  );
  return matched === undefined ? null : { ...matched };
}

function throwPublicError(error: DesktopPublicError): never {
  const thrown = new Error(error.messageKey) as Error & {
    desktop: DesktopPublicError;
  };
  thrown.desktop = { ...error };
  throw thrown;
}

export function backupRestoreSuccess<T>(
  value: T,
): BackupRestoreIpcEnvelope<T> {
  return { ok: true, value };
}

export function backupRestoreFailure(
  error: DesktopPublicError,
): BackupRestoreIpcEnvelope<never> {
  return { ok: false, error: { ...error } };
}

export function unwrapBackupRestoreEnvelope<T>(value: unknown): T {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    if (record.ok === true) {
      const success = exactRecord(value, ["ok", "value"]);
      if (success !== null) return success.value as T;
    } else if (record.ok === false) {
      const failure = exactRecord(value, ["ok", "error"]);
      const error = failure === null ? null : projectPublicError(failure.error);
      if (error !== null) throwPublicError(error);
    }
  }
  throwPublicError(INTERNAL_FALLBACK);
}
