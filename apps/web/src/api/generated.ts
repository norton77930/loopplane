export const WEB_CONTRACT_VERSION = "074-web-parity-foundation";

export interface GeneratedContractArtifact {
  version: typeof WEB_CONTRACT_VERSION;
  generatedAt: "static";
}

export interface GeneratedRawEvent {
  type: string;
  payload?: unknown;
  session_id?: string;
  sequence?: number;
  occurred_at?: string;
  replay?: boolean;
  schema_version?: number;
}

export interface GeneratedOutputPayload {
  text: string;
  turn_index: number;
}

export interface GeneratedReasoningPayload {
  text: string;
  turn_index: number;
}

export interface GeneratedToolStartedPayload {
  call_id: string;
  tool_name: string;
  input?: Record<string, unknown>;
}

export interface GeneratedToolCompletedPayload {
  call_id: string;
  outcome: "success" | "failure";
  outputs?: unknown[];
  artifact_reference?: string | null;
  error?: unknown;
  duration_seconds?: number;
}

export interface GeneratedApprovalPayload {
  request_id: string;
  call_id?: string;
  tool_name: string;
  input_summary: string;
}

export interface GeneratedQuestion {
  text: string;
  options: string[];
}

export interface GeneratedQuestionPayload {
  request_id: string;
  questions: GeneratedQuestion[];
}

export interface GeneratedTokenUsage {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
}

export interface GeneratedTurnCompletedPayload {
  turn_index: number;
  stop_reason: string;
  usage: GeneratedTokenUsage;
}

export interface GeneratedTerminatedPayload {
  reason: string;
  turns_taken: number;
}

export interface GeneratedOpenedSession {
  session_id: string;
}

export interface GeneratedSessionSummary {
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

export interface GeneratedForkSessionRequest {
  sequence: number;
  title?: string | null;
  model?: string | null;
}

export interface GeneratedBulkDeleteRequest {
  session_ids: string[];
  confirm: boolean;
}

export interface GeneratedBulkDeleteResult {
  deleted: string[];
}

export interface GeneratedLiveTicketView {
  ticket: string;
  session_id: string;
  expires_at: string;
  issued_at: string;
  capabilities: string[];
}

export type GeneratedLiveClientMessageType =
  | "submit"
  | "abort"
  | "approval_decision"
  | "question_answer"
  | "ack";

export interface GeneratedLiveClientMessage {
  type: GeneratedLiveClientMessageType;
  client_message_id?: string | null;
  sequence?: number | null;
  payload?: Record<string, unknown>;
}

export type GeneratedLiveServerMessageType = "ready" | "event" | "notice" | "error";

export interface GeneratedLiveServerMessage {
  type: GeneratedLiveServerMessageType;
  session_id?: string;
  sequence?: number;
  payload?: unknown;
}

export const generatedApiResponseFixtures = {
  opened_session: { session_id: "session-1" },
  forked_session: { session_id: "session-fork" },
  session_summary: {
    session_id: "session-1",
    label: "Generated session",
    last_active_at: "2026-01-01T00:00:01Z",
    created_at: "2026-01-01T00:00:00Z",
    model: "model-a",
    starred: true,
    forked_from_session_id: "session-0",
    forked_from_sequence: 1,
    search_snippet: "Generated",
  },
  bulk_delete_result: { deleted: ["session-1"] },
  live_ticket: {
    ticket: "ticket-1",
    session_id: "session-1",
    expires_at: "2026-01-01T00:05:00Z",
    issued_at: "2026-01-01T00:00:00Z",
    capabilities: ["submit", "abort", "approval_decision", "question_answer", "ack"],
  },
} as const satisfies {
  opened_session: GeneratedOpenedSession;
  forked_session: GeneratedOpenedSession;
  session_summary: GeneratedSessionSummary;
  bulk_delete_result: GeneratedBulkDeleteResult;
  live_ticket: GeneratedLiveTicketView;
};

export const generatedSessionEventFixtures = {
  assistant_output_increment: {
    type: "assistant-output-increment",
    payload: { text: "generated hello", turn_index: 0 },
  },
  assistant_reasoning_increment: {
    type: "assistant-reasoning-increment",
    payload: { text: "thinking", turn_index: 0 },
  },
  tool_call_started: {
    type: "tool-call-started",
    payload: { call_id: "call-1", tool_name: "lookup", input: {} },
  },
  tool_call_completed: {
    type: "tool-call-completed",
    payload: {
      call_id: "call-1",
      outcome: "success",
      outputs: [],
      artifact_reference: null,
      error: null,
      duration_seconds: 0.01,
    },
  },
  approval_requested: {
    type: "approval-requested",
    payload: {
      request_id: "approval-1",
      call_id: "call-1",
      tool_name: "lookup",
      input_summary: "metadata only",
    },
  },
  question_asked: {
    type: "question-asked",
    payload: {
      request_id: "question-1",
      questions: [{ text: "Choose one", options: ["A", "B"] }],
    },
  },
  turn_completed: {
    type: "turn-completed",
    payload: {
      turn_index: 0,
      stop_reason: "end_turn",
      usage: {
        input_tokens: 1,
        output_tokens: 2,
        cached_tokens: 0,
        reasoning_tokens: 0,
      },
    },
  },
  run_terminated: {
    type: "run-terminated",
    payload: { reason: "natural-completion", turns_taken: 1 },
  },
} as const satisfies Record<string, GeneratedRawEvent>;
