/**
 * DesktopPresentationHost over typed preload facade (078 T065).
 *
 * No HTTP/API-client/RPC envelopes — only window.loopplaneDesktop.
 */

import {
  defaultCapabilityMap,
  type CoworkPresentationHost,
  type ProgressHandler,
  type PresentationSubmitOptions,
} from "@loopplane/cowork-presentation";
import type {
  PresentationAgentControls,
  PresentationCapability,
  PresentationInspection,
  PresentationSessionSummary,
} from "@loopplane/cowork-presentation";

import type {
  BackupCreateResult,
  LoopPlaneDesktopApi,
  RestoreCommitResult,
  RestoreValidationResult,
  TurnAuditPage,
} from "./global";
import type { DesktopApi } from "./sidecar";
import { getDesktopApi, SidecarTransport } from "./sidecar";

type DesktopPresentationApi = DesktopApi &
  Partial<Pick<LoopPlaneDesktopApi, "audit" | "backup">>;

export class DesktopPresentationHost implements CoworkPresentationHost {
  private readonly api: DesktopPresentationApi;
  private readonly transport: SidecarTransport;
  private readonly progressHandlers = new Map<string, Set<ProgressHandler>>();

  constructor(api: DesktopPresentationApi) {
    this.api = api;
    this.transport = new SidecarTransport(api);
  }

  capabilities() {
    return defaultCapabilityMap();
  }

  async listSessions(): Promise<PresentationSessionSummary[]> {
    const sessions = await this.transport.listSessions();
    return sessions.map((s) => ({
      id: s.session_id,
      title: s.title ?? s.session_id.slice(0, 8),
      starred: Boolean(s.starred),
      projectId: null,
    }));
  }

  async getTurnAudit(
    sessionId: string,
    cursor?: string,
    limit?: number,
  ): Promise<TurnAuditPage> {
    const audit = this.api.audit;
    if (!audit) throw new Error("audit_unavailable");
    return audit.list(sessionId, cursor, limit);
  }

  async createBackup(
    acknowledgement: boolean,
  ): Promise<BackupCreateResult | null> {
    const backup = this.api.backup;
    if (!backup) throw new Error("backup_unavailable");
    return backup.chooseAndCreate({ acknowledgement });
  }

  async validateRestore(): Promise<RestoreValidationResult | null> {
    const backup = this.api.backup;
    if (!backup) throw new Error("backup_unavailable");
    return backup.chooseAndValidateRestore();
  }

  async commitRestore(
    restoreToken: string,
    confirmation: boolean,
  ): Promise<RestoreCommitResult> {
    const backup = this.api.backup;
    if (!backup) throw new Error("backup_unavailable");
    return backup.commitRestore(restoreToken, confirmation);
  }

  async cancelRestore(restoreToken: string): Promise<void> {
    const backup = this.api.backup;
    if (!backup) throw new Error("backup_unavailable");
    await backup.cancelRestore(restoreToken);
  }

  async getCapabilities(): Promise<PresentationCapability[]> {
    const result = (await this.api.capabilities.list()) as {
      capabilities?: PresentationCapability[];
    };
    if (!Array.isArray(result.capabilities)) {
      throw new Error("capabilities_unavailable");
    }
    return result.capabilities;
  }

  async invokeCapabilityAction(
    capabilityId: string,
    action: string,
  ): Promise<PresentationCapability[]> {
    const result = (await this.api.capabilities.invokeAction(
      capabilityId,
      action,
    )) as { capabilities?: PresentationCapability[] };
    if (!Array.isArray(result.capabilities)) {
      throw new Error("capabilities_unavailable");
    }
    return result.capabilities;
  }

  async getInspection(
    sessionId: string | null,
  ): Promise<PresentationInspection> {
    const raw = (await this.api.inspection.get(sessionId)) as Record<
      string,
      unknown
    >;
    return {
      sessionId:
        typeof raw.session_id === "string" ? raw.session_id : sessionId,
      skills: Array.isArray(raw.skills)
        ? (raw.skills as PresentationInspection["skills"])
        : [],
      tools: Array.isArray(raw.tools)
        ? (raw.tools as PresentationInspection["tools"])
        : [],
      mcp: Array.isArray(raw.mcp)
        ? (raw.mcp as PresentationInspection["mcp"])
        : [],
      memory: Array.isArray(raw.memory)
        ? (raw.memory as PresentationInspection["memory"])
        : [],
      // The V1 Desktop facade has no cost/context/upload/artifact projections.
      // Explicitly preserve that absence rather than inventing successful values.
      cost: { status: "unavailable" },
      context: { status: "unavailable" },
      uploads: { status: "unavailable" },
      artifacts: { status: "unavailable" },
      unavailable: raw.unavailable === true,
    };
  }

  async getAgentControls(
    sessionId: string,
  ): Promise<PresentationAgentControls> {
    const raw = (await this.api.agentControls.get(sessionId)) as Record<
      string,
      unknown
    >;
    const budget = (raw.budget as Record<string, unknown>) || {};
    return {
      sessionId,
      defaultMode:
        typeof raw.default_mode === "string" ? raw.default_mode : null,
      selectableModes: Array.isArray(raw.selectable_modes)
        ? (raw.selectable_modes as PresentationAgentControls["selectableModes"])
        : [],
      activeRun: (raw.active_run as PresentationAgentControls["activeRun"]) ?? null,
      lastAcceptedRun:
        (raw.last_accepted_run as PresentationAgentControls["lastAcceptedRun"]) ??
        null,
      budget: {
        tracking: String(budget.tracking ?? "unknown"),
        pricing: String(budget.pricing ?? "unknown"),
        sessionGuard: String(budget.session_guard ?? "unknown"),
        monthlyGuard: String(budget.monthly_guard ?? "unknown"),
      },
      actions: Array.isArray(raw.actions) ? (raw.actions as string[]) : [],
      unavailable: raw.unavailable === true,
    };
  }

  subscribeProgress(sessionId: string, onEvent: ProgressHandler): () => void {
    let handlers = this.progressHandlers.get(sessionId);
    if (!handlers) {
      handlers = new Set();
      this.progressHandlers.set(sessionId, handlers);
    }
    handlers.add(onEvent);
    let active = true;
    return () => {
      if (!active) return;
      active = false;
      const current = this.progressHandlers.get(sessionId);
      current?.delete(onEvent);
      if (current?.size === 0) this.progressHandlers.delete(sessionId);
    };
  }

  async submit(
    sessionId: string,
    prompt: string,
    options?: PresentationSubmitOptions,
  ): Promise<void> {
    for await (const event of this.transport.run(prompt, options)) {
      this.routeProgressEvent(sessionId, event);
    }
  }

  private routeProgressEvent(
    sessionId: string,
    event: { type: string; payload?: unknown },
  ): void {
    for (const handler of this.progressHandlers.get(sessionId) ?? []) {
      handler(event);
    }
  }

  async answerApproval(requestId: string, allow: boolean): Promise<void> {
    this.transport.answerApproval(requestId, allow);
  }

  async answerQuestion(requestId: string, answers: string[]): Promise<void> {
    this.transport.answerQuestion(requestId, answers);
  }

  async cancel(sessionId: string): Promise<void> {
    void sessionId;
    this.transport.cancel();
  }
}

export function createDesktopPresentationHost(): DesktopPresentationHost | null {
  const api = getDesktopApi();
  if (!api?.capabilities || !api.inspection || !api.agentControls) {
    // Still allow construction when partial facade exists for sessions-only.
    if (!api) return null;
  }
  if (!api) return null;
  return new DesktopPresentationHost(api);
}
