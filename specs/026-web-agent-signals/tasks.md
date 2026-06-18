---
description: "Task list for unit 026 — Web Agent Signals (frontend-only; reasoning / question options / token usage)"
---

# Tasks: Web Agent Signals

**Input**: Design documents from `specs/026-web-agent-signals/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/signals.md

**Tests**: REQUIRED (Constitution X). Vitest + jsdom. Write the reducer + component tests FIRST
and confirm they FAIL before implementing. The api-layer and unit-025 component tests stay green
(the question test event is corrected to the real `text`/`options` wire shape).

**Scope guard**: frontend-only under `apps/web/` — consumes events the backend **already emits**
(`assistant-reasoning-increment`, `turn-completed`, `question-asked` options; grounded in
`src/loopplane/events/envelope.py`); **no** backend/contract/Python change; **no** cost/pricing
(counts only). The web gate is green at the implement commit.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Confirm **no new dependency** — `apps/web/package.json` is unchanged (reuses
  unit-025's `react-markdown` + `remark-gfm`); ensure deps are installed for the gate.

---

## Phase 2: Foundational (shared types + reducer; tests first)

- [ ] T002 [P] Extend `apps/web/src/api/types.ts`: add `ReasoningPayload { text; turn_index }`,
  `TokenUsage { input_tokens; output_tokens; cached_tokens; reasoning_tokens }`,
  `TurnCompletedPayload { turn_index; stop_reason; usage }`; **correct** `Question` to
  `{ text: string; options: string[] }` and `QuestionPayload { request_id; questions: Question[] }`
  (the real wire shape; was the mis-named `prompt`).
- [ ] T003 Write the reducer tests FIRST (FAIL) in `apps/web/src/__tests__/chat.test.ts`: an
  `assistant-reasoning-increment` merges into a `reasoning` entry and interleaves before the
  `assistant` answer; `turn-completed` sets `usage.last` and accumulates `usage.total` field-wise
  across two turns; `question-asked` maps `questions[0].text` → `pendingQuestion.prompt` and carries
  `options`; absent signals leave empty structures; unknown events still ignored.
- [ ] T004 Extend `apps/web/src/state/chat.ts` per `data-model.md`: add the `reasoning` entry kind;
  add `UsageState` + `ZERO_USAGE` + `usage` on `ChatState`; add `options` to `pendingQuestion`
  (prompt from `text`); handle `assistant-reasoning-increment` (merge) and `turn-completed`
  (last + field-wise total); keep the reducer **pure**. Make T003 pass.

**Checkpoint**: the reducer models all three signals; the 025 flows still pass.

---

## Phase 3: User Story 1 - See the agent's reasoning (Priority: P1) 🎯 MVP

**Goal**: a distinct, de-emphasized, collapsible thinking block, streamed separately from the
answer.

**Independent Test**: reasoning increments render a streamed collapsible block above the answer;
no reasoning → no block.

- [ ] T005 [P] [US1] Write `apps/web/src/__tests__/ReasoningBlock.test.tsx` FIRST (FAIL): renders
  the reasoning text; toggles collapsed/expanded; renders nothing for empty text.
- [ ] T006 [US1] Create `apps/web/src/components/ReasoningBlock.tsx`: a de-emphasized, collapsible
  block rendering streamed reasoning as pre-wrapped text (distinct from the markdown answer)
  (FR-001/002). Make T005 pass.
- [ ] T007 [US1] Extend `apps/web/src/components/MessageList.tsx` to render a `reasoning` entry via
  `ReasoningBlock`; extend `MessageList.test.tsx` (a reasoning entry renders before the assistant
  answer).

**Checkpoint**: reasoning streams as a separate collapsible block; absent → nothing.

---

## Phase 4: User Story 2 - Answer a question with options (Priority: P2)

**Goal**: selectable option choices (single/multi) with a free-text fallback.

**Independent Test**: a question with options renders choices and submits the selection; without
options, the free-text field is used.

- [ ] T008 [P] [US2] Update `apps/web/src/__tests__/QuestionDialog.test.tsx`: with options, the
  choices render and selecting one (and selecting several) submits the chosen `answers`; with no
  options, the free-text field submits a single answer; the prompt comes from the question `text`.
- [ ] T009 [US2] Update `apps/web/src/components/QuestionDialog.tsx`: when `options` is non-empty,
  render a select-one-or-many choice group + Send (submits the selected option(s) as `answers`);
  when empty, the unit-025 free-text field (FR-003/004/005). `App` passes
  `pendingQuestion.options` and the answer handler accepts an array.

**Checkpoint**: option questions are answerable; the free-text path is unchanged.

---

## Phase 5: User Story 3 - See token usage (Priority: P3)

**Goal**: a per-turn usage indicator + a session total; hidden when absent.

**Independent Test**: a completed turn shows its usage; a session total accrues; an all-zero turn
shows nothing.

- [ ] T010 [P] [US3] Write `apps/web/src/__tests__/UsageIndicator.test.tsx` FIRST (FAIL): shows
  input/output for the last turn and the session total; shows cached/reasoning only when non-zero;
  renders nothing when the total is all-zero.
- [ ] T011 [US3] Create `apps/web/src/components/UsageIndicator.tsx` (per-turn `last` + session
  `total`, hidden when all-zero — FR-006/007/008) and host it in
  `apps/web/src/components/ChatHeader.tsx`; `App` passes `state.usage`.

**Checkpoint**: usage shows per-turn + total and degrades gracefully.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T012 Extend `apps/web/src/__tests__/App.test.tsx`: a run that streams a reasoning increment +
  a `turn-completed` renders the thinking block and a usage indicator; a question with options
  renders selectable choices — over a stubbed client.
- [ ] T013 [P] `docs/web-frontend.md`: add a **Signals (026)** section (reasoning block, question
  options, usage indicator).
- [ ] T014 [P] `CHANGELOG.md`: add a `026` entry under Added.
- [ ] T015 [P] `docs/loopplane-agent-board.md`: set **026 → Verified** with a status-evidence note;
  refresh §3/§4 to make **027** the active unit.
- [ ] T016 Run the gates: `apps/web` `npm run typecheck` + `npm test` + `npm run build` green;
  confirm the **Python suite is unchanged** (no `src/loopplane/**` diff); public-safety scan clean
  (no secret/path/internal name; no legacy UI copied).
- [ ] T017 Final review: confirm frontend-only (no backend/contract change), graceful degradation
  for each signal, and the rollback (revert the `apps/web` diff → unit 025); commit
  (`feat: implement LoopPlane web-agent-signals`).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T004)** precede all stories.
- **US1 (T005–T007)** is the MVP (reasoning) — depends on the reducer reasoning entry (T004).
- **US2 (T008–T009)** depends on the corrected question shape (T002/T004).
- **US3 (T010–T011)** depends on the usage accumulator (T004).
- **Polish (T012–T017)** depends on all three stories.

### Within each story

- Tests written first and FAIL before implementation (T003, T005, T008, T010).
- The web gate is green at the **implement commit**.

### Parallel opportunities

- T002 (types) is independent `[P]`; the three story test files (T005/T008/T010) are independent `[P]`.
- Docs T013/T014/T015 are independent `[P]` files.

---

## Implementation Strategy

MVP = US1 (reasoning, the highest-value "agent-like" signal). Then US2 (options) → US3 (usage) →
polish. Each story is additive and independently testable; each signal degrades gracefully when
its data is absent.

## Notes

- All three signals consume events the backend **already emits** (grounded in `envelope.py`); **no
  backend change**. The reducer stays a pure consumer-side fold (Constitution VI).
- The wire question field is `text` (+ `options`); unit-018 mis-modeled it as `prompt` (rendered
  empty against a real backend) — 026 corrects it.
- The wire `Question` has no single/multi-select flag, but `answers` is already a list — the dialog
  uniformly allows selecting one-or-many (contract-true).
- **Rollback**: revert the `apps/web` diff → the unit-025 app returns; backend + Python untouched (X).
