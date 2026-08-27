// The interactive MCP authorization flow, Desktop side (unit 084; ADR 0019 D1/D6).
//
// This is the half the runtime refuses to do. `src/loopplane` opens no browser and
// binds no socket — a runtime is frequently a headless server process, and one that
// reaches for a browser breaks there. Desktop is the opposite case: a local
// application, run by the machine's owner, with a browser and a spare port. So the
// listening happens here, and a contract test proves it does not happen there.
//
// Pure like the vault: `openExternal` and the HTTP server are injected, so the whole
// flow is unit-testable without Electron and without a real browser.

import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

/** The result a redirect delivered, as the runtime's protocol expects it. */
export interface McpAuthorizationResult {
  code: string;
  state: string | null;
}

export interface McpFlowDeps {
  /** Opens a URL in the user's browser (`shell.openExternal` in main.ts). */
  openExternal(url: string): Promise<void>;
  /** Overridable for tests; defaults to a loopback `node:http` server. */
  listen?(handler: RedirectHandler): Promise<RedirectListener>;
  /** Milliseconds before an unfinished authorization is abandoned. */
  timeoutMs?: number;
}

export type RedirectHandler = (query: URLSearchParams) => void;

export interface RedirectListener {
  /** The absolute redirect URI the authorization server must send the user to. */
  redirectUri: string;
  close(): Promise<void>;
}

// Five minutes matches the SDK's own authorization timeout. A shorter window
// punishes anyone who has to log in and pick an account first.
const DEFAULT_TIMEOUT_MS = 300_000;

const DONE_PAGE =
  "<!doctype html><meta charset=utf-8><title>LoopPlane</title>" +
  "<p>Authorization complete. You can close this tab and return to LoopPlane.";

const FAILED_PAGE =
  "<!doctype html><meta charset=utf-8><title>LoopPlane</title>" +
  "<p>Authorization did not complete. Return to LoopPlane and try again.";

function isSafeAuthorizationUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    if (parsed.username || parsed.password) return false;
    if (parsed.protocol === "https:") return true;
    return (
      parsed.protocol === "http:" &&
      (parsed.hostname === "127.0.0.1" || parsed.hostname === "[::1]")
    );
  } catch {
    return false;
  }
}

/**
 * A loopback listener on an OS-assigned port, bound to 127.0.0.1 only.
 *
 * Port 0 rather than a fixed port: a fixed one collides with whatever else the
 * user is running, and a collision here reads to them as "authorization is broken".
 * The cost is that the redirect URI is only known after binding, which is why the
 * runtime asks the host for it instead of assuming one.
 */
export async function loopbackListener(
  handler: RedirectHandler,
): Promise<RedirectListener> {
  let server: Server | null = null;
  const port = await new Promise<number>((resolve, reject) => {
    const created = createServer((request, response) => {
      let query: URLSearchParams;
      try {
        query = new URL(request.url ?? "/", "http://127.0.0.1").searchParams;
      } catch {
        response.writeHead(400, { "content-type": "text/html; charset=utf-8" });
        response.end(FAILED_PAGE);
        return;
      }
      const ok = query.has("code");
      response.writeHead(ok ? 200 : 400, {
        "content-type": "text/html; charset=utf-8",
      });
      response.end(ok ? DONE_PAGE : FAILED_PAGE);
      handler(query);
    });
    created.once("error", reject);
    created.listen(0, "127.0.0.1", () => {
      server = created;
      resolve((created.address() as AddressInfo).port);
    });
  });

  return {
    redirectUri: `http://127.0.0.1:${port}/callback`,
    close: () =>
      new Promise<void>((resolve) => {
        if (server === null) {
          resolve();
          return;
        }
        server.close(() => resolve());
        server = null;
      }),
  };
}

/**
 * Run one authorization: bind, hand the redirect URI to `begin`, open the browser
 * at the URL that comes back, and resolve with what the redirect delivered.
 *
 * The listener is always closed — on success, on failure, and on timeout. Leaving a
 * port bound after a user abandons a login would accumulate one listener per
 * attempt for the life of the application.
 */
export async function runAuthorization(
  deps: McpFlowDeps,
  begin: (redirectUri: string) => Promise<string>,
): Promise<McpAuthorizationResult> {
  const listen = deps.listen ?? loopbackListener;
  const timeoutMs = deps.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  let settle: ((result: McpAuthorizationResult) => void) | null = null;
  let fail: ((error: Error) => void) | null = null;
  const delivered = new Promise<McpAuthorizationResult>((resolve, reject) => {
    settle = resolve;
    fail = reject;
  });

  const listener = await listen((query) => {
    const code = query.get("code");
    if (code) {
      settle?.({ code, state: query.get("state") });
      return;
    }
    // An authorization server reports a denial as `error`, not as a missing code.
    // Failing here rather than waiting out the timeout is the difference between
    // "that didn't work" and five minutes of nothing happening.
    fail?.(new Error("authorization was not granted"));
  });

  let timer: ReturnType<typeof setTimeout> | null = null;
  try {
    const authorizationUrl = await begin(listener.redirectUri);
    if (!isSafeAuthorizationUrl(authorizationUrl)) {
      throw new Error("authorization URL is unsafe");
    }
    const expectedState = new URL(authorizationUrl).searchParams.get("state");
    if (!expectedState) throw new Error("authorization state is missing");
    await deps.openExternal(authorizationUrl);
    const result = await Promise.race([
      delivered,
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(
          () => reject(new Error("authorization timed out")),
          timeoutMs,
        );
      }),
    ]);
    if (result.state !== expectedState) {
      throw new Error("authorization state mismatch");
    }
    return result;
  } finally {
    if (timer !== null) clearTimeout(timer);
    await listener.close();
  }
}
