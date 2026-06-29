// Metadata-only shapes mirroring the web API (unit 018; extended in 026). Field shapes are
// grounded in the runtime event contract (src/loopplane/events/envelope.py), serialized verbatim
// by serialize_event. Only the fields the UI renders are typed.

import type {
  GeneratedApprovalPayload,
  GeneratedBulkDeleteRequest,
  GeneratedBulkDeleteResult,
  GeneratedForkSessionRequest,
  GeneratedLiveClientMessage,
  GeneratedLiveServerMessage,
  GeneratedLiveTicketView,
  GeneratedOpenedSession,
  GeneratedOutputPayload,
  GeneratedQuestion,
  GeneratedQuestionPayload,
  GeneratedRawEvent,
  GeneratedReasoningPayload,
  GeneratedSessionSummary,
  GeneratedTerminatedPayload,
  GeneratedTokenUsage,
  GeneratedToolCompletedPayload,
  GeneratedToolStartedPayload,
  GeneratedTurnCompletedPayload,
} from "./generated";

export type RawEvent = GeneratedRawEvent;

export type OutputPayload = GeneratedOutputPayload;

// 026 — reasoning/thinking increment (assistant-reasoning-increment); same shape as output.
export type ReasoningPayload = GeneratedReasoningPayload;

export type ToolStartedPayload = GeneratedToolStartedPayload;

export type ToolCompletedPayload = GeneratedToolCompletedPayload;

export type ApprovalPayload = GeneratedApprovalPayload;

// 026 — the real wire question shape is { text, options } (unit-018 mis-modeled it as { prompt }).
export type Question = GeneratedQuestion;

export type QuestionPayload = GeneratedQuestionPayload;

// 026 — per-turn token usage, reported on turn-completed.
export type TokenUsage = GeneratedTokenUsage;

export type TurnCompletedPayload = GeneratedTurnCompletedPayload;

export type TerminatedPayload = GeneratedTerminatedPayload;

export type OpenedSession = GeneratedOpenedSession;

export type SessionSummary = GeneratedSessionSummary;

export type ForkSessionRequest = GeneratedForkSessionRequest;

export type BulkDeleteRequest = GeneratedBulkDeleteRequest;

export type BulkDeleteResult = GeneratedBulkDeleteResult;

export type LiveTicketView = GeneratedLiveTicketView;

export type LiveClientMessage = GeneratedLiveClientMessage;

export type LiveServerMessage = GeneratedLiveServerMessage;

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

// 075 — capability management foundation views.
export interface MemoryCapability {
  id: string;
  name: string;
  kind: string;
  description: string;
  snippet: string;
  status: string;
  updated_at?: string | null;
}

export interface CapabilityOperationResult {
  ok: boolean;
  resource_id?: string | null;
  status: string;
  message: string;
}

export interface MemoryWriteRequest {
  name: string;
  kind: string;
  description: string;
  content: string;
}

export interface MemoryMutationResponse {
  result: CapabilityOperationResult;
  entry?: MemoryCapability | null;
}

export interface ManagedSkill {
  id: string;
  name: string;
  description: string;
  source: string;
  status: string;
  problem?: string | null;
  updated_at?: string | null;
}

export interface SkillWriteRequest {
  name: string;
  description: string;
  instructions: string;
}

export interface SkillMutationResponse {
  result: CapabilityOperationResult;
  skill?: ManagedSkill | null;
}

export interface McpConfiguration {
  id: string;
  name: string;
  status: string;
  tool_count: number;
  tools: string[];
  problem?: string | null;
  updated_at?: string | null;
}

export interface WorkspaceContext {
  id: string;
  name: string;
  description: string;
  workspace_label: string;
  status: string;
  updated_at?: string | null;
}

export interface ManagedSchedule {
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

export interface ModelDefault {
  model_id: string | null;
  label: string | null;
  status: string;
  updated_at?: string | null;
}
