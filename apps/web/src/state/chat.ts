// A pure reducer folding the normalized event stream into the ordered view model (R3; 025/026).
// One ordered `entries` list (stream order) interleaves user / reasoning / assistant / tool /
// terminated; a small usage accumulator folds turn-completed. Consumer-side shaping over the
// same normalized events (Constitution VI) — no event schema change.

import type {
  ApprovalPayload,
  OutputPayload,
  QuestionPayload,
  RawEvent,
  ReasoningPayload,
  TerminatedPayload,
  TokenUsage,
  ToolCompletedPayload,
  ToolStartedPayload,
  TurnCompletedPayload,
} from "../api/types";

export type ConversationEntry =
  | { kind: "user"; text: string }
  | { kind: "reasoning"; text: string }
  | { kind: "assistant"; text: string }
  | {
      kind: "tool";
      callId: string;
      name: string;
      outcome?: "success" | "failure";
      artifactReference?: string;
    }
  | { kind: "terminated"; reason: string; turns: number };

export interface UsageState {
  last?: TokenUsage;
  total: TokenUsage;
}

export interface ChatState {
  entries: ConversationEntry[];
  pendingApproval?: { requestId: string; toolName: string };
  pendingQuestion?: { requestId: string; prompt: string; options: string[] };
  usage: UsageState;
  status: "idle" | "running" | "terminated" | "error";
}

export const ZERO_USAGE: TokenUsage = {
  input_tokens: 0,
  output_tokens: 0,
  cached_tokens: 0,
  reasoning_tokens: 0,
};

export const initialState: ChatState = {
  entries: [],
  usage: { total: ZERO_USAGE },
  status: "idle",
};

/** Record a submitted user prompt and mark the run active. */
export function userPrompt(state: ChatState, text: string): ChatState {
  return {
    ...state,
    entries: [...state.entries, { kind: "user", text }],
    status: "running",
  };
}

/** Mark the connection/stream as failed (FR-010, 025); the conversation is preserved. */
export function errored(state: ChatState): ChatState {
  return { ...state, status: "error" };
}

export function reduce(state: ChatState, event: RawEvent): ChatState {
  switch (event.type) {
    case "assistant-output-increment":
      return appendText(state, "assistant", (event.payload as OutputPayload).text);
    case "assistant-reasoning-increment":
      return appendText(state, "reasoning", (event.payload as ReasoningPayload).text);
    case "tool-call-started": {
      const p = event.payload as ToolStartedPayload;
      return {
        ...state,
        entries: [...state.entries, { kind: "tool", callId: p.call_id, name: p.tool_name }],
      };
    }
    case "tool-call-completed": {
      const p = event.payload as ToolCompletedPayload;
      return {
        ...state,
        entries: state.entries.map((entry) =>
          entry.kind === "tool" && entry.callId === p.call_id && entry.outcome === undefined
            ? {
                ...entry,
                outcome: p.outcome,
                ...(p.artifact_reference
                  ? { artifactReference: p.artifact_reference }
                  : {}),
              }
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
      const q = p.questions[0];
      return {
        ...state,
        pendingQuestion: {
          requestId: p.request_id,
          prompt: q?.text ?? "",
          options: q?.options ?? [],
        },
      };
    }
    case "turn-completed": {
      const p = event.payload as TurnCompletedPayload;
      return {
        ...state,
        usage: { last: p.usage, total: sumUsage(state.usage.total, p.usage) },
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
      // Unknown event types pass through unchanged (forward-compatible — FR-010).
      return state;
  }
}

/** Merge consecutive same-kind text increments (assistant or reasoning) into one entry. */
function appendText(
  state: ChatState,
  kind: "assistant" | "reasoning",
  text: string,
): ChatState {
  const last = state.entries[state.entries.length - 1];
  if (last && last.kind === kind) {
    return {
      ...state,
      entries: [...state.entries.slice(0, -1), { kind, text: last.text + text }],
    };
  }
  return { ...state, entries: [...state.entries, { kind, text }] };
}

function sumUsage(a: TokenUsage, b: TokenUsage): TokenUsage {
  return {
    input_tokens: a.input_tokens + b.input_tokens,
    output_tokens: a.output_tokens + b.output_tokens,
    cached_tokens: a.cached_tokens + b.cached_tokens,
    reasoning_tokens: a.reasoning_tokens + b.reasoning_tokens,
  };
}
