# Contract: Event → Ordered View Model

The reducer (`state/chat.ts`) is the single, pure mapping from the **existing** normalized event
stream to the ordered `entries` view model the UI renders. This contract pins that mapping so the
presentation layer and its tests can depend on it. **No event schema changes** — the inputs are the
unit-011/018 events verbatim.

## Inputs (unchanged normalized events)

| Event `type` | Payload fields used | View-model effect |
|---|---|---|
| `assistant-output-increment` | `text` | append/merge an `assistant` entry |
| `tool-call-started` | `call_id`, `tool_name` | append a `tool` entry (running) |
| `tool-call-completed` | `call_id`, `outcome` | set `outcome` on the matching running `tool` entry |
| `approval-requested` | `request_id`, `tool_name` | set `pendingApproval` |
| `question-asked` | `request_id`, `questions[0].prompt` | set `pendingQuestion` |
| `run-terminated` | `reason`, `turns_taken` | append a `terminated` entry; clear pending dialogs |
| _any other_ | — | ignored (state returned unchanged) |

Local (non-event) transitions: `userPrompt(text)` appends a `user` entry + sets `running`;
`errored()` sets `status = "error"`.

## Guarantees

1. **Order = stream order.** `entries` preserves the arrival order of events, so tool cards appear
   inline between the assistant text before and after them (FR-002, FR-003).
2. **Assistant merge boundary.** Consecutive `assistant-output-increment`s with no intervening
   entry coalesce into one `assistant` entry; an increment after a `tool` entry starts a new
   `assistant` entry (so a card separates the two message blocks).
3. **Tool lifecycle.** A `tool` entry is **running** while `outcome === undefined`, then
   **success**/**failure**. A `tool-call-completed` with no matching running entry (orphan or
   duplicate) is a **no-op** — the view never breaks (FR-016 / edge case).
4. **Terminated clears dialogs.** `run-terminated` clears any `pendingApproval`/`pendingQuestion`
   (the spec edge case "a run that ends while a dialog is pending").
5. **Error preserves history.** `errored()` only flips `status`; `entries` are retained so the
   error banner overlays the existing conversation (FR-010).
6. **Forward-compatible & pure.** Unknown event types return state unchanged; the reducer performs
   no I/O and mutates nothing (new objects via spread).

## Tool-card lifecycle (rendered by `ToolCard`)

```text
tool-call-started(call_id=c, tool_name=t)      → { kind:"tool", callId:c, name:t }            [running]
…assistant/tool entries may interleave…
tool-call-completed(call_id=c, outcome=success)→ same entry gains outcome:"success"           [success]
```

`ToolCard` shows the tool name + a running/success/failure status and is **collapsible** to reveal
detail; consecutive tool entries are visually grouped while each stays independently inspectable.

## Verification

`__tests__/chat.test.ts` (rewritten) asserts: a user→assistant→tool(running)→tool(completed)→
assistant interleave produces the expected ordered `entries`; an orphan/duplicate
`tool-call-completed` is a no-op; `run-terminated` appends the marker and clears a pending dialog;
an unknown event is ignored; `errored` keeps `entries`. These are pure-function assertions (no DOM).
