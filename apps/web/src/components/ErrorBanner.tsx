import { useTranslation } from "../i18n/i18n";

// A non-blocking error banner (FR-010): surfaces a connection/stream failure while the preserved
// conversation stays visible. role="alert" so it is announced. A Retry action (032) re-establishes
// the stream when a handler is given.
export function ErrorBanner({ onRetry }: { onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="error-banner" role="alert">
      <span>{t("error.disconnected")}</span>
      {onRetry && (
        <button type="button" className="retry" onClick={onRetry}>
          {t("error.retry")}
        </button>
      )}
    </div>
  );
}
