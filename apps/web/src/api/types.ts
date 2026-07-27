// Metadata-only shapes mirroring the web API (unit 018; extended in 026). Field shapes are
// grounded in the runtime event contract (src/loopplane/events/envelope.py), serialized verbatim
// by serialize_event. Only the fields the UI renders are typed.

import type {
  GeneratedAcceptedRunPosture,
  GeneratedAgentControlProjection,
  GeneratedApprovalPayload,
  GeneratedBudgetGuardPosture,
  GeneratedBulkDeleteRequest,
  GeneratedBulkDeleteResult,
  GeneratedCapabilityAction,
  GeneratedCapabilityMetadata,
  GeneratedCapabilityOperationResult,
  GeneratedCapabilityScope,
  GeneratedCapabilitySettingsStatus,
  GeneratedForkSessionRequest,
  GeneratedLiveClientMessage,
  GeneratedLiveServerMessage,
  GeneratedLiveTicketView,
  GeneratedManagedSchedule,
  GeneratedManagedSkill,
  GeneratedMcpConfiguration,
  GeneratedMemoryCapability,
  GeneratedModelDefault,
  GeneratedMonthlyCostView,
  GeneratedOpenedSession,
  GeneratedOutputPayload,
  GeneratedPermissionModeOption,
  GeneratedPermissionPosture,
  GeneratedQuestion,
  GeneratedQuestionPayload,
  GeneratedRawEvent,
  GeneratedReasoningPayload,
  GeneratedWorkspaceContext,
  GeneratedSessionCostView,
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

export type SessionSummary = GeneratedSessionSummary & {
  context_id?: string | null;
  context_name?: string | null;
  context_workspace_label?: string | null;
  context_status?: string | null;
};

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

export type PermissionModeOption = GeneratedPermissionModeOption;

export type AcceptedRunPosture = GeneratedAcceptedRunPosture;

export type PermissionPosture = GeneratedPermissionPosture;

export type BudgetGuardPosture = GeneratedBudgetGuardPosture;

export type AgentControlProjection = GeneratedAgentControlProjection;

export type SessionCostView = GeneratedSessionCostView;

export type MonthlyCostView = GeneratedMonthlyCostView;

// 075 — capability management foundation views.
export type CapabilityScope = GeneratedCapabilityScope;

export type CapabilityAction = GeneratedCapabilityAction;

export type CapabilityMetadata = GeneratedCapabilityMetadata;

export type CapabilitySettingsStatus = GeneratedCapabilitySettingsStatus;

export type MemoryCapability = GeneratedMemoryCapability;

export type MemoryCapabilityDetail = MemoryCapability & {
  content: string;
};

export type CapabilityOperationResult = GeneratedCapabilityOperationResult;

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

export type ManagedSkill = GeneratedManagedSkill;

export type ManagedSkillDetail = ManagedSkill & {
  instructions: string;
};

export interface SkillWriteRequest {
  name: string;
  description: string;
  instructions: string;
}

export interface SkillMutationResponse {
  result: CapabilityOperationResult;
  skill?: ManagedSkill | null;
}

export type McpConfiguration = GeneratedMcpConfiguration;

export interface McpConfigurationWriteRequest {
  name: string;
  transport: "http" | "sse" | "stdio" | "websocket";
  url?: string | null;
  command?: string | null;
  args?: string[];
}

export interface McpMutationResponse {
  result: CapabilityOperationResult;
  config?: McpConfiguration | null;
}

export type WorkspaceContext = GeneratedWorkspaceContext;

export interface WorkspaceContextWriteRequest {
  name: string;
  description: string;
  workspace_label: string;
}

export interface WorkspaceContextMutationResponse {
  result: CapabilityOperationResult;
  context?: WorkspaceContext | null;
}

export interface SessionContextView {
  session_id: string;
  context_id: string;
  name: string;
  workspace_label: string;
  status: string;
}

export type ManagedSchedule = GeneratedManagedSchedule;

export interface ScheduleWriteRequest {
  name: string;
  description: string;
  trigger: string;
  enabled: boolean;
  instruction?: string;
}

export interface ScheduleMutationResponse {
  result: CapabilityOperationResult;
  schedule?: ManagedSchedule | null;
}

export type ModelDefault = GeneratedModelDefault;

export interface ModelDefaultMutationResponse {
  result: CapabilityOperationResult;
  default: ModelDefault;
}
