// MCP authorization vault + flow (unit 084; ADR 0019 D6).
//
// Desktop is where the credential actually becomes durable, so these tests pin what
// leaves the module rather than only the happy path: the refusal when the OS
// keystore is unavailable, the placement outside the profile root, the projection
// that carries no value, and the listener that is always closed.

import { describe, expect, it, vi } from "vitest";

import {
  clearMcpAuthorizations,
  discardMcpAuthorization,
  publicMcpView,
  readMcpAuthorization,
  readMcpAuthorizationEntry,
  vaultKey,
  writeMcpAuthorization,
  type McpVaultDeps,
} from "../mcp-oauth-vault";
import {
  runAuthorization,
  type RedirectHandler,
  type RedirectListener,
} from "../mcp-oauth-flow";
import {
  McpMaterialSyncCoordinator,
  McpOAuthController,
  mcpNotificationMayRefresh,
} from "../mcp-oauth-controller";
import type { CredentialFileIo, CredentialVault } from "../provider-credentials";

const USER_DATA = "/userData";
const MATERIAL = "sk-live-084-desktop-sentinel-not-a-real-credential";

/** A vault that "encrypts" by tagging, so a leak of plaintext is visible. */
function fakeVault(available = true): CredentialVault {
  return {
    isEncryptionAvailable: () => available,
    encryptString: (plain) => Buffer.from(`enc:${plain}`, "utf8"),
    decryptString: (buf) => {
      const raw = buf.toString("utf8");
      if (!raw.startsWith("enc:")) throw new Error("not encrypted");
      return raw.slice(4);
    },
  };
}

function fakeIo(seed: Record<string, Buffer> = {}): CredentialFileIo & {
  files: Record<string, Buffer>;
  calls: string[];
} {
  const files: Record<string, Buffer> = { ...seed };
  const calls: string[] = [];
  return {
    files,
    calls,
    exists: (p) => p in files,
    readFile: (p) => {
      if (!(p in files)) throw new Error("ENOENT");
      return files[p]!;
    },
    writeFile: (p, data) => {
      calls.push(`write:${p}`);
      files[p] = data;
    },
    rename: (from, to) => {
      calls.push(`rename:${from}->${to}`);
      files[to] = files[from]!;
      delete files[from];
    },
    unlink: (p) => {
      calls.push(`unlink:${p}`);
      delete files[p];
    },
    mkdir: (p) => {
      calls.push(`mkdir:${p}`);
    },
  };
}

function deps(available = true, seed: Record<string, Buffer> = {}): McpVaultDeps & {
  io: ReturnType<typeof fakeIo>;
} {
  return { vault: fakeVault(available), io: fakeIo(seed), userDataDir: USER_DATA };
}

describe("vault storage", () => {
  it("round-trips the material version used for refresh write-back", () => {
    const d = deps();
    expect(writeMcpAuthorization(d, "alice", "docs", MATERIAL, "etag-1")).toEqual({
      ok: true,
    });
    expect(readMcpAuthorizationEntry(d, "alice", "docs")).toEqual({
      material: MATERIAL,
      version: "etag-1",
    });
  });

  it("round-trips material for one (principal, server)", () => {
    const d = deps();
    expect(writeMcpAuthorization(d, "alice", "docs", MATERIAL)).toEqual({ ok: true });
    expect(readMcpAuthorization(d, "alice", "docs")).toBe(MATERIAL);
  });

  it("isolates by principal and by server", () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL);
    expect(readMcpAuthorization(d, "bob", "docs")).toBeNull();
    expect(readMcpAuthorization(d, "alice", "other")).toBeNull();
    expect(readMcpAuthorization(d, null, "docs")).toBeNull();
  });

  it("cannot be confused by a name containing the separator", () => {
    // principal "a:b" + server "c" must not collide with principal "a" +
    // server "b:c". Unit 059's review found this class of bug for real.
    expect(vaultKey("a:b", "c")).not.toBe(vaultKey("a", "b:c"));
  });

  it("refuses to store anything when the OS keystore is unavailable", () => {
    const d = deps(false);
    expect(writeMcpAuthorization(d, "alice", "docs", MATERIAL)).toEqual({
      ok: false,
      reason: "encryption_unavailable",
    });
    // The refusal must be total: no plaintext fallback, no partial file.
    expect(Object.keys(d.io.files)).toEqual([]);
  });

  it("stores outside the LoopPlane profile root, under userData", () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL);
    const [stored] = Object.keys(d.io.files);
    // Separator-agnostic: path.join yields backslashes on win32 and the app ships
    // on all three platforms, so asserting on "/userData" would pass only on POSIX.
    expect(stored).toContain("userData");
    expect(stored).toContain("mcp-authorization.bin");
    // A backup assembles the profile through a whitelist, so material placed here
    // cannot reach an archive by construction (ADR 0019 D6).
    expect(stored).not.toContain("profile");
  });

  it("never writes material in the clear", () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL);
    const written = Object.values(d.io.files)
      .map((b) => b.toString("utf8"))
      .join("");
    expect(written).toContain("enc:");
    expect(written.replace(/^enc:/, "")).toContain(MATERIAL); // inside the ciphertext
    expect(written.startsWith(MATERIAL)).toBe(false);
  });

  it("writes then renames, so a crash cannot leave half a document", () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL);
    const order = d.io.calls.join(" ");
    expect(order.indexOf("write:")).toBeLessThan(order.indexOf("rename:"));
  });

  it("treats an unreadable vault as empty rather than throwing", () => {
    const d = deps(true, { [`${USER_DATA}/mcp-authorization.bin`]: Buffer.from("junk") });
    expect(readMcpAuthorization(d, "alice", "docs")).toBeNull();
  });
});

