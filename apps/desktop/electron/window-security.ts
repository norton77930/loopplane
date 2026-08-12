/**
 * BrowserWindow / session security helpers (078 T028 / IPC contract §2).
 *
 * Pure enough for unit tests: no Electron import required for policy constants
 * or URL checks; apply functions accept injected window/session doubles.
 */

/** Restrictive CSP for bundled local renderer assets (no remote connect/script). */
export const BUNDLED_RENDERER_CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'none'",
  "object-src 'none'",
  "base-uri 'none'",
  "frame-ancestors 'none'",
  "form-action 'none'",
].join("; ");

export type NavigationEventLike = {
  preventDefault: () => void;
};

export type WebContentsSecurityLike = {
  /** Narrow adapter: guards only subscribe to Electron's will-navigate event. */
  onWillNavigate: (listener: (event: NavigationEventLike, url: string) => void) => void;
  setWindowOpenHandler: (handler: (details: { url: string }) => { action: "deny" | "allow" }) => void;
  getURL: () => string;
};

export type BrowserWindowSecurityLike = {
  webContents: WebContentsSecurityLike;
};

export type SessionPermissionLike = {
  setPermissionRequestHandler: (
    handler: (
      webContents: unknown,
      permission: string,
      callback: (allow: boolean) => void,
    ) => void,
  ) => void;
  setPermissionCheckHandler: (
    handler: (
      webContents: unknown,
      permission: string,
      requestingOrigin: string,
      details: unknown,
    ) => boolean,
  ) => void;
};

/**
 * Install top-frame navigation denial and window-open denial (V1: deny all opens).
 * Only the exact already-loaded entry URL may navigate without preventDefault.
 */
export function installNavigationGuards(
  window: BrowserWindowSecurityLike,
  options: { entryUrl?: string } = {},
): void {
  const entry = options.entryUrl;

  window.webContents.onWillNavigate((event, url) => {
    const allowed =
      entry !== undefined && entry.length > 0
        ? url === entry || url === window.webContents.getURL()
        : url === window.webContents.getURL();
    if (!allowed) {
      event.preventDefault();
    }
  });

  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
}

/** Deny all renderer permission requests/checks by default. */
export function installDenyByDefaultPermissions(
  session: SessionPermissionLike,
): void {
  session.setPermissionRequestHandler((_wc, _permission, callback) => {
    callback(false);
  });
  session.setPermissionCheckHandler(() => false);
}

/** Trusted local renderer URL predicate for tests and development policy checks. */
export function isTrustedRendererUrl(url: string): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "file:") {
      return parsed.pathname.endsWith("/dist/index.html");
    }
    return (
      parsed.protocol === "http:" &&
      (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1")
    );
  } catch {
    return false;
  }
}

export type IpcFrameLike = { url?: string };

export type IpcEventLike = {
  senderFrame?: IpcFrameLike | null;
  sender?: {
    id?: number;
    isDestroyed?: () => boolean;
    getURL?: () => string;
    mainFrame?: IpcFrameLike;
  };
  /** Flat fields retained only for non-privileged test-double compatibility. */
  id?: number;
  url?: string;
  isDestroyed?: () => boolean;
};

export function assertTrustedSender(
  event: IpcEventLike,
  expectedSenderId: number,
  expectedSenderUrl: string,
): void {
  const frame = event.senderFrame;
  const sender = event.sender;
  if (frame === null || frame === undefined || sender === undefined) {
    throw new Error("untrusted sender frame");
  }
  if (frame !== sender.mainFrame) {
    throw new Error("untrusted sender subframe");
  }
  if (sender.isDestroyed?.() ?? true) {
    throw new Error("destroyed sender");
  }
  if (sender.id !== expectedSenderId) {
    throw new Error("sender window mismatch");
  }
  const frameUrl = frame.url ?? "";
  if (
    !expectedSenderUrl ||
    frameUrl !== expectedSenderUrl ||
    sender.getURL?.() !== expectedSenderUrl
  ) {
    throw new Error("untrusted sender entry");
  }
}
