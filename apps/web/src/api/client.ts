// The single seam between the UI and the unit-011 web/API host (R1; api-client.md).
// fetch is injectable so tests run the full client against a stubbed network.

import { streamEvents } from "./events";
import { RestSessionTransport } from "./restTransport";
import type { SessionTransport } from "./transport";
import type {
  BulkDeleteRequest,
  McpServerView,
  MemoryEntryView,
  BulkDeleteResult,
  ForkSessionRequest,
  ModelInfo,
  OpenedSession,
  RawEvent,
  SessionSummary,
  SkillsResponse,
  ToolView,
  UploadResult,
} from "./types";

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`api error ${status}`);
    this.name = "ApiError";
  }
}

export interface ClientOptions {
  baseUrl?: string;
  authHeader?: string;
  fetch?: typeof fetch;
}

export interface ApprovalDecision {
  allow: boolean;
  scope?: "once" | "session";
  reason?: string;
}

export function createRestSessionTransport(client: ApiClient): SessionTransport {
  return new RestSessionTransport(client);
}

export class ApiClient {
  private readonly base: string;
  private readonly headers: Record<string, string>;
  private readonly fetchFn: typeof fetch;

  constructor(opts: ClientOptions = {}) {
    this.base = opts.baseUrl ?? "";
    this.headers = {
      "content-type": "application/json",
      ...(opts.authHeader ? { authorization: opts.authHeader } : {}),
    };
    this.fetchFn = opts.fetch ?? fetch;
  }

  async *streamRun(prompt: string): AsyncGenerator<RawEvent> {
    const res = await this.fetchFn(`${this.base}/v1/runs/events`, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok || !res.body) throw new ApiError(res.status);
    yield* streamEvents(res.body);
  }

  async openSession(model?: string): Promise<OpenedSession> {
    const suffix = model ? `?model=${encodeURIComponent(model)}` : "";
    return this.json(`/v1/sessions${suffix}`, { method: "POST" });
  }

  async listModels(): Promise<ModelInfo[]> {
    return this.json("/v1/models");
  }

  async uploadFile(file: File): Promise<UploadResult> {
    const res = await this.fetchFn(
      `${this.base}/v1/uploads?name=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        headers: { ...this.headers, "content-type": "application/octet-stream" },
        body: file,
      },
    );
    if (!res.ok) throw new ApiError(res.status);
    return (await res.json()) as UploadResult;
  }

  async *streamSession(id: string): AsyncGenerator<RawEvent> {
    const res = await this.fetchFn(`${this.base}/v1/sessions/${id}/events`, {
      headers: this.headers,
    });
    if (!res.ok || !res.body) throw new ApiError(res.status);
    yield* streamEvents(res.body);
  }

  async submit(id: string, prompt: string): Promise<unknown> {
    return this.json(`/v1/sessions/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    });
  }

  async answerApproval(
    id: string,
    requestId: string,
    decision: ApprovalDecision,
  ): Promise<void> {
    await this.json(`/v1/sessions/${id}/approvals/${requestId}`, {
      method: "POST",
      body: JSON.stringify(decision),
    });
  }

  async answerQuestion(
    id: string,
    requestId: string,
    answers: string[],
  ): Promise<void> {
    await this.json(`/v1/sessions/${id}/questions/${requestId}`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });
  }

  async cancel(id: string): Promise<void> {
    await this.json(`/v1/sessions/${id}/cancel`, { method: "POST" });
  }

  async listSessions(): Promise<SessionSummary[]> {
    return this.json("/v1/sessions");
  }

  async history(id: string): Promise<unknown[]> {
    return this.json(`/v1/sessions/${id}/history`);
  }

  // 030 — session management.
  async renameSession(id: string, title: string): Promise<void> {
    await this.json(`/v1/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  }

  async deleteSession(id: string): Promise<void> {
    await this.json(`/v1/sessions/${id}`, { method: "DELETE" });
  }

  async starSession(id: string): Promise<void> {
    await this.json(`/v1/sessions/${id}/star`, { method: "POST" });
  }

  async unstarSession(id: string): Promise<void> {
    await this.json(`/v1/sessions/${id}/star`, { method: "DELETE" });
  }

  async searchSessions(query: string): Promise<SessionSummary[]> {
    return this.json(`/v1/sessions/search?q=${encodeURIComponent(query)}`);
  }

  async forkSession(
    id: string,
    request: ForkSessionRequest,
  ): Promise<OpenedSession> {
    return this.json(`/v1/sessions/${id}/fork`, {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async bulkDeleteSessions(ids: string[]): Promise<BulkDeleteResult> {
    const request: BulkDeleteRequest = { session_ids: ids, confirm: true };
    return this.json("/v1/sessions/bulk-delete", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  // 027 — read-only inspection (metadata-only).
  async inspectSkills(): Promise<SkillsResponse> {
    return this.json("/v1/inspect/skills");
  }

  async inspectTools(): Promise<ToolView[]> {
    return this.json("/v1/inspect/tools");
  }

  async inspectMcp(): Promise<McpServerView[]> {
    return this.json("/v1/inspect/mcp");
  }

  async inspectMemory(query?: string): Promise<MemoryEntryView[]> {
    const suffix = query ? `?q=${encodeURIComponent(query)}` : "";
    return this.json(`/v1/inspect/memory${suffix}`);
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await this.fetchFn(`${this.base}${path}`, {
      ...init,
      headers: { ...this.headers, ...(init?.headers ?? {}) },
    });
    if (!res.ok) throw new ApiError(res.status);
    return (await res.json()) as T;
  }
}