describe("sign-out", () => {
  it("discards material and leaves the rest alone", () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL);
    writeMcpAuthorization(d, "alice", "other", "second");
    expect(discardMcpAuthorization(d, "alice", "docs")).toEqual({ ok: true });
    expect(readMcpAuthorization(d, "alice", "docs")).toBeNull();
    expect(readMcpAuthorization(d, "alice", "other")).toBe("second");
  });

  it("succeeds for material that was never stored, revealing nothing", () => {
    const d = deps();
    expect(discardMcpAuthorization(d, "nobody", "docs")).toEqual({ ok: true });
  });

  it("clears the temp file too", () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL);
    // Derive the temp path from the real one rather than rebuilding it with a
    // literal separator, which would only match on POSIX.
    const [stored] = Object.keys(d.io.files);
    d.io.files[`${stored}.tmp`] = Buffer.from("enc:leftover");
    clearMcpAuthorizations(d);
    expect(Object.keys(d.io.files)).toEqual([]);
  });
});

describe("renderer projection", () => {
  it("carries a state and no fragment of any value", () => {
    const view = publicMcpView("docs", "interactive", "authorized");
    expect(view).toEqual({ server: "docs", mode: "interactive", state: "authorized" });
    expect(JSON.stringify(view)).not.toContain(MATERIAL);
    // ADR 0016's provider view allows a four-character hint; nothing here needs
    // one, because a server is already identified by its own name.
    expect(Object.keys(view)).toEqual(["server", "mode", "state"]);
  });
});

describe("authorization flow", () => {
  function fakeListen(): {
    listen: (h: RedirectHandler) => Promise<RedirectListener>;
    deliver: RedirectHandler | null;
    closed: number;
  } {
    const state = {
      deliver: null as RedirectHandler | null,
      closed: 0,
      listen: async (handler: RedirectHandler): Promise<RedirectListener> => {
        state.deliver = handler;
        return {
          redirectUri: "http://127.0.0.1:7842/callback",
          close: async () => {
            state.closed += 1;
          },
        };
      },
    };
    return state;
  }

  it("opens the browser and resolves with what the redirect delivered", async () => {
    const listener = fakeListen();
    const openExternal = vi.fn(async () => {});
    const promise = runAuthorization(
      { openExternal, listen: listener.listen },
      async (redirectUri) => {
        expect(redirectUri).toBe("http://127.0.0.1:7842/callback");
        return "https://idp.example/authorize?state=xyz";
      },
    );
    await vi.waitFor(() => expect(listener.deliver).not.toBeNull());
    listener.deliver!(new URLSearchParams("code=abc&state=xyz"));

    await expect(promise).resolves.toEqual({ code: "abc", state: "xyz" });
    expect(openExternal).toHaveBeenCalledWith("https://idp.example/authorize?state=xyz");
    expect(listener.closed).toBe(1);
  });

  it("fails fast when the user denies, instead of waiting out the timeout", async () => {
    const listener = fakeListen();
    const promise = runAuthorization(
      { openExternal: async () => {}, listen: listener.listen, timeoutMs: 60_000 },
      async () => "https://idp.example/authorize?state=denied",
    );
    await vi.waitFor(() => expect(listener.deliver).not.toBeNull());
    listener.deliver!(new URLSearchParams("error=access_denied"));

    await expect(promise).rejects.toThrow("not granted");
    expect(listener.closed).toBe(1);
  });

  it("rejects a callback whose state does not match the authorization URL", async () => {
    const listener = fakeListen();
    const promise = runAuthorization(
      { openExternal: async () => {}, listen: listener.listen },
      async () => "https://idp.example/authorize?state=expected",
    );
    await vi.waitFor(() => expect(listener.deliver).not.toBeNull());
    listener.deliver!(new URLSearchParams("code=abc&state=wrong"));

    await expect(promise).rejects.toThrow("state mismatch");
    expect(listener.closed).toBe(1);
  });

  it("closes the listener on timeout", async () => {
    const listener = fakeListen();
    await expect(
      runAuthorization(
        { openExternal: async () => {}, listen: listener.listen, timeoutMs: 1 },
        async () => "https://idp.example/authorize?state=timeout",
      ),
    ).rejects.toThrow("timed out");
    // A port left bound per abandoned login would accumulate for the life of the app.
    expect(listener.closed).toBe(1);
  });

  it("closes the listener when the authorization url cannot be built", async () => {
    const listener = fakeListen();
    await expect(
      runAuthorization({ openExternal: async () => {}, listen: listener.listen }, async () => {
        throw new Error("discovery failed");
      }),
    ).rejects.toThrow("discovery failed");
    expect(listener.closed).toBe(1);
  });

  it("refuses a non-web authorization URL before opening it", async () => {
    const listener = fakeListen();
    const openExternal = vi.fn(async () => {});
    await expect(
      runAuthorization(
        { openExternal, listen: listener.listen, timeoutMs: 1 },
        async () => "file:///untrusted-handler",
      ),
    ).rejects.toThrow("unsafe");
    expect(openExternal).not.toHaveBeenCalled();
    expect(listener.closed).toBe(1);
  });
});

