// The provider credential vault (Unit A): the Electron main process owns the
// user's API key, encrypts it with the OS keystore through Electron's
// `safeStorage`, and hands it to the sidecar as a spawn environment variable.
//
// Two placement decisions carry the safety here:
//
//   * The blob lives under `app.getPath("userData")`, deliberately NOT under the
//     LoopPlane profile root. Backups read the profile through a whitelist
//     (`sidecar/archive.py`), so a credential outside it cannot reach an archive
//     by construction — the `"credentials"` exclusion already disclosed in
//     `sidecar/backup.py` stays true without any backup-side rule.
//   * The renderer is never given the key. Only `publicProviderView` crosses the
//     IPC boundary, and it carries a hint of the last four characters at most.
//
// Pure like `sidecar-spawn.ts`: it imports no `electron`, so it is unit-testable;
// `main.ts` supplies the Electron-provided vault and the userData directory.

import { mkdirSync, existsSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

/** Provider ids, in the same order and spelling the sidecar's table uses. */
export const DESKTOP_PROVIDER_IDS = [
  "anthropic",
  "openai",
  "gemini",
  "openrouter",
  "ollama",
] as const;

export type DesktopProviderId = (typeof DESKTOP_PROVIDER_IDS)[number];

/** The only provider that reaches a local daemon and needs no credential. */
const KEYLESS_PROVIDERS: ReadonlySet<string> = new Set(["ollama"]);

/**
 * The variables `select_desktop_model` reads in `apps/desktop/sidecar/bridge.py`.
 * `tests/contract/test_desktop_provider_env.py` pins both sides to this shape.
 */
export const PROVIDER_ENV = {
  provider: "LOOPPLANE_DESKTOP_PROVIDER",
  modelId: "LOOPPLANE_DESKTOP_MODEL_ID",
  key: "LOOPPLANE_DESKTOP_API_KEY",
} as const;

const CREDENTIAL_FILE = "provider-credential.bin";
const TEMP_SUFFIX = ".tmp";
const FORMAT_VERSION = 1;

export interface ProviderConfig {
  provider: string;
  modelId: string;
  apiKey: string | null;
}

/** The only projection allowed to leave the main process. */
export interface PublicProviderView {
  provider: string;
  modelId: string;
  hasKey: boolean;
  keyHint: string | null;
}

export type SaveFailureReason =
  | "encryption_unavailable"
  | "invalid_provider"
  | "invalid_model_id"
  | "missing_key"
  | "write_failed";

export type SaveResult = { ok: true } | { ok: false; reason: SaveFailureReason };

/** Electron's `safeStorage`, narrowed to what this module uses. */
export interface CredentialVault {
  isEncryptionAvailable(): boolean;
  encryptString(plain: string): Buffer;
  decryptString(encrypted: Buffer): string;
}

export interface CredentialFileIo {
  exists(target: string): boolean;
  readFile(target: string): Buffer;
  writeFile(target: string, data: Buffer): void;
  rename(from: string, to: string): void;
  unlink(target: string): void;
  mkdir(dir: string): void;
}

export interface VaultDeps {
  vault: CredentialVault;
  io: CredentialFileIo;
  userDataDir: string;
}

/** The default `node:fs` implementation; `main.ts` uses this one. */
export function nodeCredentialFileIo(): CredentialFileIo {
  return {
    exists: (target) => existsSync(target),
    readFile: (target) => readFileSync(target),
    // 0o600 / 0o700 are a POSIX-only defence in depth; Node ignores mode on
    // win32, where the real protection is the DPAPI-backed ciphertext.
    writeFile: (target, data) => writeFileSync(target, data, { mode: 0o600 }),
    rename: (from, to) => renameSync(from, to),
    unlink: (target) => rmSync(target, { force: true }),
    mkdir: (dir) => mkdirSync(dir, { recursive: true, mode: 0o700 }),
  };
}

function credentialPath(userDataDir: string): string {
  return path.join(userDataDir, CREDENTIAL_FILE);
}

function isKnownProvider(provider: string): boolean {
  return (DESKTOP_PROVIDER_IDS as readonly string[]).includes(provider);
}

function requiresKey(provider: string): boolean {
  return !KEYLESS_PROVIDERS.has(provider);
}

/**
 * The last four characters of a key, and nothing else — enough for the user to
 * recognize which key is stored, too little to reconstruct it. A key of four
 * characters or fewer reveals no tail at all.
 */
export function keyHint(apiKey: string | null | undefined): string | null {
  const trimmed = (apiKey ?? "").trim();
  if (!trimmed) return null;
  return trimmed.length > 4 ? `…${trimmed.slice(-4)}` : "…";
}

export function publicProviderView(
  config: ProviderConfig | null,
): PublicProviderView | null {
  if (config === null) return null;
  const key = (config.apiKey ?? "").trim();
  return {
    provider: config.provider,
    modelId: config.modelId,
    hasKey: key.length > 0,
    keyHint: keyHint(key),
  };
}

/** The spawn environment for a configured provider; `{}` when unconfigured. */
export function providerSpawnEnv(
  config: ProviderConfig | null,
): Record<string, string> {
  if (config === null) return {};
  const env: Record<string, string> = {
    [PROVIDER_ENV.provider]: config.provider,
    [PROVIDER_ENV.modelId]: config.modelId,
  };
  const key = (config.apiKey ?? "").trim();
  if (key) env[PROVIDER_ENV.key] = key;
  return env;
}

export function writeProviderConfig(
  deps: VaultDeps,
  input: ProviderConfig,
): SaveResult {
  const provider = (input.provider ?? "").trim();
  if (!isKnownProvider(provider)) return { ok: false, reason: "invalid_provider" };
  const modelId = (input.modelId ?? "").trim();
  if (!modelId) return { ok: false, reason: "invalid_model_id" };
  let apiKey = (input.apiKey ?? "").trim();
  if (requiresKey(provider) && !apiKey) {
    // Changing only the model should not require retyping a long key. Reuse is
    // scoped to the same provider: a key is provider-specific, so switching
    // provider always demands a new one.
    const existing = readProviderConfig(deps);
    apiKey =
      existing && existing.provider === provider ? (existing.apiKey ?? "") : "";
    if (!apiKey) return { ok: false, reason: "missing_key" };
  }
  // Refuse before touching disk: a plaintext fallback is never acceptable here.
  if (!deps.vault.isEncryptionAvailable()) {
    return { ok: false, reason: "encryption_unavailable" };
  }

  const target = credentialPath(deps.userDataDir);
  const temp = `${target}${TEMP_SUFFIX}`;
  try {
    deps.io.mkdir(deps.userDataDir);
    const payload = JSON.stringify({
      v: FORMAT_VERSION,
      provider,
      modelId,
      apiKey: apiKey || null,
    });
    // Write-then-rename so a crash mid-write cannot leave a half credential that
    // reads as a different provider.
    deps.io.writeFile(temp, deps.vault.encryptString(payload));
    deps.io.rename(temp, target);
  } catch {
    // A fixed reason only: the raw error can name a path or an OS detail.
    try {
      deps.io.unlink(temp);
    } catch {
      /* the temp file may never have been created */
    }
    return { ok: false, reason: "write_failed" };
  }
  return { ok: true };
}

/** The stored configuration, or `null` for anything unreadable. Never throws. */
export function readProviderConfig(deps: VaultDeps): ProviderConfig | null {
  const target = credentialPath(deps.userDataDir);
  if (!deps.io.exists(target)) return null;
  try {
    const decrypted = deps.vault.decryptString(deps.io.readFile(target));
    const parsed: unknown = JSON.parse(decrypted);
    if (typeof parsed !== "object" || parsed === null) return null;
    const record = parsed as Record<string, unknown>;
    const provider = typeof record.provider === "string" ? record.provider : "";
    const modelId = typeof record.modelId === "string" ? record.modelId : "";
    const apiKey = typeof record.apiKey === "string" ? record.apiKey : null;
    if (!isKnownProvider(provider) || !modelId) return null;
    if (requiresKey(provider) && !apiKey) return null;
    return { provider, modelId, apiKey };
  } catch {
    return null;
  }
}

export function clearProviderConfig(deps: VaultDeps): void {
  const target = credentialPath(deps.userDataDir);
  // The temp file too: a crash between write and rename leaves ciphertext
  // behind, and "Remove" has to mean the key material is gone.
  for (const path of [target, `${target}${TEMP_SUFFIX}`]) {
    try {
      deps.io.unlink(path);
    } catch {
      /* already absent */
    }
  }
}
