// Metadata-only shapes mirroring the web API (unit 018; data-model.md).
// Only the fields the UI renders are typed.

export interface RawEvent {
  type: string;
  payload?: unknown;
}

export interface OutputPayload {
  text: string;
  turn_index: number;
}

export interface ToolStartedPayload {
  call_id: string;
  tool_name: string;
}

export interface ToolCompletedPayload {
  call_id: string;
  outcome: "success" | "failure";
}

export interface ApprovalPayload {
  request_id: string;
  tool_name: string;
  input_summary: string;
}

export interface QuestionPayload {
  request_id: string;
  questions: { prompt: string }[];
}

export interface TerminatedPayload {
  reason: string;
  turns_taken: number;
}

export interface SessionSummary {
  session_id: string;
  last_active_at: string;
}
