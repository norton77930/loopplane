/** Main-process orchestration for Desktop MCP interactive OAuth (084). */

import type { McpAuthorizationResult } from "./mcp-oauth-flow";
import {
  discardMcpAuthorization,
  publicMcpView,
  readMcpAuthorizationEntry,
  writeMcpAuthorization,
  type McpVaultDeps,
  type PublicMcpAuthorizationView,
} from "./mcp-oauth-vault";

type RpcOptions = { mutationId?: string };

export interface McpOAuthRpc {
  request(method: string, params?: unknown, options?: RpcOptions): Promise<unknown>;
  newMutationId(): string;
}

export interface McpOAuthControllerDeps {
  rpc: McpOAuthRpc;
  vault: McpVaultDeps;
  authorize(
    begin: (redirectUri: string) => Promise<string>,
  ): Promise<McpAuthorizationResult>;
  sleep?(milliseconds: number): Promise<void>;
}

type AuthorizationView = PublicMcpAuthorizationView;
type MaterialReply = {
  principal: string | null;
  material: string | null;
  version: string | null;
};

const POLL_MS = 50;
// Keep main's polling window above the adapter's 300s human wait and its 315s
// interactive connection budget, but below the sidecar request's 360s lease.
const POLL_LIMIT = 6_600;

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("invalid MCP OAuth response");
  }
  return value as Record<string, unknown>;
}

function operationOk(value: unknown): boolean {
  return record(value).ok === true;
}

export function mcpNotificationMayRefresh(method: string, params: unknown): boolean {
  if (method === "runtime.outcome") return true;
  if (method !== "runtime.event" || params === null || typeof params !== "object") {
    return false;
  }
  const event = (params as Record<string, unknown>).event;
  return (
    event !== null &&
    typeof event === "object" &&
    (event as Record<string, unknown>).type === "tool-call-completed"
  );
}

export class McpMaterialSyncCoordinator {
  private pending = false;
  private running: Promise<void> | null = null;

  constructor(private readonly sync: () => Promise<void>) {}

  trigger(): void {
    this.pending = true;
    this.running ??= this.drain();
  }

  async flush(): Promise<void> {
    this.trigger();
    await this.running;
  }

  private async drain(): Promise<void> {
    try {
      while (this.pending) {
        this.pending = false;
        try {
          await this.sync();
        } catch {
          // A sync failure is contained; a later boundary must still retry.
        }
      }
    } finally {
      this.running = null;
    }
  }
}

function authorizationView(value: unknown, server: string): AuthorizationView {
  const auth = record(record(value).authorization);
  const mode = auth.mode;
  const state = auth.state;
  if (
    auth.server !== server ||
    (mode !== "none" && mode !== "interactive") ||
    (state !== "authorized" &&
      state !== "needs_authorization" &&
      state !== "failed")
  ) {
    throw new Error("invalid MCP authorization view");
  }
  return publicMcpView(server, mode, state);
}

function materialReply(value: unknown): MaterialReply {
  const reply = record(value);
  if (
    (reply.principal !== null && typeof reply.principal !== "string") ||
    (reply.material !== null && typeof reply.material !== "string") ||
    (reply.version !== null && typeof reply.version !== "string")
  ) {
    throw new Error("invalid MCP material response");
  }
  return {
    principal: reply.principal as string | null,
    material: reply.material as string | null,
    version: reply.version as string | null,
  };
}

export class McpOAuthController {
  private readonly sleep: (milliseconds: number) => Promise<void>;

  constructor(private readonly deps: McpOAuthControllerDeps) {
    this.sleep = deps.sleep ?? ((milliseconds) => new Promise((r) => setTimeout(r, milliseconds)));
  }

  async publicView(server: string): Promise<PublicMcpAuthorizationView> {
    return authorizationView(
      await this.deps.rpc.request("mcp.get", { mcp_id: server }),
      server,
    );
  }

