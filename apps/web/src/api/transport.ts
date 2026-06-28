import type { ApprovalDecision } from "./client";
import type { RawEvent } from "./types";

export type TransportStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "degraded"
  | "closed";

export interface SubmitOptions {
  model?: string;
}

export interface SessionTransport {
  readonly mode: "rest_sse" | "live";
  openSession(model?: string): Promise<{ session_id: string }>;
  streamSession(sessionId: string): AsyncGenerator<RawEvent>;
  submit(sessionId: string, prompt: string, options?: SubmitOptions): Promise<unknown>;
  answerApproval(
    sessionId: string,
    requestId: string,
    decision: ApprovalDecision,
  ): Promise<void>;
  answerQuestion(sessionId: string, requestId: string, answers: string[]): Promise<void>;
  cancel(sessionId: string): Promise<void>;
}
