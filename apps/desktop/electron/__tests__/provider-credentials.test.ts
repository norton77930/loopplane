// Provider credential vault (Unit A). The credential is the one value in this
// app that must never reach the renderer, an RPC payload, a log, or a backup,
// so these tests pin the shape of what leaves the module rather than only the
// happy path.

import { describe, expect, it } from "vitest";

import {
  DESKTOP_PROVIDER_IDS,
  PROVIDER_ENV,
  clearProviderConfig,
  keyHint,
  providerSpawnEnv,
  publicProviderView,
  readProviderConfig,
  writeProviderConfig,
  type CredentialFileIo,
  type CredentialVault,
} from "../provider-credentials";

const FAKE_KEY = "sk-ant-api03-abcdefghijklmnop4f2a";
const USER_DATA = "/userData";

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

describe("provider identity", () => {
  it("offers the same provider ids the sidecar knows", () => {
    expect([...DESKTOP_PROVIDER_IDS]).toEqual([
      "anthropic",
      "openai",
      "gemini",
      "openrouter",
      "ollama",
    ]);
  });

  it("names the same environment variables the sidecar reads", () => {
    expect(PROVIDER_ENV).toEqual({
      provider: "LOOPPLANE_DESKTOP_PROVIDER",
      modelId: "LOOPPLANE_DESKTOP_MODEL_ID",
      key: "LOOPPLANE_DESKTOP_API_KEY",
    });
  });
});

describe("keyHint", () => {
  it("reveals only the last four characters", () => {
    expect(keyHint(FAKE_KEY)).toBe("…4f2a");
  });

  it("reveals nothing for a short or absent key", () => {
    expect(keyHint(null)).toBeNull();
    expect(keyHint("")).toBeNull();
    expect(keyHint("abcd")).toBe("…");
  });
});

describe("publicProviderView", () => {
  it("never carries the key", () => {
    const view = publicProviderView({
      provider: "anthropic",
      modelId: "claude-x",
      apiKey: FAKE_KEY,
    });

    expect(view).toEqual({
      provider: "anthropic",
      modelId: "claude-x",
      hasKey: true,
      keyHint: "…4f2a",
    });
    expect(JSON.stringify(view)).not.toContain(FAKE_KEY);
  });

  it("reports a keyless provider honestly", () => {
    expect(
      publicProviderView({ provider: "ollama", modelId: "llama3", apiKey: null }),
    ).toEqual({
      provider: "ollama",
      modelId: "llama3",
      hasKey: false,
      keyHint: null,
    });
  });
});

describe("writeProviderConfig", () => {
  it("encrypts, writes a temp file, then renames", () => {
    const io = fakeIo();

    const result = writeProviderConfig(
      { vault: fakeVault(), io, userDataDir: USER_DATA },
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    );

    expect(result).toEqual({ ok: true });
    const written = Object.values(io.files)[0]!.toString("utf8");
    expect(written.startsWith("enc:")).toBe(true);
    const tempWrite = io.calls.find((c) => c.startsWith("write:"))!;
    expect(tempWrite.endsWith(".tmp")).toBe(true);
    const rename = io.calls.find((c) => c.startsWith("rename:"))!;
    expect(rename).toMatch(/\.tmp->.*provider-credential\.bin$/);
    // Nothing is left at the temp path once the rename lands.
    expect(Object.keys(io.files)).toEqual([
      expect.stringContaining("provider-credential.bin"),
    ]);
    expect(Object.keys(io.files)[0]!.endsWith(".tmp")).toBe(false);
  });

  it("refuses to store anything when OS encryption is unavailable", () => {
    const io = fakeIo();

    const result = writeProviderConfig(
      { vault: fakeVault(false), io, userDataDir: USER_DATA },
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    );

    expect(result).toEqual({ ok: false, reason: "encryption_unavailable" });
    expect(Object.keys(io.files)).toHaveLength(0);
  });

  it.each([
    ["not-a-provider", "claude-x", FAKE_KEY, "invalid_provider"],
    ["anthropic", "  ", FAKE_KEY, "invalid_model_id"],
    ["anthropic", "claude-x", "   ", "missing_key"],
    ["anthropic", "claude-x", null, "missing_key"],
  ])(
    "rejects %s/%s with %s",
    (provider, modelId, apiKey, reason) => {
      const io = fakeIo();

      const result = writeProviderConfig(
        { vault: fakeVault(), io, userDataDir: USER_DATA },
        { provider, modelId, apiKey: apiKey as string | null },
      );

      expect(result).toEqual({ ok: false, reason });
      expect(Object.keys(io.files)).toHaveLength(0);
    },
  );

  it("reuses the stored key when only the model changes", () => {
    const io = fakeIo();
    const deps = { vault: fakeVault(), io, userDataDir: USER_DATA };
    writeProviderConfig(deps, {
      provider: "anthropic",
      modelId: "claude-old",
      apiKey: FAKE_KEY,
    });

    expect(
      writeProviderConfig(deps, {
        provider: "anthropic",
        modelId: "claude-new",
        apiKey: null,
      }),
    ).toEqual({ ok: true });
    expect(readProviderConfig(deps)).toEqual({
      provider: "anthropic",
      modelId: "claude-new",
      apiKey: FAKE_KEY,
    });
  });

  it("will not carry a key across a provider change", () => {
    const io = fakeIo();
    const deps = { vault: fakeVault(), io, userDataDir: USER_DATA };
    writeProviderConfig(deps, {
      provider: "anthropic",
      modelId: "claude-x",
      apiKey: FAKE_KEY,
    });

    expect(
      writeProviderConfig(deps, {
        provider: "openai",
        modelId: "gpt-x",
        apiKey: null,
      }),
    ).toEqual({ ok: false, reason: "missing_key" });
    expect(readProviderConfig(deps)?.provider).toBe("anthropic");
  });

  it("stores a keyless provider without a key", () => {
    const io = fakeIo();

    expect(
      writeProviderConfig(
        { vault: fakeVault(), io, userDataDir: USER_DATA },
        { provider: "ollama", modelId: "llama3", apiKey: null },
      ),
    ).toEqual({ ok: true });
  });

  it("cleans up the temp file when the rename fails", () => {
    const io = fakeIo();
    io.rename = () => {
      throw new Error("EXDEV");
    };

    const result = writeProviderConfig(
      { vault: fakeVault(), io, userDataDir: USER_DATA },
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    );

    expect(result).toEqual({ ok: false, reason: "write_failed" });
    expect(Object.keys(io.files)).toHaveLength(0);
  });

  it("reports a write failure with a fixed reason and no raw error text", () => {
    const io = fakeIo();
    io.writeFile = () => {
      throw new Error(`disk on fire at ${USER_DATA}`);
    };

    const result = writeProviderConfig(
      { vault: fakeVault(), io, userDataDir: USER_DATA },
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    );

    expect(result).toEqual({ ok: false, reason: "write_failed" });
  });
});