  async upsert(input: {
    name: string;
    transport: unknown;
    url: unknown;
    authorization?: "interactive";
  }): Promise<{ ok: boolean; message: string }> {
    const server = input.name.trim();
    const raw = record(
      await this.deps.rpc.request(
        "mcp.upsert",
        { ...input, name: server },
        { mutationId: this.deps.rpc.newMutationId() },
      ),
    );
    if (typeof raw.ok !== "boolean" || typeof raw.message !== "string") {
      throw new Error("invalid MCP upsert response");
    }
    if (raw.ok && raw.authorization_reset === true) {
      const identity = await this.currentMaterial(server);
      const discarded = discardMcpAuthorization(
        this.deps.vault,
        identity.principal,
        server,
      );
      if (!discarded.ok) {
        throw new Error("MCP authorization storage unavailable");
      }
    }
    return { ok: raw.ok, message: raw.message };
  }

  private async currentMaterial(server: string, knownVersion?: string | null): Promise<MaterialReply> {
    return materialReply(
      await this.deps.rpc.request("mcp.material", {
        mcp_id: server,
        ...(knownVersion ? { known_version: knownVersion } : {}),
      }),
    );
  }

  private persist(
    principal: string | null,
    server: string,
    material: string,
    version: string,
  ): void {
    const result = writeMcpAuthorization(
      this.deps.vault,
      principal,
      server,
      material,
      version,
    );
    if (!result.ok) throw new Error("MCP authorization storage unavailable");
  }

  private async syncOne(
    principal: string | null,
    server: string,
    knownVersion: string | null,
  ): Promise<void> {
    const reply = await this.currentMaterial(server, knownVersion);
    if (reply.principal !== principal) {
      throw new Error("MCP authorization principal changed");
    }
    if (reply.material === null) {
      if (knownVersion !== null && reply.version === null) {
        const discarded = discardMcpAuthorization(
          this.deps.vault,
          principal,
          server,
        );
        if (!discarded.ok) {
          throw new Error("MCP authorization storage unavailable");
        }
        await this.deps.rpc.request(
          "mcp.disconnect",
          { mcp_id: server },
          { mutationId: this.deps.rpc.newMutationId() },
        );
      }
      return;
    }
    if (reply.version === null) throw new Error("missing MCP material version");
    this.persist(principal, server, reply.material, reply.version);
  }

  private async poll(
    requestId: string,
    accept: (reply: Record<string, unknown>) => string | null,
  ): Promise<string> {
    for (let attempt = 0; attempt < POLL_LIMIT; attempt += 1) {
      const reply = record(
        await this.deps.rpc.request("mcp.authorize_status", {
          request_id: requestId,
        }),
      );
      const accepted = accept(reply);
      if (accepted !== null) return accepted;
      if (reply.state !== "awaiting") throw new Error("MCP authorization failed");
      await this.sleep(POLL_MS);
    }
    throw new Error("MCP authorization status timed out");
  }

  private async authorizeOne(
    server: string,
    expectedPrincipal: string | null,
  ): Promise<{ ok: true }> {
    let requestId: string | null = null;
    const result = await this.deps.authorize(async (redirectUri) => {
      const started = record(
        await this.deps.rpc.request("mcp.authorize", {
          mcp_id: server,
          redirect_uri: redirectUri,
        }),
      );
      if (typeof started.request_id !== "string") {
        throw new Error("invalid MCP authorization request");
      }
      requestId = started.request_id;
      return this.poll(requestId, (reply) =>
        reply.state === "awaiting" && typeof reply.url === "string"
          ? reply.url
          : null,
      );
    });
    if (requestId === null || result.state === null) {
      throw new Error("MCP authorization state missing");
    }
    await this.deps.rpc.request("mcp.authorize_complete", {
      request_id: requestId,
      code: result.code,
      state: result.state,
    });
    const serialized = await this.poll(requestId, (reply) => {
      if (reply.state !== "authorized") return null;
      const material = materialReply(reply);
      if (
        material.principal !== expectedPrincipal ||
        material.material === null ||
        material.version === null
      ) {
        throw new Error("invalid MCP authorization material");
      }
      this.persist(material.principal, server, material.material, material.version);
      return "stored";
    });
    if (serialized !== "stored") throw new Error("MCP authorization failed");
    return { ok: true };
  }

