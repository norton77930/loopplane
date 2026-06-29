"""Backend-owned web contract artifact helpers for 075.

This module keeps deterministic fixtures used by contract/type drift tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import cast

WEB_CONTRACT_VERSION = "075-web-capability-management"

_API_RESPONSE_FIXTURES: dict[str, dict[str, object]] = {
    "opened_session": {"session_id": "session-1"},
    "forked_session": {"session_id": "session-fork"},
    "session_summary": {
        "session_id": "session-1",
        "label": "Generated session",
        "last_active_at": "2026-01-01T00:00:01Z",
        "created_at": "2026-01-01T00:00:00Z",
        "model": "model-a",
        "starred": True,
        "forked_from_session_id": "session-0",
        "forked_from_sequence": 1,
        "search_snippet": "Generated",
        "context_id": "Docs",
        "context_name": "Docs",
        "context_workspace_label": "docs-repo",
        "context_status": "available",
    },
    "bulk_delete_result": {"deleted": ["session-1"]},
    "live_ticket": {
        "ticket": "ticket-1",
        "session_id": "session-1",
        "expires_at": "2026-01-01T00:05:00Z",
        "issued_at": "2026-01-01T00:00:00Z",
        "capabilities": [
            "submit",
            "abort",
            "approval_decision",
            "question_answer",
            "ack",
        ],
    },
}

_API_RESPONSE_REQUIRED_FIELDS: dict[str, set[str]] = {
    "opened_session": {"session_id"},
    "forked_session": {"session_id"},
    "session_summary": {"session_id", "label", "last_active_at", "created_at"},
    "bulk_delete_result": {"deleted"},
    "live_ticket": {"ticket", "session_id", "expires_at", "issued_at", "capabilities"},
}

_SESSION_EVENT_FIXTURES: dict[str, dict[str, object]] = {
    "assistant_output_increment": {
        "type": "assistant-output-increment",
        "payload": {"text": "generated hello", "turn_index": 0},
    },
    "assistant_reasoning_increment": {
        "type": "assistant-reasoning-increment",
        "payload": {"text": "thinking", "turn_index": 0},
    },
    "tool_call_started": {
        "type": "tool-call-started",
        "payload": {"call_id": "call-1", "tool_name": "lookup", "input": {}},
    },
    "tool_call_completed": {
        "type": "tool-call-completed",
        "payload": {
            "call_id": "call-1",
            "outcome": "success",
            "outputs": [],
            "artifact_reference": None,
            "error": None,
            "duration_seconds": 0.01,
        },
    },
    "approval_requested": {
        "type": "approval-requested",
        "payload": {
            "request_id": "approval-1",
            "call_id": "call-1",
            "tool_name": "lookup",
            "input_summary": "metadata only",
        },
    },
    "question_asked": {
        "type": "question-asked",
        "payload": {
            "request_id": "question-1",
            "questions": [{"text": "Choose one", "options": ["A", "B"]}],
        },
    },
    "turn_completed": {
        "type": "turn-completed",
        "payload": {
            "turn_index": 0,
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 2,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
        },
    },
    "run_terminated": {
        "type": "run-terminated",
        "payload": {"reason": "natural-completion", "turns_taken": 1},
    },
}

_SESSION_EVENT_PAYLOAD_FIELDS: dict[str, set[str]] = {
    "assistant_output_increment": {"text", "turn_index"},
    "assistant_reasoning_increment": {"text", "turn_index"},
    "tool_call_started": {"call_id", "tool_name", "input"},
    "tool_call_completed": {
        "call_id",
        "outcome",
        "outputs",
        "artifact_reference",
        "error",
        "duration_seconds",
    },
    "approval_requested": {"request_id", "call_id", "tool_name", "input_summary"},
    "question_asked": {"request_id", "questions"},
    "turn_completed": {"turn_index", "stop_reason", "usage"},
    "run_terminated": {"reason", "turns_taken"},
}

_CAPABILITY_FIXTURES: dict[str, dict[str, object]] = {
    "memory": {
        "id": "pref",
        "name": "pref",
        "kind": "user",
        "description": "editor preference",
        "snippet": "likes tabs",
        "status": "available",
        "updated_at": None,
    },
    "skill": {
        "id": "writer",
        "name": "writer",
        "description": "writes notes",
        "source": "managed",
        "status": "available",
        "problem": None,
        "updated_at": None,
    },
    "mcp": {
        "id": "docs",
        "name": "docs",
        "status": "disconnected",
        "tool_count": 0,
        "tools": [],
        "problem": None,
        "updated_at": None,
    },
    "context": {
        "id": "Docs",
        "name": "Docs",
        "description": "documentation workspace",
        "workspace_label": "docs-repo",
        "status": "available",
        "updated_at": None,
    },
    "schedule": {
        "id": "daily-notes",
        "name": "daily-notes",
        "description": "refresh notes",
        "trigger": "manual",
        "enabled": True,
        "status": "enabled",
        "next_run_at": None,
        "last_run_at": None,
        "problem": None,
    },
    "model_default": {
        "model_id": "model-a",
        "label": "Model A",
        "status": "available",
        "updated_at": None,
    },
    "result": {
        "ok": True,
        "resource_id": "pref",
        "status": "available",
        "message": "saved",
    },
}

_CAPABILITY_FIXTURE_REQUIRED_FIELDS: dict[str, set[str]] = {
    "memory": {"id", "name", "kind", "description", "snippet", "status"},
    "skill": {"id", "name", "description", "source", "status"},
    "mcp": {"id", "name", "status", "tool_count", "tools"},
    "context": {"id", "name", "description", "workspace_label", "status"},
    "schedule": {"id", "name", "description", "trigger", "enabled", "status"},
    "model_default": {"model_id", "label", "status"},
    "result": {"ok", "status", "message"},
}


def _copy_fixture_map(
    fixtures: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    return cast(dict[str, dict[str, object]], deepcopy(dict(fixtures)))


def api_response_contract_fixtures() -> dict[str, dict[str, object]]:
    """Return deterministic API response fixtures for web type validation."""

    return _copy_fixture_map(_API_RESPONSE_FIXTURES)


def session_event_contract_fixtures() -> dict[str, dict[str, object]]:
    """Return deterministic representative session events consumed by web UI."""

    return _copy_fixture_map(_SESSION_EVENT_FIXTURES)


def capability_contract_fixtures() -> dict[str, dict[str, object]]:
    """Return deterministic capability fixtures consumed by web and desktop tests."""

    return _copy_fixture_map(_CAPABILITY_FIXTURES)


def validate_api_response_fixture(name: str, fixture: Mapping[str, object]) -> None:
    """Fail clearly when a representative API response fixture drifts."""

    required = _API_RESPONSE_REQUIRED_FIELDS.get(name)
    if required is None:
        raise ValueError(f"unknown API response fixture: {name}")
    missing = required - set(fixture)
    if missing:
        raise ValueError(f"{name} missing fields: {', '.join(sorted(missing))}")


def validate_session_event_fixture(name: str, fixture: Mapping[str, object]) -> None:
    """Fail clearly when a representative session event fixture drifts."""

    expected = _SESSION_EVENT_FIXTURES.get(name)
    if expected is None:
        raise ValueError(f"unknown session event fixture: {name}")
    expected_type = expected["type"]
    if fixture.get("type") != expected_type:
        raise ValueError(f"{name} type must be {expected_type}")
    payload = fixture.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError(f"{name} payload must be an object")
    missing = _SESSION_EVENT_PAYLOAD_FIELDS[name] - set(payload)
    if missing:
        raise ValueError(f"{name} payload missing fields: {', '.join(sorted(missing))}")


def validate_capability_contract_fixture(
    name: str, fixture: Mapping[str, object]
) -> None:
    """Fail clearly when a representative capability fixture drifts."""

    required = _CAPABILITY_FIXTURE_REQUIRED_FIELDS.get(name)
    if required is None:
        raise ValueError(f"unknown capability fixture: {name}")
    missing = required - set(fixture)
    if missing:
        raise ValueError(f"{name} missing fields: {', '.join(sorted(missing))}")


_TYPESCRIPT_TYPE_ARTIFACT = (
    'export const WEB_CONTRACT_VERSION = "075-web-capability-management";\n'
    """
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
"""
)


def typescript_type_artifact() -> str:
    """Return the deterministic generated TypeScript artifact content."""

    return _TYPESCRIPT_TYPE_ARTIFACT


def live_contract_artifacts() -> dict[str, object]:
    """Return deterministic live-channel metadata for tests and drift checks."""

    return {
        "version": WEB_CONTRACT_VERSION,
        "credential_policy": "short_lived_ticket",
        "ticket_fields": {
            "ticket",
            "principal_id",
            "session_id",
            "expires_at",
            "issued_at",
            "capabilities",
        },
        "client_message_types": {
            "submit",
            "abort",
            "approval_decision",
            "question_answer",
            "ack",
        },
        "server_message_types": {"ready", "event", "notice", "error"},
    }


def session_management_contract_artifacts() -> dict[str, object]:
    """Return additive session-management contract metadata."""

    return {
        "version": WEB_CONTRACT_VERSION,
        "owner_scoped": True,
        "summary_optional_fields": {
            "model",
            "starred",
            "forked_from_session_id",
            "forked_from_sequence",
            "search_snippet",
            "context_id",
            "context_name",
            "context_workspace_label",
            "context_status",
        },
        "actions": {
            "draft_commit",
            "preferred_model",
            "star",
            "unstar",
            "fork",
            "search",
            "bulk_delete",
        },
        "bulk_delete_requires_confirmation": True,
    }


def contract_type_artifacts() -> dict[str, object]:
    """Return backend-owned web type artifact metadata."""

    session_fields = {
        "session_id",
        "label",
        "created_at",
        "last_active_at",
        "model",
        "starred",
        "forked_from_session_id",
        "forked_from_sequence",
        "search_snippet",
        "context_id",
        "context_name",
        "context_workspace_label",
        "context_status",
    }
    event_types = {
        "assistant-output-increment",
        "assistant-reasoning-increment",
        "tool-call-started",
        "tool-call-completed",
        "approval-requested",
        "question-asked",
        "turn-completed",
        "run-terminated",
    }
    return {
        "version": WEB_CONTRACT_VERSION,
        "session_summary_fields": session_fields,
        "event_types": event_types,
        "capability_fixture_names": set(_CAPABILITY_FIXTURES),
        "live": live_contract_artifacts(),
        "session_management": session_management_contract_artifacts(),
    }


def validate_contract_artifact(artifact: dict[str, object]) -> None:
    """Fail clearly when a required web-facing field or event type drifts."""

    required_session_fields = cast(
        set[str], contract_type_artifacts()["session_summary_fields"]
    )
    required_event_types = cast(set[str], contract_type_artifacts()["event_types"])
    actual_session_fields = artifact.get("session_summary_fields")
    actual_event_types = artifact.get("event_types")
    if not isinstance(actual_session_fields, set):
        raise ValueError("session_summary_fields must be a set")
    if not isinstance(actual_event_types, set):
        raise ValueError("event_types must be a set")
    missing_session = required_session_fields - actual_session_fields
    if missing_session:
        missing = ", ".join(sorted(missing_session))
        raise ValueError(f"missing session fields: {missing}")
    missing_events = required_event_types - actual_event_types
    if missing_events:
        raise ValueError(f"missing event types: {', '.join(sorted(missing_events))}")
