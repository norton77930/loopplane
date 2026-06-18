// Metadata-only shapes mirroring the web API (unit 018; extended in 026). Field shapes are
// grounded in the runtime event contract (src/loopplane/events/envelope.py), serialized verbatim
// by serialize_event. Only the fields the UI renders are typed.

export interface RawEvent {
  type: string;
  payload?: unknown;
}

export interface OutputPayload {
  text: string;
  turn_index: number;
}

// 026 — reasoning/thinking increment (assistant-reasoning-increment); same shape as output.
export interface ReasoningPayload {
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

// 026 — the real wire question shape is { text, options } (unit-018 mis-modeled it as { prompt }).
export interface Question {
  text: string;
  options: string[];
}

export interface QuestionPayload {
  request_id: string;
  questions: Question[];
}

// 026 — per-turn token usage, reported on turn-completed.
export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
}

export interface TurnCompletedPayload {
  turn_index: number;
  stop_reason: string;
  usage: TokenUsage;
}

export interface TerminatedPayload {
  reason: string;
  turns_taken: number;
}

export interface SessionSummary {
  session_id: string;
  last_active_at: string;
}
