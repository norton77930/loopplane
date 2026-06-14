# Phase 1 Data Model: Web Frontend

TypeScript types under `apps/web/src`. They mirror the API's metadata-only shapes.

## Event types (`api/types.ts`)

A discriminated union by `type`, matching the normalized event envelope (only the
fields the UI renders are typed):

```
type RuntimeEvent =
  | { type: "user-input"; payload: { blocks: unknown[] } }
  | { type: "assistant-output-increment"; payload: { text: string; turn_index: number } }
  | { type: "tool-call-started"; payload: { call_id: string; tool_name: string } }
  | { type: "tool-call-completed"; payload: { call_id: string; outcome: "success" | "failure" } }
  | { type: "approval-requested"; payload: { request_id: string; tool_name: string; input_summary: string } }
  | { type: "question-asked"; payload: { request_id: string; questions: { prompt: string }[] } }
  | { type: "run-terminated"; payload: { reason: string; turns_taken: number } }
  | { type: string; payload: unknown }   // forward-compatible: unknown types are ignored
```

`SessionSummary = { session_id: string; last_active_at: string }`.

## Chat state (`state/chat.ts`)

```
interface ChatState {
  turns: { role: "user" | "assistant"; text: string }[];   // the conversation
  timeline: TimelineEntry[];                                // ordered, metadata-only
  pendingApproval?: { request_id: string; tool_name: string };
  pendingQuestion?: { request_id: string; prompt: string };
  status: "idle" | "running" | "terminated" | "error";
}

type TimelineEntry =
  | { kind: "assistant-turn"; turn: number }
  | { kind: "tool"; name: string; outcome?: "success" | "failure" }
  | { kind: "terminated"; reason: string; turns: number };

function reduce(state: ChatState, event: RuntimeEvent): ChatState   // pure
```

`reduce` folds the stream: assistant-output-increment appends to the current
assistant turn's text; tool-call-started/-completed add/close a timeline tool entry;
approval-requested/question-asked set the pending prompt; run-terminated sets status +
the terminal timeline entry. Unknown event types pass through unchanged.

## API client (`api/client.ts`)

```
class ApiClient {
  constructor(opts: { baseUrl: string; authHeader?: string; fetch?: typeof fetch });
  streamRun(prompt: string): AsyncIterable<RuntimeEvent>;          // POST /v1/runs/events (SSE)
  openSession(): Promise<{ session_id: string }>;
  streamSession(id: string): AsyncIterable<RuntimeEvent>;          // GET /v1/sessions/{id}/events
  submit(id: string, prompt: string): Promise<unknown>;
  answerApproval(id: string, requestId: string, decision: {...}): Promise<void>;
  answerQuestion(id: string, requestId: string, answers: string[]): Promise<void>;
  cancel(id: string): Promise<void>;
  listSessions(): Promise<SessionSummary[]>;
  history(id: string): Promise<unknown[]>;
}
```

The `fetch` is injectable so tests stub the network; the auth header is supplied at
construction (never baked into the bundle).

## Components (thin, over the state)

- `Conversation` — renders `state.turns`.
- `Timeline` — renders `state.timeline` (metadata only).
- `Prompts` — renders a pending approval/question and submits the response.
- `SessionList` — lists `SessionSummary[]` and opens one.
- `App` — wires the client + reducer to the components.
