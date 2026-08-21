/**
 * Typed Desktop RPC adapter (078 T030/T044).
 *
 * Speaks only through `window.loopplaneDesktop` (or an injected double). Never
 * sends raw JSON-RPC envelopes, request IDs, or mutation IDs from the renderer.
 */

import type { RawEvent } from "@web/api/types";

import type { LoopPlaneDesktopApi } from "./global";

/** Injected facade shape used by tests and production preload. */
export type DesktopApi = Pick<
  LoopPlaneDesktopApi,
  | "app"
  | "sessions"
  | "interaction"
  | "projects"
  | "workspaces"
  | "inspection"
  | "agentControls"
  | "capabilities"
>;

export type DesktopBridge = DesktopApi;

export type SessionSummaryView = {
  session_id: string;
  title?: string | null;
  starred?: boolean;
  principal_id?: string | null;
};

export type ProjectView = {
  id: string;
  label: string;
  workspace_id?: string | null;
  session_ids?: string[];
};

export type WorkspaceView = {
  id: string;
  label: string;
  availability: string;
  actions?: string[];
};

type InteractionPush = {
  method?: string;
  params?: {
    event?: string | RawEvent;
    reason?: string;
    notification_seq?: number;
    subscription_id?: string;
    session_id?: string;
    [key: string]: unknown;
  };
};

function asRawEvent(value: unknown): RawEvent | null {
  if (!value || typeof value !== "object") return null;
  const rec = value as { type?: unknown };
  if (typeof rec.type !== "string") return null;
  return value as RawEvent;
}

function parseNotificationEvent(
  params: InteractionPush["params"],
): RawEvent | null {
  if (!params) return null;
  return asRawEvent(params.event);
}

/**
 * Renderer transport: sessions/projects/workspaces + interactive run.
 * No protocol IDs or absolute paths in the renderer surface.
 */
export class SidecarTransport {
  private subscriptionId: string | null = null;
  private sessionId: string | null = null;
  private unsubscribePush: (() => void) | null = null;
  private disposed = false;
  /** Renderer-only unsent composer text — never persisted via API. */
  private transientDraft = "";

  constructor(private readonly api: DesktopApi) {}

  get activeSubscriptionId(): string | null {
    return this.subscriptionId;
  }

  get activeSessionId(): string | null {
    return this.sessionId;
  }

  get draft(): string {
    return this.transientDraft;
  }

  setDraft(text: string): void {
    this.transientDraft = text;
  }

  clearDraft(): void {
    this.transientDraft = "";
  }

  async status(): Promise<{ ready?: boolean; [key: string]: unknown }> {
    if (this.disposed) return { ready: false };
    return this.api.app.status();
  }

  // --- Sessions (non-interactive) ---

  async listSessions(query?: string): Promise<SessionSummaryView[]> {
    const result = await this.api.sessions.list(
      query ? { query } : undefined,
    );
    const sessions = (result as { sessions?: unknown }).sessions;
    return Array.isArray(sessions)
      ? (sessions as SessionSummaryView[])
      : [];
  }

  async sessionHistory(sessionId: string): Promise<unknown> {
    return this.api.sessions.history(sessionId);
  }

  async renameSession(sessionId: string, title: string): Promise<unknown> {
    return this.api.sessions.rename(sessionId, title);
  }

  async setSessionStarred(
    sessionId: string,
    starred: boolean,
  ): Promise<unknown> {
    return this.api.sessions.setStarred(sessionId, starred);
  }

  async deleteSession(
    sessionId: string,
    confirmation: unknown = true,
  ): Promise<unknown> {
    return this.api.sessions.delete(sessionId, confirmation);
  }

  async forkSession(
    sessionId: string,
    confirmation: unknown = true,
    sourceSequence = 0,
  ): Promise<unknown> {
    return this.api.sessions.fork(sessionId, confirmation, sourceSequence);
  }

  // --- Projects ---

  async listProjects(): Promise<ProjectView[]> {
    const result = await this.api.projects.list();
    const projects = (result as { projects?: unknown }).projects;
    return Array.isArray(projects) ? (projects as ProjectView[]) : [];
  }

  async createProject(label: string): Promise<unknown> {
    return this.api.projects.create({ label });
  }

  async renameProject(projectId: string, label: string): Promise<unknown> {
    return this.api.projects.rename(projectId, label);
  }

  async removeProject(projectId: string): Promise<unknown> {
    return this.api.projects.remove(projectId);
  }

  async assignSessionToProject(
    projectId: string | null,
    sessionId: string,
  ): Promise<unknown> {
    return this.api.projects.assignSession(projectId, sessionId);
  }

  // --- Workspaces (safe projections only) ---

  async listWorkspaces(): Promise<WorkspaceView[]> {
    const result = await this.api.workspaces.list();
    const workspaces = (result as { workspaces?: unknown }).workspaces;
    return Array.isArray(workspaces) ? (workspaces as WorkspaceView[]) : [];
  }

  async chooseAndBindWorkspace(label?: string): Promise<unknown> {
    return this.api.workspaces.chooseAndBind(label ? { label } : undefined);
  }

