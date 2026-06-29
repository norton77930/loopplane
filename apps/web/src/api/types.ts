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
  label: string | null;
  last_active_at: string;
  created_at: string;
  model?: string | null;
  starred?: boolean;
  forked_from_session_id?: string | null;
  forked_from_sequence?: number | null;
  search_snippet?: string | null;
}

export interface ForkSessionRequest {
  sequence: number;
  title?: string | null;
  model?: string | null;
}

export interface BulkDeleteResult {
  deleted: string[];
}

// 027 — read-only inspection views (metadata-only).
export interface SkillView {
  name: string;
  description: string;
  autonomous: boolean;
  approval_required: boolean;
  source: string;
}

export interface SkillsResponse {
  skills: SkillView[];
  problems: string[];
}

export interface ToolView {
  name: string;
  description: string;
  read_only: boolean;
  source: string;
}

export interface McpServerView {
  name: string;
  tools: string[];
}

export interface MemoryEntryView {
  type: string;
  name: string;
  description: string;
  snippet: string;
}

// 028 — model catalog + uploads.
export interface ModelInfo {
  id: string;
  label: string;
}

export interface UploadResult {
  reference: string;
  name: string;
}
