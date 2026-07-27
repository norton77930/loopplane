import type { ApiClient } from "./client";
import type { SessionTransport, SubmitOptions } from "./transport";

export class RestSessionTransport implements SessionTransport {
  readonly mode = "rest_sse" as const;

  constructor(private readonly client: ApiClient) {}

  openSession(model?: string): Promise<{ session_id: string }> {
    return this.client.openSession(model);
  }

  streamSession(sessionId: string) {
    return this.client.streamSession(sessionId);
  }

  submit(sessionId: string, prompt: string, options?: SubmitOptions): Promise<unknown> {
    return this.client.submit(sessionId, prompt, options);
  }

  answerApproval(
    sessionId: string,
    requestId: string,
    decision: Parameters<ApiClient["answerApproval"]>[2],
  ): Promise<void> {
    return this.client.answerApproval(sessionId, requestId, decision);
  }

  answerQuestion(sessionId: string, requestId: string, answers: string[]): Promise<void> {
    return this.client.answerQuestion(sessionId, requestId, answers);
  }

  cancel(sessionId: string): Promise<void> {
    return this.client.cancel(sessionId);
  }
}
