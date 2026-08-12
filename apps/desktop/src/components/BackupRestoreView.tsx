import { useState } from "react";

import { AuditView, type AuditEntry } from "@loopplane/cowork-presentation";

import type {
  BackupCreateResult,
  RestoreCommitResult,
  RestoreValidationResult,
} from "../global";

type BackupRestoreHost = {
  createBackup(acknowledgement: boolean): Promise<BackupCreateResult | null>;
  validateRestore(): Promise<RestoreValidationResult | null>;
  commitRestore(
    restoreToken: string,
    confirmation: boolean,
  ): Promise<RestoreCommitResult>;
  cancelRestore(restoreToken: string): Promise<void>;
};

type DesktopPublicError = {
  category: string;
  messageKey: string;
  retryable: boolean;
  recovery?: string;
};

const PUBLIC_ERROR_MESSAGES: Record<string, string> = {
  "desktop.error.invalid_params": "The request was invalid.",
  "backup.error.unsafe_archive": "This backup cannot be used safely.",
  "backup.error.incompatible": "This backup is incompatible. Contact support.",
  "backup.error.integrity_failed": "Backup integrity validation failed.",
  "backup.error.limit_exceeded": "This backup exceeds restore safety limits.",
  "backup.error.profile_busy": "The profile is busy. Wait and try again.",
  "backup.error.insufficient_space":
    "There is insufficient space. Free space and retry.",
  "restore.error.durability_unsupported":
    "Restore is not supported on this storage. Contact support.",
  "restore.error.publication_failed_retryable":
    "Restore could not be published. Retry.",
  "restore.error.publication_failed_restart":
    "Restore state is uncertain. Restart the runtime.",
  "restore.error.rolled_back": "Restore was rolled back. Retry.",
  "backup.error.cancelled": "The operation was cancelled.",
  "desktop.error.internal_failure":
    "An internal failure occurred. Restart the runtime.",
};

function publicErrorMessage(error: unknown): string {
  const desktop = (error as { desktop?: unknown } | null)?.desktop;
  if (desktop === null || typeof desktop !== "object" || Array.isArray(desktop)) {
    return PUBLIC_ERROR_MESSAGES["desktop.error.internal_failure"]!;
  }
  const messageKey = (desktop as DesktopPublicError).messageKey;
  return (
    PUBLIC_ERROR_MESSAGES[messageKey] ??
    PUBLIC_ERROR_MESSAGES["desktop.error.internal_failure"]!
  );
}

export type BackupRestoreViewProps = {
  host: BackupRestoreHost | null;
  auditEntries?: AuditEntry[];
  auditLoading?: boolean;
  auditFailed?: boolean;
  onBack(): void;
};

export function BackupRestoreView({
  host,
  auditEntries = [],
  auditLoading = false,
  auditFailed = false,
  onBack,
}: BackupRestoreViewProps) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [restore, setRestore] = useState<RestoreValidationResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function createBackup() {
    if (!host || !acknowledged || busy) return;
    setBusy(true);
    setError(null);
    setStatus("Creating backup…");
    try {
      const result = await host.createBackup(true);
      setStatus(result === null ? "Backup cancelled." : "Backup complete.");
    } catch (caught) {
      setStatus(null);
      setError(publicErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function validateRestore() {
    if (!host || busy) return;
    setBusy(true);
    setError(null);
    setStatus("Validating backup…");
    setRestore(null);
    setConfirmed(false);
    try {
      const result = await host.validateRestore();
      setRestore(result);
      setStatus(result === null ? "Restore selection cancelled." : null);
    } catch (caught) {
      setStatus(null);
      setError(publicErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function commitRestore() {
    if (!host || !restore || !confirmed || busy) return;
    setBusy(true);
    setError(null);
    setStatus("Restoring profile…");
    try {
      await host.commitRestore(restore.restore_token, true);
      setRestore(null);
      setConfirmed(false);
      setStatus("Restore complete. Workspace relink required.");
    } catch (caught) {
      setStatus(null);
      setError(publicErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function cancelRestore() {
    if (!host || !restore || busy) return;
    setBusy(true);
    setError(null);
    setStatus("Cancelling restore…");
    try {
      await host.cancelRestore(restore.restore_token);
      setRestore(null);
      setConfirmed(false);
      setStatus("Restore reservation cancelled.");
    } catch (caught) {
      setStatus(null);
      setError(publicErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="backup-restore-view">
      <button type="button" onClick={onBack}>
        Back to chat
      </button>
      <h1>Backup and restore</h1>

      <section aria-labelledby="backup-heading">
        <h2 id="backup-heading">Create a portable backup</h2>
        <p>
          The archive is not application-encrypted. Full session history, including
          user, model, and tool conversation content, and eligible artifacts are
          preserved losslessly. They may contain credentials, secrets, personal
          data, absolute paths, or copied workspace excerpts.
        </p>
        <p>
          Unsent drafts are excluded and cannot be recovered. LoopPlane-owned
          provider credentials or tokens, private capability configuration, private
          workspace path mappings, logs, raw internal errors, PIDs, caches,
          transient run state, and arbitrary workspace contents are also excluded.
        </p>
        <p>
          Choose and protect the destination through the operating system. Integrity
          hashes detect corruption but do not encrypt or authenticate the archive,
          or protect it from someone who can rewrite the complete archive.
        </p>
        <label>
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          I understand this backup is unencrypted
        </label>
        <button
          type="button"
          disabled={!host || !acknowledged || busy}
          onClick={() => void createBackup()}
        >
          Choose backup destination
        </button>
      </section>

      <section aria-labelledby="restore-heading">
        <h2 id="restore-heading">Restore a portable backup</h2>
        <button
          type="button"
          disabled={!host || busy || restore !== null}
          onClick={() => void validateRestore()}
        >
          Choose backup to restore
        </button>

        {restore && (
          <div aria-label="Restore preview">
            <p>Restore reservation active.</p>
            <ul>
              <li>Projects: {restore.summary.project_count}</li>
              <li>Sessions: {restore.summary.session_count}</li>
              <li>Artifacts: {restore.summary.artifact_count}</li>
              <li>Unsent drafts excluded</li>
              <li>Workspace relink required</li>
            </ul>
            <label>
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              Replace this profile
            </label>
            <button
              type="button"
              disabled={!confirmed || busy}
              onClick={() => void commitRestore()}
            >
              Commit restore
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void cancelRestore()}
            >
              Cancel restore
            </button>
          </div>
        )}
      </section>

      {status && (
        <div role="status" aria-live="polite">
          {status}
        </div>
      )}
      {error && <div role="alert">{error}</div>}
      {!host && <div role="alert">Backup and restore unavailable.</div>}

      <AuditView
        entries={auditEntries}
        loading={auditLoading}
        failed={auditFailed}
      />
    </main>
  );
}
