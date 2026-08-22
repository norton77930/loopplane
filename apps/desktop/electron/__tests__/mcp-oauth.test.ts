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
  vaultKey,
  writeMcpAuthorization,
  type McpVaultDeps,
} from "../mcp-oauth-vault";
import {
  runAuthorization,
  type RedirectHandler,
  type RedirectListener,
} from "../mcp-oauth-flow";
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
      async () => "https://idp.example/authorize",
    );
    await vi.waitFor(() => expect(listener.deliver).not.toBeNull());
    listener.deliver!(new URLSearchParams("error=access_denied"));

    await expect(promise).rejects.toThrow("not granted");
    expect(listener.closed).toBe(1);
  });

  it("closes the listener on timeout", async () => {
    const listener = fakeListen();
    await expect(
      runAuthorization(
        { openExternal: async () => {}, listen: listener.listen, timeoutMs: 1 },
        async () => "https://idp.example/authorize",
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
});
