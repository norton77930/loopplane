// A non-blocking error banner (FR-010): surfaces a connection/stream failure while the
// conversation already shown is preserved. role="alert" so it is announced.
export function ErrorBanner() {
  return (
    <div className="error-banner" role="alert">
      Disconnected &mdash; please retry.
    </div>
  );
}
