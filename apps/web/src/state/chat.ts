// A pure reducer folding the normalized event stream into the ordered view model (R3).
// One ordered `entries` list (stream order) replaces the previous parallel turns/timeline,
// so tool cards interleave with assistant messages (FR-002/003). Consumer-side shaping over
// the same normalized events (Constitution VI) — no event schema change.

import type {
  ApprovalPayload,
  OutputPayload,
  QuestionPayload,
  RawEvent,
  TerminatedPayload,
  ToolCompletedPayload,
  ToolStartedPayload,
} from "../api/types";

export type ConversationEntry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "tool"; callId: string; name: string; outcome?: "success" | "failure" }
  | { kind: "terminated"; reason: string; turns: number };

export interface ChatState {
  entries: ConversationEntry[];
  pendingApproval?: { requestId: string; toolName: string };
  pendingQuestion?: { requestId: string; prompt: string };
  status: "idle" | "running" | "terminated" | "error";
}

export const initialState: ChatState = { entries: [], status: "idle" };

/** Record a submitted user prompt and mark the run active. */
export function userPrompt(state: ChatState, text: string): ChatState {
  return {
    ...state,
    entries: [...state.entries, { kind: "user", text }],
    status: "running",
  };
}

/** Mark the connection/stream as failed (FR-010); the conversation is preserved. */
export function errored(state: ChatState): ChatState {
  return { ...state, status: "error" };
}

export function reduce(state: ChatState, event: RawEvent): ChatState {
  switch (event.type) {
    case "assistant-output-increment":
      return appendAssistant(state, (event.payload as OutputPayload).text);
    case "tool-call-started": {
      const p = event.payload as ToolStartedPayload;
      return {
        ...state,
        entries: [
          ...state.entries,
          { kind: "tool", callId: p.call_id, name: p.tool_name },
        ],
      };
    }
    case "tool-call-completed": {
      const p = event.payload as ToolCompletedPayload;
      return {
        ...state,
        entries: state.entries.map((entry) =>
          entry.kind === "tool" &&
          entry.callId === p.call_id &&
          entry.outcome === undefined
            ? { ...entry, outcome: p.outcome }
            : entry,
        ),
      };
    }
    case "approval-requested": {
      const p = event.payload as ApprovalPayload;
      return {
        ...state,
        pendingApproval: { requestId: p.request_id, toolName: p.tool_name },
      };
    }
    case "question-asked": {
      const p = event.payload as QuestionPayload;
      return {
        ...state,
        pendingQuestion: {
          requestId: p.request_id,
          prompt: p.questions[0]?.prompt ?? "",
        },
      };
    }
    case "run-terminated": {
      const p = event.payload as TerminatedPayload;
      return {
        ...state,
        status: "terminated",
        // A run that ends while a dialog is pending clears it (spec edge case).
        pendingApproval: undefined,
        pendingQuestion: undefined,
        entries: [
          ...state.entries,
          { kind: "terminated", reason: p.reason, turns: p.turns_taken },
        ],
      };
    }
    default:
      // Unknown event types pass through unchanged (forward-compatible — FR-016).
      return state;
  }
}

function appendAssistant(state: ChatState, text: string): ChatState {
  const last = state.entries[state.entries.length - 1];
  if (last && last.kind === "assistant") {
    return {
      ...state,
      entries: [
        ...state.entries.slice(0, -1),
        { kind: "assistant", text: last.text + text },
      ],
    };
  }
  return { ...state, entries: [...state.entries, { kind: "assistant", text }] };
}
