import {
  ApiClient,
  ApiError,
  createRestSessionTransport,
  type ApprovalDecision,
} from "./api/client";
import type { SessionTransport, SubmitOptions } from "./api/transport";
import type {
  AgentControlProjection,
  BulkDeleteResult,
  CapabilitySettingsStatus,
  ForkSessionRequest,
  McpServerView,
  MonthlyCostView,
  RawEvent,
  SessionCostView,
  SessionSummary,
  SkillsResponse,
  ToolView,
  UploadResult,
} from "./api/types";

/** Web-only construction seam: auth/HTTP/SSE/live implementation remains behind this host. */
export interface WebPresentationHostOptions {
  client?: ApiClient;
  transport?: SessionTransport;
}

export type WebSessionProjection = {
  id: string;
  title: string;
  starred: boolean;
  projectId: null;
};

export class WebPresentationHost {
  readonly webClient: ApiClient;
  private readonly transport: SessionTransport;
  private readonly subscriptions = new Set<() => void>();

  constructor({ client = new ApiClient(), transport }: WebPresentationHostOptions = {}) {
    this.webClient = client;
    this.transport = transport ?? createRestSessionTransport(client);
  }

  listSessions(): Promise<SessionSummary[]> {
    return this.webClient.listSessions();
  }

  async listSessionProjections(): Promise<WebSessionProjection[]> {
    const sessions = await this.listSessions();
    return sessions.map((session) => ({
      id: session.session_id,
      title: session.label ?? session.session_id.slice(0, 8),
      starred: Boolean(session.starred),
      projectId: null,
    }));
  }

  openSession(model?: string): Promise<{ session_id: string }> {
    return this.transport.openSession(model);
  }

  subscribeProgress(
    sessionId: string,
    onEvent: (event: RawEvent) => void,
    onError: (error: unknown) => void = () => undefined,
    onComplete: () => void = () => undefined,
  ): () => void {
    let active = true;
    const unsubscribe = () => {
      active = false;
      this.subscriptions.delete(unsubscribe);
    };
    this.subscriptions.add(unsubscribe);

    void (async () => {
      try {
        for await (const event of this.transport.streamSession(sessionId)) {
          if (!active) return;
          onEvent(event);
        }
      } catch (error) {
        if (active) onError(error);
      } finally {
        if (active) {
          this.subscriptions.delete(unsubscribe);
          onComplete();
        }
      }
    })();

    return unsubscribe;
  }

  submit(sessionId: string, prompt: string, options?: SubmitOptions): Promise<unknown> {
    return options
      ? this.transport.submit(sessionId, prompt, options)
      : this.transport.submit(sessionId, prompt);
  }

  answerApproval(
    sessionId: string,
    requestId: string,
    decision: ApprovalDecision,
  ): Promise<void> {
    return this.transport.answerApproval(sessionId, requestId, decision);
  }

  answerQuestion(sessionId: string, requestId: string, answers: string[]): Promise<void> {
    return this.transport.answerQuestion(sessionId, requestId, answers);
  }

  cancel(sessionId: string): Promise<void> {
    return this.transport.cancel(sessionId);
  }

  history(sessionId: string): Promise<unknown[]> {
    return this.webClient.history(sessionId);
  }

  renameSession(sessionId: string, title: string): Promise<void> {
    return this.webClient.renameSession(sessionId, title);
  }

  deleteSession(sessionId: string): Promise<void> {
    return this.webClient.deleteSession(sessionId);
  }

  setSessionStarred(sessionId: string, starred: boolean): Promise<void> {
    return starred ? this.webClient.starSession(sessionId) : this.webClient.unstarSession(sessionId);
  }

  searchSessions(query: string): Promise<SessionSummary[]> {
    return this.webClient.searchSessions(query);
  }

  bulkDeleteSessions(sessionIds: string[]): Promise<BulkDeleteResult> {
    return this.webClient.bulkDeleteSessions(sessionIds);
  }

  forkSession(sessionId: string, request: ForkSessionRequest): Promise<{ session_id: string }> {
    return this.webClient.forkSession(sessionId, request);
  }

  getAgentControls(sessionId: string): Promise<AgentControlProjection> {
    return this.webClient.getAgentControls(sessionId);
  }

  getSessionCost(sessionId: string): Promise<SessionCostView> {
    return this.webClient.getSessionCost(sessionId);
  }

  getMonthlyCost(): Promise<MonthlyCostView> {
    return this.webClient.getMonthlyCost();
  }

  inspectSkills(): Promise<SkillsResponse> {
    return this.webClient.inspectSkills();
  }

  inspectTools(): Promise<ToolView[]> {
    return this.webClient.inspectTools();
  }

  inspectMcp(): Promise<McpServerView[]> {
    return this.webClient.inspectMcp();
  }

  getCapabilitySettings(): Promise<CapabilitySettingsStatus> {
    return this.webClient.getCapabilitySettings();
  }

  uploadFile(file: File): Promise<UploadResult> {
    return this.webClient.uploadFile(file);
  }

  /** Stop every renderer-owned subscription on remount/unmount without altering server state. */
  teardown(): void {
    for (const unsubscribe of [...this.subscriptions]) unsubscribe();
  }

  isUnauthorized(error: unknown): boolean {
    return error instanceof ApiError && error.status === 401;
  }
}

export function createWebPresentationHost(
  options: WebPresentationHostOptions = {},
): WebPresentationHost {
  return new WebPresentationHost(options);
}
