import { useState } from "react";

import { AuditView, type AuditEntry } from "@loopplane/cowork-presentation";

import { useTranslation } from "../i18n";

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

const FALLBACK_ERROR_KEY = "desktop.error.internal_failure";

/**
 * The message keys the sidecar is allowed to surface here. Membership is checked
 * before translating: an unrecognized key must not reach `t()`, which would
 * render the key itself and put an internal identifier on screen.
 */
const PUBLIC_ERROR_KEYS: ReadonlySet<string> = new Set([
  "desktop.error.invalid_params",
  "backup.error.unsafe_archive",
  "backup.error.incompatible",
  "backup.error.integrity_failed",
  "backup.error.limit_exceeded",
  "backup.error.profile_busy",
  "backup.error.insufficient_space",
  "restore.error.durability_unsupported",
  "restore.error.publication_failed_retryable",
  "restore.error.publication_failed_restart",
  "restore.error.rolled_back",
  "backup.error.cancelled",
  FALLBACK_ERROR_KEY,
]);

function publicErrorKey(error: unknown): string {
  const desktop = (error as { desktop?: unknown } | null)?.desktop;
  if (desktop === null || typeof desktop !== "object" || Array.isArray(desktop)) {
    return FALLBACK_ERROR_KEY;
  }
  const messageKey = (desktop as DesktopPublicError).messageKey;
  return PUBLIC_ERROR_KEYS.has(messageKey) ? messageKey : FALLBACK_ERROR_KEY;
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
  const { t } = useTranslation();
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
    setStatus(t("backup.creating"));
    try {
      const result = await host.createBackup(true);
      setStatus(t(result === null ? "backup.cancelled" : "backup.complete"));
    } catch (caught) {
      setStatus(null);
      setError(t(publicErrorKey(caught)));
    } finally {
      setBusy(false);
    }
  }

  async function validateRestore() {
    if (!host || busy) return;
    setBusy(true);
    setError(null);
    setStatus(t("restore.validating"));
    setRestore(null);
    setConfirmed(false);
    try {
      const result = await host.validateRestore();
      setRestore(result);
      setStatus(result === null ? t("restore.selectionCancelled") : null);
    } catch (caught) {
      setStatus(null);
      setError(t(publicErrorKey(caught)));
    } finally {
      setBusy(false);
    }
  }

  async function commitRestore() {
    if (!host || !restore || !confirmed || busy) return;
    setBusy(true);
    setError(null);
    setStatus(t("restore.restoring"));
    try {
      await host.commitRestore(restore.restore_token, true);
      setRestore(null);
      setConfirmed(false);
      setStatus(t("restore.complete"));
    } catch (caught) {
      setStatus(null);
      setError(t(publicErrorKey(caught)));
    } finally {
      setBusy(false);
    }
  }

  async function cancelRestore() {
    if (!host || !restore || busy) return;
    setBusy(true);
    setError(null);
    setStatus(t("restore.cancelling"));
    try {
      await host.cancelRestore(restore.restore_token);
      setRestore(null);
      setConfirmed(false);
      setStatus(t("restore.reservationCancelled"));
    } catch (caught) {
      setStatus(null);
      setError(t(publicErrorKey(caught)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="backup-restore-view">
      <button type="button" onClick={onBack}>
        {t("backup.back")}
      </button>
      <h1>{t("backup.title")}</h1>

      <section aria-labelledby="backup-heading">
        <h2 id="backup-heading">{t("backup.createHeading")}</h2>
        <p>{t("backup.disclosureContents")}</p>
        <p>{t("backup.disclosureExclusions")}</p>
        <p>{t("backup.disclosureDestination")}</p>
        <label>
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          {t("backup.acknowledge")}
        </label>
        <button
          type="button"
          disabled={!host || !acknowledged || busy}
          onClick={() => void createBackup()}
        >
          {t("backup.chooseDestination")}
        </button>
      </section>

      <section aria-labelledby="restore-heading">
        <h2 id="restore-heading">{t("restore.heading")}</h2>
        <button
          type="button"
          disabled={!host || busy || restore !== null}
          onClick={() => void validateRestore()}
        >
          {t("restore.choose")}
        </button>

        {restore && (
          <div aria-label={t("restore.preview")}>
            <p>{t("restore.reservationActive")}</p>
            <ul>
              <li>{t("restore.projects")}: {restore.summary.project_count}</li>
              <li>{t("restore.sessions")}: {restore.summary.session_count}</li>
              <li>{t("restore.artifacts")}: {restore.summary.artifact_count}</li>
              <li>{t("restore.draftsExcluded")}</li>
              <li>{t("restore.relinkRequired")}</li>
            </ul>
            <label>
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              {t("restore.replaceProfile")}
            </label>
            <div className="restore-actions">
              <button
                type="button"
                className="primary"
                disabled={!confirmed || busy}
                onClick={() => void commitRestore()}
              >
                {t("restore.commit")}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void cancelRestore()}
              >
                {t("restore.cancel")}
              </button>
            </div>
          </div>
        )}
      </section>

      {status && (
        <div role="status" aria-live="polite">
          {status}
        </div>
      )}
      {error && <div role="alert">{error}</div>}
      {!host && <div role="alert">{t("backup.unavailable")}</div>}

      <AuditView
        entries={auditEntries}
        loading={auditLoading}
        failed={auditFailed}
      />
    </main>
  );
}