  async chooseAndRelinkWorkspace(workspaceId: string): Promise<unknown> {
    return this.api.workspaces.chooseAndRelink(workspaceId);
  }

  async removeWorkspace(workspaceId: string): Promise<unknown> {
    return this.api.workspaces.remove(workspaceId);
  }

  async revalidateWorkspace(workspaceId: string): Promise<unknown> {
    return this.api.workspaces.revalidate(workspaceId);
  }

  /** Resume an existing durable session into the single interactive lease. */
  async resume(sessionId: string, workspaceId?: string): Promise<void> {
    if (this.disposed) throw new Error("transport disposed");
    if (this.subscriptionId) await this.release();
    const handle = await this.api.sessions.resumeInteractive({
      sessionId,
      workspaceId,
    });
    this.subscriptionId = handle.subscription_id;
    this.sessionId = handle.session_id;
  }

  async *run(
    prompt: string,
    options: { workspaceId?: string; permissionMode?: string } = {},
  ): AsyncGenerator<RawEvent> {
    if (this.disposed) throw new Error("transport disposed");
    if (!this.subscriptionId) {
      const handle = await this.api.sessions.createInteractive({
        workspaceId: options.workspaceId,
      });
      this.subscriptionId = handle.subscription_id;
      this.sessionId = handle.session_id;
    }

    const queue: RawEvent[] = [];
    let done = false;
    let terminalEventSeen = false;
    const submitFailure: { error?: unknown } = {};
    let wake: (() => void) | null = null;
    const wakeUp = () => {
      wake?.();
      wake = null;
    };

    this.unsubscribePush?.();
    this.unsubscribePush = this.api.interaction.subscribe(
      this.subscriptionId,
      (payload: unknown) => {
        const push = payload as InteractionPush;
        if (push?.method === "runtime.event") {
          const event = parseNotificationEvent(push.params);
          if (event) {
            if (event.type === "run-terminated") terminalEventSeen = true;
            queue.push(event);
            wakeUp();
          }
          return;
        }
        if (push?.method === "runtime.outcome") {
          done = true;
          wakeUp();
        }
      },
    );

    try {
      this.clearDraft();
      const submitResult = this.api.interaction.submit(this.subscriptionId, {
        prompt,
        ...(options.permissionMode === undefined
          ? {}
          : { permissionMode: options.permissionMode }),
      });

      const submitDone = submitResult.then(
        (result) => {
          done = true;
          if (
            result &&
            typeof result === "object" &&
            "termination_reason" in result &&
            !terminalEventSeen
          ) {
            queue.push({
              type: "run-terminated",
              payload: {
                reason: String(
                  (result as { termination_reason?: string })
                    .termination_reason ?? "natural-completion",
                ),
                turns_taken: Number(
                  (result as { turns_taken?: number }).turns_taken ?? 0,
                ),
              },
            } as RawEvent);
          }
          wakeUp();
          return result;
        },
        (error: unknown) => {
          submitFailure.error = error;
          done = true;
          wakeUp();
        },
      );

      for (;;) {
        while (queue.length > 0) {
          const event = queue.shift();
          if (event) yield event;
        }
        if (done && queue.length === 0) {
          await submitDone;
          if ("error" in submitFailure) throw submitFailure.error;
          while (queue.length > 0) {
            const event = queue.shift();
            if (event) yield event;
          }
          return;
        }
        await new Promise<void>((resolve) => {
          wake = resolve;
        });
      }
    } finally {
      this.unsubscribePush?.();
      this.unsubscribePush = null;
    }
  }

  async release(): Promise<void> {
    if (!this.subscriptionId) return;
    const id = this.subscriptionId;
    this.subscriptionId = null;
    this.sessionId = null;
    this.unsubscribePush?.();
    this.unsubscribePush = null;
    try {
      await this.api.sessions.releaseInteractive(id);
    } catch {
      /* best-effort */
    }
  }

  async dispose(): Promise<void> {
    if (this.disposed) return;
    this.disposed = true;
    this.transientDraft = "";
    this.unsubscribePush?.();
    this.unsubscribePush = null;
    await this.release();
  }

  answerApproval(requestId: string, allow: boolean): void {
    if (this.disposed || !this.subscriptionId) return;
    void this.api.interaction.answerApproval(this.subscriptionId, requestId, {
      allow,
    });
  }

  answerQuestion(requestId: string, answers: string[]): void {
    if (this.disposed || !this.subscriptionId) return;
    void this.api.interaction.answerQuestion(this.subscriptionId, requestId, {
      answers,
    });
  }

  cancel(): void {
    if (this.disposed || !this.subscriptionId) return;
    void this.api.interaction.cancel(this.subscriptionId);
  }
}

export function getDesktopApi(): DesktopApi | null {
  if (typeof window === "undefined") return null;
  return window.loopplaneDesktop ?? null;
}

export function createTransportFromWindow(): SidecarTransport | null {
  const api = getDesktopApi();
  return api ? new SidecarTransport(api) : null;
}
