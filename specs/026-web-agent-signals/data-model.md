# Phase 1 Data Model: Web Agent Signals

Frontend view-model additions only — **no backend/persistent model change**. All shapes under
`apps/web/src/`. Types mirror the **real** wire contract (`envelope.py`).

## api/types.ts (added / corrected)

```ts
// Reasoning increment — same shape as the output increment.
export interface ReasoningPayload {
  text: string;
  turn_index: number;
}

// Per-turn usage, reported on turn completion.
export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
}

export interface TurnCompletedPayload {
  turn_index: number;
  stop_reason: string;
  usage: TokenUsage;
}

// CORRECTED: the real wire field is `text` (+ `options`), not `prompt`.
export interface Question {
  text: string;
  options: string[];
}
export interface QuestionPayload {
  request_id: string;
  questions: Question[];
}
```

## ConversationEntry (extended)

```ts
export type ConversationEntry =
  | { kind: "user"; text: string }
  | { kind: "reasoning"; text: string }     // NEW — merged reasoning increments (de-emphasized block)
  | { kind: "assistant"; text: string }
  | { kind: "tool"; callId: string; name: string; outcome?: "success" | "failure" }
  | { kind: "terminated"; reason: string; turns: number };
```

## ChatState (extended)

```ts
export interface UsageState {
  last?: TokenUsage;     // most recent completed turn (per-turn indicator)
  total: TokenUsage;     // session running total
}

export interface ChatState {
  entries: ConversationEntry[];
  pendingApproval?: { requestId: string; toolName: string };
  pendingQuestion?: { requestId: string; prompt: string; options: string[] };  // prompt <- wire `text`; + options
  usage: UsageState;                                                             // NEW
  status: "idle" | "running" | "terminated" | "error";
}

export const ZERO_USAGE: TokenUsage = { input_tokens: 0, output_tokens: 0, cached_tokens: 0, reasoning_tokens: 0 };
export const initialState: ChatState = { entries: [], usage: { total: ZERO_USAGE }, status: "idle" };
```

### State transitions (additions to the unit-025 reducer; same events)

| Trigger | Effect |
|---|---|
| `assistant-reasoning-increment` | if last entry is `reasoning` → merge `text`; else append `{ kind: "reasoning", text }` |
| `turn-completed` | `usage.last = payload.usage`; `usage.total = sum(total, payload.usage)` (field-wise) |
| `question-asked` | `pendingQuestion = { requestId, prompt: questions[0].text, options: questions[0].options ?? [] }` |
| (unchanged) | user / assistant / tool / approval / terminated / unknown as in unit 025 |

**Invariants**: still pure (no I/O, spread for new objects); reasoning merges only across
consecutive reasoning increments (an intervening output/tool starts a new block); `usage.total` is
a monotonic field-wise sum; the question maps from the real `text`/`options` wire fields; absent
signals leave their structures empty (graceful — FR-008).

## Usage display rule

`UsageState` is rendered only when `total` has any non-zero field; otherwise hidden (a turn /
session with all-zero usage shows nothing — FR-006/008). The per-turn part shows `last`; the
session part shows `total`. Cached/reasoning sub-counts show only when non-zero.

## Question dialog inputs (reused answer contract)

| Dialog state | Produces | Maps to |
|---|---|---|
| Options present, one selected | `[option]` | `answerQuestion(id, reqId, answers)` |
| Options present, several selected | `[opt1, opt2, …]` | same (the wire `answers` is already a list) |
| No options | `[freeText]` | same (the unit-025 path) |
