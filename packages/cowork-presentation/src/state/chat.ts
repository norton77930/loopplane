export type RawEvent = { type: string; payload?: unknown };

export type TokenUsage = {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
};

type OutputPayload = { text: string };
type ReasoningPayload = { text: string };
type ToolStartedPayload = { call_id: string; tool_name: string };
type ToolCompletedPayload = {
  call_id: string;
  outcome: "success" | "failure";
  artifact_reference?: string;
};
type ApprovalPayload = { request_id: string; tool_name: string };
type QuestionPayload = { request_id: string; questions: Array<{ text: string; options: string[] }> };
type TurnCompletedPayload = { usage: TokenUsage };
type TerminatedPayload = { reason: string; turns_taken: number };

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

export function userPrompt(state: ChatState, text: string): ChatState {
  return { ...state, entries: [...state.entries, { kind: "user", text }], status: "running" };
}

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
      const payload = event.payload as ToolStartedPayload;
      return { ...state, entries: [...state.entries, { kind: "tool", callId: payload.call_id, name: payload.tool_name }] };
    }
    case "tool-call-completed": {
      const payload = event.payload as ToolCompletedPayload;
      return {
        ...state,
        entries: state.entries.map((entry) =>
          entry.kind === "tool" && entry.callId === payload.call_id && entry.outcome === undefined
            ? { ...entry, outcome: payload.outcome, ...(payload.artifact_reference ? { artifactReference: payload.artifact_reference } : {}) }
            : entry,
        ),
      };
    }
    case "approval-requested": {
      const payload = event.payload as ApprovalPayload;
      return { ...state, pendingApproval: { requestId: payload.request_id, toolName: payload.tool_name } };
    }
    case "question-asked": {
      const payload = event.payload as QuestionPayload;
      const question = payload.questions[0];
      return {
        ...state,
        pendingQuestion: {
          requestId: payload.request_id,
          prompt: question?.text ?? "",
          options: question?.options ?? [],
        },
      };
    }
    case "turn-completed": {
      const payload = event.payload as TurnCompletedPayload;
      return { ...state, usage: { last: payload.usage, total: sumUsage(state.usage.total, payload.usage) } };
    }
    case "run-terminated": {
      const payload = event.payload as TerminatedPayload;
      return {
        ...state,
        status: "terminated",
        pendingApproval: undefined,
        pendingQuestion: undefined,
        entries: [...state.entries, { kind: "terminated", reason: payload.reason, turns: payload.turns_taken }],
      };
    }
    default:
      return state;
  }
}

function appendText(state: ChatState, kind: "assistant" | "reasoning", text: string): ChatState {
  const last = state.entries[state.entries.length - 1];
  return last?.kind === kind
    ? { ...state, entries: [...state.entries.slice(0, -1), { kind, text: last.text + text }] }
    : { ...state, entries: [...state.entries, { kind, text }] };
}

function sumUsage(a: TokenUsage, b: TokenUsage): TokenUsage {
  return {
    input_tokens: a.input_tokens + b.input_tokens,
    output_tokens: a.output_tokens + b.output_tokens,
    cached_tokens: a.cached_tokens + b.cached_tokens,
    reasoning_tokens: a.reasoning_tokens + b.reasoning_tokens,
  };
}
