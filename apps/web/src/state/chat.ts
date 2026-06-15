// A pure reducer folding the normalized event stream into the view model (R3).

import type {
  ApprovalPayload,
  OutputPayload,
  QuestionPayload,
  RawEvent,
  TerminatedPayload,
  ToolCompletedPayload,
  ToolStartedPayload,
} from "../api/types";

export interface Turn {
  role: "user" | "assistant";
  text: string;
}

export type TimelineEntry =
  | { kind: "tool"; callId: string; name: string; outcome?: "success" | "failure" }
  | { kind: "terminated"; reason: string; turns: number };

export interface ChatState {
  turns: Turn[];
  timeline: TimelineEntry[];
  pendingApproval?: { requestId: string; toolName: string };
  pendingQuestion?: { requestId: string; prompt: string };
  status: "idle" | "running" | "terminated" | "error";
}

export const initialState: ChatState = { turns: [], timeline: [], status: "idle" };

/** Record a submitted user prompt and mark the run active. */
export function userPrompt(state: ChatState, text: string): ChatState {
  return {
    ...state,
    turns: [...state.turns, { role: "user", text }],
    status: "running",
  };
}

/** Mark the connection/stream as failed (FR-008). */
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
        timeline: [
          ...state.timeline,
          { kind: "tool", callId: p.call_id, name: p.tool_name },
        ],
      };
    }
    case "tool-call-completed": {
      const p = event.payload as ToolCompletedPayload;
      return {
        ...state,
        timeline: state.timeline.map((entry) =>
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
        timeline: [
          ...state.timeline,
          { kind: "terminated", reason: p.reason, turns: p.turns_taken },
        ],
      };
    }
    default:
      // Unknown event types pass through unchanged (forward-compatible).
      return state;
  }
}

function appendAssistant(state: ChatState, text: string): ChatState {
  const last = state.turns[state.turns.length - 1];
  if (last && last.role === "assistant") {
    return {
      ...state,
      turns: [
        ...state.turns.slice(0, -1),
        { role: "assistant", text: last.text + text },
      ],
    };
  }
  return { ...state, turns: [...state.turns, { role: "assistant", text }] };
}
