# Phase 0 Research: Web Agent Signals

All decisions are grounded in the **actual** runtime event contract
(`src/loopplane/events/envelope.py`), which `serialize_event` dumps verbatim onto the SSE wire.
There were **no `[NEEDS CLARIFICATION]`** markers; the open items were how to model/render
signals the backend already emits.

## R1 — The wire shapes (grounded, not assumed)

From `envelope.py` (Pydantic → JSON via `serialize_event`):

| Signal | Event `type` | Payload (wire) |
|---|---|---|
| Reasoning | `assistant-reasoning-increment` | `{ text: string, turn_index: number }` |
| Usage | `turn-completed` | `{ turn_index: number, stop_reason: string, usage: TokenUsage }` |
| Question | `question-asked` | `{ request_id, questions: { text: string, options: string[] }[] }` |

`TokenUsage = { input_tokens, output_tokens, cached_tokens, reasoning_tokens }` (all `int`,
default `0`; `model/boundary.py`). These already cross the existing stream — **no backend change**
is needed, confirmed by reading the contract directly.

## R2 — Reasoning: a distinct, interleaved entry

- **Decision**: add a `reasoning` kind to the unit-025 `ConversationEntry` union; the reducer
  **merges** consecutive `assistant-reasoning-increment`s into one `reasoning` entry (exactly as
  it merges `assistant-output-increment`s), appending a new one when the previous entry is not a
  reasoning entry.
- **Rationale**: reasoning increments arrive **before** the turn's answer, so a separate
  `reasoning` entry naturally lands above the `assistant` entry in stream order — "streamed,
  visually separate from the final answer" (FR-001) for free, reusing the proven merge logic. A
  `ReasoningBlock` renders it de-emphasized + collapsible (FR-002); when a turn emits no reasoning,
  no entry exists, so nothing renders (graceful — FR-002/008).
- **Alternatives considered**: attaching reasoning text to the assistant entry (couples two
  distinct signals and loses the "separate block" requirement) — rejected.

## R3 — Token usage: a `{ last, total }` accumulator

- **Decision**: extend `ChatState` with `usage: { last?: TokenUsage; total: TokenUsage }`. On each
  `turn-completed`, set `last = payload.usage` and add it into `total` (field-wise sum). A
  `UsageIndicator` shows the **last turn** (per-turn — FR-006) and the **session total** (FR-007).
- **Rationale**: simplest model that satisfies both per-turn and session-total; O(1) per turn;
  one render location (the header) keeps it compact. **Graceful degradation**: usage is shown only
  when `total` has a non-zero field — a stub/demo provider that reports `TokenUsage()` (all zeros)
  shows **no indicator** (FR-006/008). Partial fields render only what is present (cached/reasoning
  shown when non-zero) (edge case).
- **Alternatives considered**: a per-turn usage entry appended into the conversation flow (clutters
  the transcript and duplicates the session total) — rejected in favor of a single header indicator.

## R4 — Question options: select one-or-many over the existing answer list

- **Decision**: render `options` as **selectable choices** (a checkbox-style group) plus a Send
  action; submit the selected option(s) as the existing `answers: string[]`. When `options` is
  empty, fall back to the unit-025 **free-text** field (FR-005). Also **correct the field**: read
  the question text from `questions[0].text` (the real wire field), not the unit-018 `prompt`.
- **Rationale**: the wire `Question` is `{ text, options }` with **no single/multi-select flag**,
  but `QuestionAnsweredPayload.answers` is **already a `list[str]`**. A select-one-or-many group
  submitting the selected set is the **contract-true** way to support both "choose one" (FR-003)
  and "choose several" (FR-004) without a backend change — selecting exactly one submits a
  single-element answer (matching the unit-025 free-text behavior), selecting several submits them
  together. The empty-options path is byte-identical to unit 025.
- **Contract note (for `/speckit-analyze`)**: FR-004 says a question may "indicate that multiple
  selections are allowed," but the wire `Question` carries **no such flag**. Rather than assume a
  backend change, the UI uniformly permits one-or-many selection (the `answers` list already allows
  it); this is the minimal, contract-faithful interpretation. A per-question single/multi flag would
  be a future backend addition.
- **Alternatives considered**: radio (single-select only) — cannot satisfy FR-004; auto-submit on
  click — loses multi-select and a confirm step. Rejected.

## R5 — Graceful degradation (FR-008) — the central correctness risk

Each signal is optional in the stream; each must vanish cleanly:

- no `assistant-reasoning-increment` → no `reasoning` entry → no block.
- `question.options` empty/absent → free-text field (the 025 path).
- `turn-completed.usage` all-zero (or no `turn-completed`) → no usage indicator.
- unknown event types / extra fields → ignored by the reducer's forward-compatible default
  (FR-010), unchanged from unit 025.

## R6 — No new dependency, no api-client change

- **Decision**: add only **types** to `api/types.ts` and fold the new events in the **reducer**;
  the `ApiClient` and the SSE parser (`events.ts`) are unchanged (they already yield every frame as
  a `RawEvent`). Reasoning text renders as plain, pre-wrapped text in the de-emphasized block
  (distinct from the markdown answer); no markdown/highlighter dependency is added here.

**Output**: all choices resolved against the real contract; no open clarifications.
