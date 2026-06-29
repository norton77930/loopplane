export const WEB_CONTRACT_VERSION = "075-web-capability-management";

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
  context_id?: string | null;
  context_name?: string | null;
  context_workspace_label?: string | null;
  context_status?: string | null;
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

export interface GeneratedCapabilityOperationResult {
  ok: boolean;
  resource_id?: string | null;
  status: string;
  message: string;
}

export interface GeneratedMemoryCapability {
  id: string;
  name: string;
  kind: string;
  description: string;
  snippet: string;
  status: string;
  updated_at?: string | null;
}

export interface GeneratedManagedSkill {
  id: string;
  name: string;
  description: string;
  source: string;
  status: string;
  problem?: string | null;
  updated_at?: string | null;
}

export interface GeneratedMcpConfiguration {
  id: string;
  name: string;
  status: string;
  tool_count: number;
  tools: string[];
  problem?: string | null;
  updated_at?: string | null;
}

export interface GeneratedWorkspaceContext {
  id: string;
  name: string;
  description: string;
  workspace_label: string;
  status: string;
  updated_at?: string | null;
}

export interface GeneratedManagedSchedule {
  id: string;
  name: string;
  description: string;
  trigger: string;
  enabled: boolean;
  status: string;
  next_run_at?: string | null;
  last_run_at?: string | null;
  problem?: string | null;
}

export interface GeneratedModelDefault {
  model_id: string | null;
  label: string | null;
  status: string;
  updated_at?: string | null;
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
    context_id: "Docs",
    context_name: "Docs",
    context_workspace_label: "docs-repo",
    context_status: "available",
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

export const generatedCapabilityFixtures = {
  memory: {
    id: "pref",
    name: "pref",
    kind: "user",
    description: "editor preference",
    snippet: "likes tabs",
    status: "available",
    updated_at: null,
  },
  skill: {
    id: "writer",
    name: "writer",
    description: "writes notes",
    source: "managed",
    status: "available",
    problem: null,
    updated_at: null,
  },
  mcp: {
    id: "docs",
    name: "docs",
    status: "disconnected",
    tool_count: 0,
    tools: [],
    problem: null,
    updated_at: null,
  },
  context: {
    id: "Docs",
    name: "Docs",
    description: "documentation workspace",
    workspace_label: "docs-repo",
    status: "available",
    updated_at: null,
  },
  schedule: {
    id: "daily-notes",
    name: "daily-notes",
    description: "refresh notes",
    trigger: "manual",
    enabled: true,
    status: "enabled",
    next_run_at: null,
    last_run_at: null,
    problem: null,
  },
  model_default: {
    model_id: "model-a",
    label: "Model A",
    status: "available",
    updated_at: null,
  },
  result: {
    ok: true,
    resource_id: "pref",
    status: "available",
    message: "saved",
  },
} as const satisfies {
  memory: GeneratedMemoryCapability;
  skill: GeneratedManagedSkill;
  mcp: GeneratedMcpConfiguration;
  context: GeneratedWorkspaceContext;
  schedule: GeneratedManagedSchedule;
  model_default: GeneratedModelDefault;
  result: GeneratedCapabilityOperationResult;
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