  async reconnect(server: string): Promise<unknown> {
    const view = await this.publicView(server);
    if (view.mode !== "interactive") {
      return this.deps.rpc.request(
        "mcp.reconnect",
        { mcp_id: server },
        { mutationId: this.deps.rpc.newMutationId() },
      );
    }
    const identity = await this.currentMaterial(server);
    const saved = readMcpAuthorizationEntry(
      this.deps.vault,
      identity.principal,
      server,
    );
    if (saved === null) return this.authorizeOne(server, identity.principal);
    const result = await this.deps.rpc.request(
      "mcp.reconnect",
      { mcp_id: server, material: saved.material },
      { mutationId: this.deps.rpc.newMutationId() },
    );
    if (!operationOk(result)) {
      await this.disconnect(server);
      return this.authorizeOne(server, identity.principal);
    }
    await this.syncOne(identity.principal, server, saved.version);
    return result;
  }

  async restoreAll(): Promise<void> {
    const listed = record(await this.deps.rpc.request("mcp.list", {}));
    const items = Array.isArray(listed.items) ? listed.items : [];
    for (const item of items) {
      try {
        const auth = authorizationView(item, record(item).id as string);
        if (auth.mode !== "interactive") continue;
        const identity = await this.currentMaterial(auth.server);
        const saved = readMcpAuthorizationEntry(
          this.deps.vault,
          identity.principal,
          auth.server,
        );
        if (saved === null) continue;
        const result = await this.deps.rpc.request(
          "mcp.reconnect",
          { mcp_id: auth.server, material: saved.material },
          { mutationId: this.deps.rpc.newMutationId() },
        );
        if (operationOk(result)) {
          await this.syncOne(identity.principal, auth.server, saved.version);
        } else {
          await this.disconnect(auth.server);
        }
      } catch {
        // Startup is fail-closed and non-interactive per ADR 0019 D5.
      }
    }
  }

  async syncAll(): Promise<void> {
    const listed = record(await this.deps.rpc.request("mcp.list", {}));
    const items = Array.isArray(listed.items) ? listed.items : [];
    for (const item of items) {
      try {
        const raw = record(item);
        if (typeof raw.id !== "string") continue;
        const auth = authorizationView(raw, raw.id);
        if (auth.mode !== "interactive" || auth.state !== "authorized") continue;
        const identity = await this.currentMaterial(auth.server);
        const saved = readMcpAuthorizationEntry(
          this.deps.vault,
          identity.principal,
          auth.server,
        );
        await this.syncOne(identity.principal, auth.server, saved?.version ?? null);
      } catch {
        // One unavailable server must not prevent another server's rotated
        // refresh token from reaching the durable vault.
      }
    }
  }

  async remove(server: string): Promise<unknown> {
    const identity = await this.currentMaterial(server);
    const discarded = discardMcpAuthorization(
      this.deps.vault,
      identity.principal,
      server,
    );
    if (!discarded.ok) throw new Error("MCP authorization storage unavailable");
    const result = await this.deps.rpc.request(
      "mcp.delete",
      { mcp_id: server },
      { mutationId: this.deps.rpc.newMutationId() },
    );
    return result;
  }

  async disconnect(server: string): Promise<unknown> {
    const identity = await this.currentMaterial(server);
    // Remove the durable copy before asking the sidecar to deactivate. If either
    // step fails, a future process cannot silently reuse stale material.
    const discarded = discardMcpAuthorization(
      this.deps.vault,
      identity.principal,
      server,
    );
    if (!discarded.ok) throw new Error("MCP authorization storage unavailable");
    return this.deps.rpc.request(
      "mcp.disconnect",
      { mcp_id: server },
      { mutationId: this.deps.rpc.newMutationId() },
    );
  }
}
