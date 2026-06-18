# Contract: Agent Signals (wire -> view-model -> presentation)

Pins how the three **existing** wire signals are consumed and rendered. Inputs are the unchanged
runtime events (`envelope.py`, via `serialize_event`); no event schema changes.

## Inputs (existing events)

| Event `type` | Payload fields used | View-model effect |
|---|---|---|
| `assistant-reasoning-increment` | `text` | append/merge a `reasoning` entry |
| `turn-completed` | `usage` (`input_/output_/cached_/reasoning_tokens`) | `usage.last = usage`; add into `usage.total` |
| `question-asked` | `questions[0].text`, `questions[0].options` | set `pendingQuestion = { requestId, prompt: text, options }` |

All other events behave exactly as in unit 025 (forward-compatible default unchanged — FR-010).

## Guarantees

1. **Reasoning is separate and ordered.** Reasoning increments merge into a `reasoning` entry that
   sits in stream order (before the turn's `assistant` answer), never merged into the answer
   (FR-001). It renders **de-emphasized** and **collapsible** (FR-002).
2. **No reasoning → nothing.** A turn with no `assistant-reasoning-increment` produces no
   `reasoning` entry and no block (FR-002 / FR-008).
3. **Usage is per-turn + total.** Each `turn-completed` updates `usage.last` and accumulates
   `usage.total` field-wise (FR-006/007). The indicator is shown only when `total` has a non-zero
   field; cached/reasoning sub-counts show only when present (FR-008 / edge cases).
4. **Question options select one-or-many.** When `options` is non-empty, the dialog renders
   selectable choices; submitting sends the selected option(s) as `answers` (FR-003/004). When
   empty, the free-text field is used (FR-005). The question text is read from the real `text`
   field (corrects the unit-018 `prompt` mis-mapping).
5. **Pure + forward-compatible.** The reducer remains pure over the same events; unknown
   types/extra fields are ignored (FR-010); removing the new rendering restores unit 025 (X).

## Presentation

| Signal | Component | Behavior |
|---|---|---|
| `reasoning` entry | `ReasoningBlock` | de-emphasized, collapsible, streamed (plain pre-wrapped text, distinct from the markdown answer) |
| `usage` | `UsageIndicator` (in `ChatHeader`) | compact per-turn (`last`) + session `total`; hidden when all-zero |
| question `options` | `QuestionDialog` | a select-one-or-many choice group + Send; free-text fallback when no options |

## Verification

- `chat.test.ts`: reasoning merge + interleave (user → reasoning → assistant); `turn-completed`
  sets last + accumulates total; a second turn accrues; `question-asked` maps `text` + `options`;
  absent signals leave empty structures.
- `ReasoningBlock.test.tsx`: renders text, toggles collapse; nothing when text empty.
- `UsageIndicator.test.tsx`: shows input/output (+ cached/reasoning when non-zero); hidden when
  all-zero.
- `QuestionDialog.test.tsx`: options render as choices and submit the selection (single + multi);
  no options → free-text submits a single answer.
- `MessageList.test.tsx`: a `reasoning` entry renders the block before the assistant answer.