describe("readProviderConfig", () => {
  function stored(): Record<string, Buffer> {
    const io = fakeIo();
    writeProviderConfig(
      { vault: fakeVault(), io, userDataDir: USER_DATA },
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    );
    return io.files;
  }

  it("round-trips what was written", () => {
    const io = fakeIo(stored());

    expect(
      readProviderConfig({ vault: fakeVault(), io, userDataDir: USER_DATA }),
    ).toEqual({ provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY });
  });

  it("returns null when nothing is stored", () => {
    expect(
      readProviderConfig({ vault: fakeVault(), io: fakeIo(), userDataDir: USER_DATA }),
    ).toBeNull();
  });

  it.each([
    ["undecryptable bytes", Buffer.from("plain garbage", "utf8")],
    ["encrypted non-JSON", Buffer.from("enc:not json", "utf8")],
    [
      "an unknown provider",
      Buffer.from(
        `enc:${JSON.stringify({ v: 1, provider: "nope", modelId: "m", apiKey: FAKE_KEY })}`,
        "utf8",
      ),
    ],
  ])("returns null for %s instead of throwing", (_label, bytes) => {
    const io = fakeIo({ [`${USER_DATA}/provider-credential.bin`]: bytes });

    expect(
      readProviderConfig({ vault: fakeVault(), io, userDataDir: USER_DATA }),
    ).toBeNull();
  });
});

describe("clearProviderConfig", () => {
  it("removes the stored credential", () => {
    const io = fakeIo();
    writeProviderConfig(
      { vault: fakeVault(), io, userDataDir: USER_DATA },
      { provider: "anthropic", modelId: "claude-x", apiKey: FAKE_KEY },
    );

    clearProviderConfig({ vault: fakeVault(), io, userDataDir: USER_DATA });

    expect(Object.keys(io.files)).toHaveLength(0);
  });

  it("also removes ciphertext left by a crash between write and rename", () => {
    // Derive the paths from a real write: `path.join` uses the host separator,
    // so a hand-written "/userData/..." key would never match on Windows.
    const io = fakeIo();
    const deps = { vault: fakeVault(), io, userDataDir: USER_DATA };
    writeProviderConfig(deps, {
      provider: "anthropic",
      modelId: "claude-x",
      apiKey: FAKE_KEY,
    });
    const target = Object.keys(io.files)[0]!;
    io.files[`${target}.tmp`] = io.files[target]!;
    delete io.files[target];

    clearProviderConfig(deps);

    expect(Object.keys(io.files)).toHaveLength(0);
  });

  it("is idempotent when nothing is stored", () => {
    const io = fakeIo();

    expect(() =>
      clearProviderConfig({ vault: fakeVault(), io, userDataDir: USER_DATA }),
    ).not.toThrow();
  });
});

describe("providerSpawnEnv", () => {
  it("carries the configuration to the sidecar", () => {
    expect(
      providerSpawnEnv({
        provider: "anthropic",
        modelId: "claude-x",
        apiKey: FAKE_KEY,
      }),
    ).toEqual({
      LOOPPLANE_DESKTOP_PROVIDER: "anthropic",
      LOOPPLANE_DESKTOP_MODEL_ID: "claude-x",
      LOOPPLANE_DESKTOP_API_KEY: FAKE_KEY,
    });
  });

  it("omits the key entirely for a keyless provider", () => {
    const env = providerSpawnEnv({
      provider: "ollama",
      modelId: "llama3",
      apiKey: null,
    });

    expect(env.LOOPPLANE_DESKTOP_API_KEY).toBeUndefined();
    expect(env.LOOPPLANE_DESKTOP_PROVIDER).toBe("ollama");
  });

  it("yields nothing when no provider is configured", () => {
    expect(providerSpawnEnv(null)).toEqual({});
  });
});