describe("main-owned authorization controller", () => {
  it("recognizes tool completion and outcome as refresh write-back boundaries", () => {
    expect(
      mcpNotificationMayRefresh("runtime.event", {
        event: { type: "tool-call-completed" },
      }),
    ).toBe(true);
    expect(mcpNotificationMayRefresh("runtime.outcome", {})).toBe(true);
    expect(
      mcpNotificationMayRefresh("runtime.event", {
        event: { type: "text-delta" },
      }),
    ).toBe(false);
  });

  it("replays a refresh sync trigger that arrives while one is running", async () => {
    let releaseFirst: (() => void) | null = null;
    let calls = 0;
    const coordinator = new McpMaterialSyncCoordinator(async () => {
      calls += 1;
      if (calls === 1) {
        await new Promise<void>((resolve) => {
          releaseFirst = resolve;
        });
      }
    });

    coordinator.trigger();
    await vi.waitFor(() => expect(calls).toBe(1));
    coordinator.trigger();
    releaseFirst!();
    await coordinator.flush();

    expect(calls).toBe(2);
  });

  it("clears durable material when a mid-session refresh fails closed", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL, "etag-old");
    const methods: string[] = [];
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("not used");
      },
      rpc: {
        newMutationId: () => "mutation-refresh-failed",
        request: async (method) => {
          methods.push(method);
          if (method === "mcp.list") {
            return {
              items: [
                {
                  id: "docs",
                  authorization: {
                    server: "docs",
                    mode: "interactive",
                    state: "authorized",
                  },
                },
              ],
            };
          }
          if (method === "mcp.material") {
            return { principal: "alice", material: null, version: null };
          }
          if (method === "mcp.disconnect") return { ok: true };
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await controller.syncAll();

    expect(readMcpAuthorization(d, "alice", "docs")).toBeNull();
    expect(methods).toEqual([
      "mcp.list",
      "mcp.material",
      "mcp.material",
      "mcp.disconnect",
    ]);
  });

  it("contains refresh write-back failure to one server", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "good", "old-good", "etag-old");
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("not used");
      },
      rpc: {
        newMutationId: () => "mutation-contained-sync",
        request: async (method, params = {}) => {
          const values = params as Record<string, unknown>;
          if (method === "mcp.list") {
            return {
              items: ["bad", "good"].map((server) => ({
                id: server,
                authorization: {
                  server,
                  mode: "interactive",
                  state: "authorized",
                },
              })),
            };
          }
          if (method === "mcp.material" && values.mcp_id === "bad") {
            throw new Error("bad server unavailable");
          }
          if (method === "mcp.material" && !("known_version" in values)) {
            return { principal: "alice", material: null, version: null };
          }
          if (method === "mcp.material") {
            return {
              principal: "alice",
              material: "rotated-good",
              version: "etag-new",
            };
          }
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await expect(controller.syncAll()).resolves.toBeUndefined();
    expect(readMcpAuthorization(d, "alice", "good")).toBe("rotated-good");
  });

  it("waits for a human-scale authorization flow beyond twenty seconds", async () => {
    const d = deps();
    let statusCalls = 0;
    const controller = new McpOAuthController({
      vault: d,
      sleep: async () => {},
      authorize: async (begin) => {
        expect(await begin("http://127.0.0.1:7842/callback")).toContain("idp.example");
        return { code: "code-084", state: "state-084" };
      },
      rpc: {
        newMutationId: () => "mutation-slow-human",
        request: async (method) => {
          if (method === "mcp.get") {
            return {
              authorization: {
                server: "docs",
                mode: "interactive",
                state: "needs_authorization",
              },
            };
          }
          if (method === "mcp.material") {
            return { principal: "alice", material: null, version: null };
          }
          if (method === "mcp.authorize") return { request_id: "request-slow" };
          if (method === "mcp.authorize_status") {
            statusCalls += 1;
            if (statusCalls <= 401) return { state: "awaiting" };
            if (statusCalls === 402) {
              return { state: "awaiting", url: "https://idp.example/authorize" };
            }
            return {
              state: "authorized",
              principal: "alice",
              material: MATERIAL,
              version: "etag-slow",
            };
          }
          if (method === "mcp.authorize_complete") return { ok: true };
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await expect(controller.reconnect("docs")).resolves.toEqual({ ok: true });
    expect(statusCalls).toBe(403);
  });

  it("discards the old endpoint's durable material on a successful upsert", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL, "etag-old");
    const request = vi.fn(async (method: string, params?: unknown) => {
      if (method === "mcp.upsert") {
        expect(params).toMatchObject({ name: "docs" });
        return { ok: true, message: "saved", authorization_reset: true };
      }
      if (method === "mcp.material") {
        return { principal: "alice", material: null, version: null };
      }
      throw new Error(`unexpected ${method}`);
    });
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("not used");
      },
      rpc: { newMutationId: () => "mutation-upsert", request },
    });

    await expect(
      controller.upsert({
        name: "  docs  ",
        transport: "http",
        url: "https://new.example/mcp",
        authorization: "interactive",
      }),
    ).resolves.toEqual({ ok: true, message: "saved" });
    expect(readMcpAuthorization(d, "alice", "docs")).toBeNull();
  });

  it("persists interactive material without returning it to the renderer", async () => {
    const d = deps();
    let statusCalls = 0;
    const calls: Array<[string, Record<string, unknown>]> = [];
    const controller = new McpOAuthController({
      vault: d,
      sleep: async () => {},
      authorize: async (begin) => {
        expect(await begin("http://127.0.0.1:7842/callback")).toContain(
          "idp.example",
        );
        return { code: "code-084", state: "state-084" };
      },
      rpc: {
        newMutationId: () => "mutation-084",
        request: async (method, params = {}) => {
          calls.push([method, params as Record<string, unknown>]);
          if (method === "mcp.get") {
            return {
              authorization: {
                server: "docs",
                mode: "interactive",
                state: "needs_authorization",
              },
            };
          }
          if (method === "mcp.material") {
            return { principal: "alice", material: null, version: null };
          }
          if (method === "mcp.authorize") return { request_id: "request-084" };
          if (method === "mcp.authorize_status") {
            statusCalls += 1;
            return statusCalls === 1
              ? { state: "awaiting", url: "https://idp.example/authorize" }
              : {
                  state: "authorized",
                  principal: "alice",
                  material: MATERIAL,
                  version: "etag-1",
                };
          }
          if (method === "mcp.authorize_complete") return { ok: true };
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await expect(controller.reconnect("docs")).resolves.toEqual({ ok: true });
    expect(readMcpAuthorizationEntry(d, "alice", "docs")).toEqual({
      material: MATERIAL,
      version: "etag-1",
    });
    expect(JSON.stringify(await controller.publicView("docs"))).not.toContain(MATERIAL);
    expect(calls.map(([method]) => method)).toEqual([
      "mcp.get",
      "mcp.material",
      "mcp.authorize",
      "mcp.authorize_status",
      "mcp.authorize_complete",
      "mcp.authorize_status",
      "mcp.get",
    ]);
  });

  it("writes a rotated refresh token back after silent reconnect", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", "old-material", "etag-old");
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("browser must not open");
      },
      rpc: {
        newMutationId: () => "mutation-refresh",
        request: async (method, params = {}) => {
          if (method === "mcp.get") {
            return {
              authorization: {
                server: "docs",
                mode: "interactive",
                state: "needs_authorization",
              },
            };
          }
          if (method === "mcp.reconnect") {
            expect(params).toMatchObject({ material: "old-material" });
            return { ok: true };
          }
          if (method === "mcp.material") {
            if (!("known_version" in (params as Record<string, unknown>))) {
              return { principal: "alice", material: null, version: null };
            }
            expect(params).toMatchObject({ known_version: "etag-old" });
            return {
              principal: "alice",
              material: "rotated-material",
              version: "etag-new",
            };
          }
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await controller.reconnect("docs");
    expect(readMcpAuthorizationEntry(d, "alice", "docs")).toEqual({
      material: "rotated-material",
      version: "etag-new",
    });
  });

  it("clears rejected saved material before starting interactive authorization", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL, "etag-old");
    let statusCalls = 0;
    const methods: string[] = [];
    const controller = new McpOAuthController({
      vault: d,
      sleep: async () => {},
      authorize: async (begin) => {
        expect(readMcpAuthorization(d, "alice", "docs")).toBeNull();
        await begin("http://127.0.0.1:7842/callback");
        return { code: "new-code", state: "new-state" };
      },
      rpc: {
        newMutationId: () => "mutation-rejected-refresh",
        request: async (method) => {
          methods.push(method);
          if (method === "mcp.get") {
            return {
              authorization: {
                server: "docs",
                mode: "interactive",
                state: "needs_authorization",
              },
            };
          }
          if (method === "mcp.material") {
            return { principal: "alice", material: null, version: null };
          }
          if (method === "mcp.reconnect") return { ok: false };
          if (method === "mcp.disconnect") return { ok: true };
          if (method === "mcp.authorize") return { request_id: "request-new" };
          if (method === "mcp.authorize_complete") return { ok: true };
          if (method === "mcp.authorize_status") {
            statusCalls += 1;
            return statusCalls === 1
              ? { state: "awaiting", url: "https://idp.example/authorize" }
              : {
                  state: "authorized",
                  principal: "alice",
                  material: "new-material",
                  version: "etag-new",
                };
          }
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await controller.reconnect("docs");

    expect(methods).toContain("mcp.disconnect");
    expect(readMcpAuthorization(d, "alice", "docs")).toBe("new-material");
  });

  it("restores saved sessions at startup without opening a browser", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL, "etag-1");
    const methods: string[] = [];
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("browser must not open");
      },
      rpc: {
        newMutationId: () => "mutation-restart",
        request: async (method, params = {}) => {
          methods.push(method);
          if (method === "mcp.list") {
            return {
              items: [
                {
                  id: "docs",
                  authorization: {
                    server: "docs",
                    mode: "interactive",
                    state: "needs_authorization",
                  },
                },
              ],
            };
          }
          if (
            method === "mcp.material" &&
            !("known_version" in (params as Record<string, unknown>))
          ) {
            return { principal: "alice", material: null, version: null };
          }
          if (method === "mcp.reconnect") {
            expect(params).toMatchObject({ material: MATERIAL });
            return { ok: true };
          }
          if (method === "mcp.material") {
            return { principal: "alice", material: null, version: "etag-1" };
          }
          throw new Error(`unexpected ${method}`);
        },
      },
    });

    await controller.restoreAll();
    expect(methods).toEqual([
      "mcp.list",
      "mcp.material",
      "mcp.reconnect",
      "mcp.material",
    ]);
  });

  it("signs out without deleting the configuration", async () => {
    const d = deps();
    writeMcpAuthorization(d, "alice", "docs", MATERIAL, "etag-1");
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("not used");
      },
      rpc: {
        newMutationId: () => "mutation-disconnect",
        request: async (method) => {
          if (method === "mcp.material") {
            return { principal: "alice", material: null, version: null };
          }
          expect(method).toBe("mcp.disconnect");
          return { ok: true };
        },
      },
    });

    await controller.disconnect("docs");
    expect(readMcpAuthorization(d, "alice", "docs")).toBeNull();
  });

  it("does not tell the sidecar to disconnect when durable discard fails", async () => {
    const seeded = deps();
    writeMcpAuthorization(seeded, "alice", "docs", MATERIAL, "etag-1");
    const d = deps(false, { ...seeded.io.files });
    const request = vi.fn(async (method: string) => {
      if (method === "mcp.material") {
        return { principal: "alice", material: null, version: null };
      }
      return { ok: true };
    });
    const controller = new McpOAuthController({
      vault: d,
      authorize: async () => {
        throw new Error("not used");
      },
      rpc: {
        newMutationId: () => "mutation-disconnect-failed",
        request,
      },
    });

    await expect(controller.disconnect("docs")).rejects.toThrow(
      "storage unavailable",
    );
    expect(request.mock.calls.map(([method]) => method)).toEqual([
      "mcp.material",
    ]);
  });
});
