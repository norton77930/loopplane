// The single seam between the UI and the unit-011 web/API host (R1; api-client.md).
// fetch is injectable so tests run the full client against a stubbed network.

import { streamEvents } from "./events";
import type {
  McpServerView,
  MemoryEntryView,
  RawEvent,
  SessionSummary,
  SkillsResponse,
  ToolView,
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

  async openSession(): Promise<{ session_id: string }> {
    return this.json("/v1/sessions", { method: "POST" });
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
