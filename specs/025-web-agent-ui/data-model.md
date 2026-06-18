# Phase 1 Data Model: Web Agent UI

Frontend view-model and preference entities only — **no backend/persistent model changes**. All
shapes live under `apps/web/src/`. Types mirror the spec's Key Entities.

## ConversationEntry (the ordered view model)

A discriminated union; one ordered list replaces the current parallel `turns` + `timeline`. Order
is **stream order** — the sequence the normalized events arrive in.

```ts
export type ConversationEntry =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }   // markdown source; built by merging output increments
  | { kind: "tool"; callId: string; name: string; outcome?: "success" | "failure" }
  | { kind: "terminated"; reason: string; turns: number };
```

| Field | Entry kind | Notes |
|---|---|---|
| `text` | user / assistant | user = the submitted prompt; assistant = concatenated increments (rendered as markdown) |
| `callId` | tool | the `call_id` from `tool-call-started`; used to match the later `tool-call-completed` |
| `name` | tool | `tool_name`; shown on the card header |
| `outcome` | tool | `undefined` = **running**; set to `"success" \| "failure"` on completion |
| `reason` / `turns` | terminated | the run's terminal reason + turn count |

## ChatState (evolved)

```ts
export interface ChatState {
  entries: ConversationEntry[];                                  // NEW — ordered, interleaved
  pendingApproval?: { requestId: string; toolName: string };     // unchanged
  pendingQuestion?: { requestId: string; prompt: string };       // unchanged (single prompt)
  status: "idle" | "running" | "terminated" | "error";           // unchanged
}

export const initialState: ChatState = { entries: [], status: "idle" };
```

`turns` and `timeline` are **removed**; everything renders from `entries`. `pendingApproval`,
`pendingQuestion`, and `status` keep their unit-018 meaning.

### State transitions (pure reducer over the same events)

| Trigger | Effect on `entries` | Effect on other fields |
|---|---|---|
| `userPrompt(text)` (local) | append `{ kind: "user", text }` | `status = "running"` |
| `assistant-output-increment` | if last entry is `assistant` → merge `text`; else append `{ kind: "assistant", text }` | — |
| `tool-call-started` | append `{ kind: "tool", callId, name }` (running) | — |
| `tool-call-completed` | set `outcome` on the matching `tool` entry (same `callId`, `outcome === undefined`); **no-op if no match** (duplicate / orphan tolerated) | — |
| `approval-requested` | — | set `pendingApproval` |
| `question-asked` | — | set `pendingQuestion` (`questions[0].prompt`) |
| `run-terminated` | append `{ kind: "terminated", reason, turns }` | `status = "terminated"`; **clear** `pendingApproval` + `pendingQuestion` |
| `errored()` (local) | — | `status = "error"` (entries preserved) |
| unknown event | — | unchanged (forward-compatible default) |

**Invariants**: pure (no I/O, no mutation — new objects via spread); idempotent for a duplicate
`tool-call-completed` (the `outcome === undefined` guard); a terminated run never leaves a dialog
pending (the spec edge case); `errored` preserves `entries` (the error banner overlays an intact
conversation — FR-010).

## ThemePreference

```ts
export type Theme = "light" | "dark";              // the resolved, applied theme
export type StoredTheme = Theme | null;            // localStorage value; null = "follow system"
```

| Concept | Definition |
|---|---|
| Stored value | `localStorage["loopplane-theme"]` ∈ `{ "light", "dark" }`, or absent = follow system |
| Resolution | stored value if present; else `matchMedia("(prefers-color-scheme: dark)")` → `"dark"`, else `"light"` |
| Application | `document.documentElement.setAttribute("data-theme", resolved)` |
| Toggle | flip resolved → write the new value to `localStorage` → re-apply |
| Failure mode | any storage / matchMedia access wrapped in `try/catch`; on failure resolve to `"light"` (no throw) |

## Decision / dialog inputs (reused contract)

No new persistent model — these are call shapes the dialogs produce, all already on `ApiClient`:

| Dialog | Produces | Maps to |
|---|---|---|
| Approval — Allow | `{ allow: true, scope: "once" }` | `answerApproval(id, reqId, decision)` |
| Approval — Deny | `{ allow: false }` | same |
| Approval — Always allow this session | `{ allow: true, scope: "session" }` | same (existing `scope` field) |
| Question — answer | `[answerText]` | `answerQuestion(id, reqId, answers)` (single-element array) |

## Session summary (reused, unchanged)

`SessionSummary { session_id: string; last_active_at: string }` from `api/types.ts` — rendered in
the sidebar with recency; selecting one opens it (history replay + live stream, R6).
