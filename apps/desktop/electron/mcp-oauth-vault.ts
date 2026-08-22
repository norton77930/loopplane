// The MCP authorization vault (unit 084; ADR 0019 D6). Electron main owns every
// durable byte of OAuth material: the sidecar holds it only for as long as a
// connection needs it, and `src/loopplane` never writes it at all.
//
// The placement and the refusal are inherited from ADR 0016's provider vault,
// deliberately and for the same reasons:
//
//   * The blob lives under `app.getPath("userData")`, NOT under the LoopPlane
//     profile root. Backups assemble the profile through a whitelist
//     (`sidecar/archive.py`), so material stored outside it cannot reach an archive
//     by construction — no backup-side exclusion rule has to be remembered.
//   * When `safeStorage.isEncryptionAvailable()` is false, nothing is stored. A
//     plaintext fallback is not offered; a refused save is a worse day than a
//     silent plaintext credential is a worse year.
//
// Kept separate from `provider-credentials.ts` rather than folded into it: that
// file holds one credential for one provider, this one holds a growing map keyed by
// (principal, server), and a shared format would make both harder to reason about.
//
// Pure like `sidecar-spawn.ts` — it imports no `electron`, so it is unit-testable;
// `main.ts` supplies the Electron-provided vault and the userData directory.

import path from "node:path";

import {
  type CredentialFileIo,
  type CredentialVault,
} from "./provider-credentials";

const VAULT_FILE = "mcp-authorization.bin";
const TEMP_SUFFIX = ".tmp";
const FORMAT_VERSION = 1;

/** One server's authorization material, opaque to this module. */
export interface McpAuthorizationEntry {
  /** The sidecar's serialized material. Never inspected here. */
  material: string;
}

export type McpVaultFailure =
  | "encryption_unavailable"
  | "invalid_key"
  | "write_failed";

export type McpVaultResult = { ok: true } | { ok: false; reason: McpVaultFailure };

/** What may cross to the renderer: a state, never a value. */
export type McpAuthorizationState =
  | "authorized"
  | "needs_authorization"
  | "failed";

export interface PublicMcpAuthorizationView {
  server: string;
  mode: "none" | "interactive";
  state: McpAuthorizationState;
}

export interface McpVaultDeps {
  vault: CredentialVault;
  io: CredentialFileIo;
  userDataDir: string;
}

type VaultDocument = Record<string, McpAuthorizationEntry>;

function vaultPath(userDataDir: string): string {
  return path.join(userDataDir, VAULT_FILE);
}

/**
 * The storage key for one (principal, server) pair.
 *
 * Both halves are length-prefixed rather than joined by a separator: a principal
 * named `a:b` and a server named `c` must not collide with principal `a` and server
 * `b:c`. Unit 059's adversarial review found exactly this class of collision in the
 * resource-tool naming, so it is worth spending four characters to make impossible.
 */
export function vaultKey(principal: string | null, server: string): string {
  const p = principal ?? "";
  return `${p.length}:${p}|${server.length}:${server}`;
}

function readDocument(deps: McpVaultDeps): VaultDocument {
  const target = vaultPath(deps.userDataDir);
  if (!deps.io.exists(target)) return {};
  try {
    const parsed: unknown = JSON.parse(
      deps.vault.decryptString(deps.io.readFile(target)),
    );
    if (typeof parsed !== "object" || parsed === null) return {};
    const record = parsed as Record<string, unknown>;
    if (record.v !== FORMAT_VERSION) return {};
    const entries = record.entries;
    if (typeof entries !== "object" || entries === null) return {};
    const out: VaultDocument = {};
    for (const [key, value] of Object.entries(entries as Record<string, unknown>)) {
      if (
        typeof value === "object" &&
        value !== null &&
        typeof (value as Record<string, unknown>).material === "string"
      ) {
        out[key] = { material: (value as Record<string, unknown>).material as string };
      }
    }
    return out;
  } catch {
    // Unreadable is treated as empty: a corrupt vault must degrade to "authorize
    // again", never to a crash on launch.
    return {};
  }
}

function writeDocument(deps: McpVaultDeps, document: VaultDocument): McpVaultResult {
  if (!deps.vault.isEncryptionAvailable()) {
    return { ok: false, reason: "encryption_unavailable" };
  }
  const target = vaultPath(deps.userDataDir);
  const temp = `${target}${TEMP_SUFFIX}`;
  try {
    deps.io.mkdir(deps.userDataDir);
    const payload = JSON.stringify({ v: FORMAT_VERSION, entries: document });
    // Write-then-rename, so a crash mid-write cannot leave a half document that
    // decrypts into a different set of authorizations.
    deps.io.writeFile(temp, deps.vault.encryptString(payload));
    deps.io.rename(temp, target);
  } catch {
    // A fixed reason only: a raw error can name a path or an OS detail.
    try {
      deps.io.unlink(temp);
    } catch {
      /* the temp file may never have been created */
    }
    return { ok: false, reason: "write_failed" };
  }
  return { ok: true };
}

/** Stored material for one (principal, server), or `null`. Never throws. */
export function readMcpAuthorization(
  deps: McpVaultDeps,
  principal: string | null,
  server: string,
): string | null {
  if (!server) return null;
  return readDocument(deps)[vaultKey(principal, server)]?.material ?? null;
}

export function writeMcpAuthorization(
  deps: McpVaultDeps,
  principal: string | null,
  server: string,
  material: string,
): McpVaultResult {
  if (!server) return { ok: false, reason: "invalid_key" };
  const document = readDocument(deps);
  document[vaultKey(principal, server)] = { material };
  return writeDocument(deps, document);
}

/**
 * Forget one (principal, server). Succeeds when nothing was stored — a sign-out
 * must not double as a probe for whether a given principal ever authorized a
 * given server.
 */
export function discardMcpAuthorization(
  deps: McpVaultDeps,
  principal: string | null,
  server: string,
): McpVaultResult {
  const document = readDocument(deps);
  const key = vaultKey(principal, server);
  if (!(key in document)) return { ok: true };
  delete document[key];
  return writeDocument(deps, document);
}

/** Remove the whole vault, temp file included. */
export function clearMcpAuthorizations(deps: McpVaultDeps): void {
  const target = vaultPath(deps.userDataDir);
  for (const candidate of [target, `${target}${TEMP_SUFFIX}`]) {
    try {
      deps.io.unlink(candidate);
    } catch {
      /* already absent */
    }
  }
}

/**
 * The only projection allowed to leave the main process.
 *
 * ADR 0016's `PublicProviderView` permits a four-character hint so a user can
 * recognize which key is stored. Nothing here needs that: an MCP server is already
 * identified by its own name, so the projection carries no fragment of any value.
 */
export function publicMcpView(
  server: string,
  mode: "none" | "interactive",
  state: McpAuthorizationState,
): PublicMcpAuthorizationView {
  return { server, mode, state };
}
