# Implementation Plan: Web Agent Signals

**Branch**: `026-web-agent-signals` (main-only) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/026-web-agent-signals/spec.md`

## Summary

A **frontend-only** extension of the unit-025 UI that surfaces three signals the backend
**already emits** over the existing SSE stream but the unit-018/025 frontend ignores — **no
backend change**. Grounded in the actual runtime event contract
(`src/loopplane/events/envelope.py`, serialized verbatim by `serialize_event`):

1. **Reasoning / thinking** — the runtime emits `assistant-reasoning-increment` events
   (payload `{ text, turn_index }`; the Anthropic adapter maps `thinking_delta`s into them).
   The UI will render them as a distinct, de-emphasized, **collapsible thinking block**,
   streamed and **separate** from the final answer.
2. **Question options** — the `question-asked` payload's `questions[]` items are
   `{ text, options }` (the real wire shape; unit-018 mis-modeled this as `{ prompt }`, so the
   prompt has been rendering empty against a real backend). The question dialog will render
   **selectable option choices** with a **free-text fallback** when `options` is empty, and
   fix the field mapping (`text`).
3. **Token usage** — the runtime emits `turn-completed` events (payload
   `{ turn_index, stop_reason, usage }`, `usage = { input_tokens, output_tokens, cached_tokens,
   reasoning_tokens }`). The UI will show a **per-turn** usage indicator and a **session-level
   total**.

Each signal **degrades gracefully** when absent (FR-008): no reasoning → no thinking block; no
options → free-text; all-zero/absent usage → no indicator; unknown events still ignored
(FR-010). The api layer is extended only by **adding** the new event/field types (reusing the
client + SSE parser); the unit-025 reducer is extended to fold the new events into the existing
ordered `entries` plus a small usage accumulator. The web gate (`tsc --noEmit` + `vitest run` +
`vite build`) stays green; the Python suite and the backend contract are **untouched**.

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (the existing `apps/web` toolchain).

**Primary Dependencies**: **none new** — reuses unit-025's `react-markdown` + `remark-gfm` and
the existing toolchain. No backend dependency.

**Storage**: none new (theme + token persistence from units 023/025 are untouched).

**Testing**: Vitest + jsdom. New/updated unit tests: the reducer folding
`assistant-reasoning-increment` (merge + interleave), `turn-completed` (per-turn + session
usage), and the corrected `question-asked` (`text` + `options`); a `ReasoningBlock` (streams,
collapses, hidden when empty); the `QuestionDialog` (option choices single/multi + free-text
fallback); a `UsageIndicator` (per-turn + total; hidden when zero). The api-layer and 025
component tests stay green (the question test event is corrected to the real `text`/`options`
shape).

**Target Platform**: the browser SPA over the unit-011 `/v1` REST + SSE host.

**Project Type**: web frontend — additive view-model + presentation under `apps/web/src/`. The
Python package and the backend are untouched.

**Performance Goals**: streaming reasoning renders incrementally like the answer; usage
accumulation is O(1) per turn. No hard numeric target.

**Constraints**: frontend-only; consumes events/fields the backend **already emits** (verified
against `envelope.py`); the reducer stays **pure** over the same events (Constitution VI
consumer-side shaping); graceful degradation is mandatory (FR-008); unknown events ignored
(FR-010); no secret or legacy UI committed (FR-011 / VII); the web gate stays green and the
Python suite is unchanged (FR-009).

**Scale/Scope**: a reducer extension (reasoning entry + usage accumulator + corrected question),
two new components (`ReasoningBlock`, `UsageIndicator`), a `QuestionDialog` upgrade (options), new
api types, a small `App`/header wiring, and docs/board/changelog. Three user stories P1–P3.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–011; SC-001–006), grounded in `envelope.py`. | PASS |
| II — Greenfield | New components written fresh; no legacy UI copied (VII). | PASS |
| III — Harness before automation | Presentation of existing signals; no loop automation. | PASS |
| IV — Boundary Clarity | The UI still reaches the runtime only through the public web API (reused `ApiClient`). | PASS |
| V — Tool Gateway Ownership | Untouched — the UI executes no tool. | PASS |
| VI — Event Bus Ownership | Consumes **existing** normalized events (`assistant-reasoning-increment`, `turn-completed`, `question-asked` options) as a consumer; **no event schema change**. | PASS |
| VII — Public-Safe | No secret/path/internal name; reasoning/usage are metadata the backend already emits; design fresh. | PASS |
| VIII — No SDK Replacement | No runtime/framework change. | PASS |
| IX — Reference, not clone | Conventional thinking-block / usage UI, written for this app. | PASS |
| X — Testable Evolution | Reducer + component tests; **rollback** = revert the `apps/web` diff (025 UI returns; backend untouched). | PASS |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/026-web-agent-signals/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   └── signals.md           # the three wire signals -> view-model + presentation contract
├── checklists/requirements.md
└── tasks.md                 # created by /speckit.tasks
```

### Source Code (repository root)

```text
apps/web/src/
├── api/
│   └── types.ts              # EDIT — add ReasoningPayload, TurnCompletedPayload, TokenUsage; fix Question to { text, options }
├── state/
│   └── chat.ts               # EDIT — reasoning entry (merge); usage accumulator (last + total); question text/options; turn-completed
├── components/
│   ├── ReasoningBlock.tsx    # NEW — de-emphasized, collapsible, streamed thinking block
│   ├── UsageIndicator.tsx    # NEW — per-turn + session-total token usage (hidden when zero)
│   ├── QuestionDialog.tsx    # EDIT — option choices (select one/many) + free-text fallback
│   ├── MessageList.tsx       # EDIT — render the `reasoning` entry via ReasoningBlock
│   └── ChatHeader.tsx        # EDIT — host the UsageIndicator
└── App.tsx                   # EDIT — pass options to QuestionDialog; pass usage to the header
```

Tests (`apps/web/src/__tests__/`): `chat.test.ts` (extended), `QuestionDialog.test.tsx`
(updated for options + corrected field), new `ReasoningBlock.test.tsx`, `UsageIndicator.test.tsx`;
`MessageList.test.tsx` extended for the reasoning entry.

Edited (docs / drift): `docs/web-frontend.md` (+ a 026 signals section), `CHANGELOG.md`
(026 entry), `docs/loopplane-agent-board.md` (026 → Verified; advance §4 to 027), `CLAUDE.md`
(SPECKIT marker → 026 plan).

**Structure Decision**: This is purely **additive consumption** of events the backend already
produces — the reducer gains a `reasoning` entry kind (folded like `assistant`, so it interleaves
before the answer) and a small usage accumulator (`{ last?, total }`), and the question payload
mapping is **corrected** to the real wire shape (`text` + `options`). Two small components render
the new signals; the question dialog and message list are extended. No api-client or SSE-parser
change (only added types). Reverting the `apps/web` diff restores the unit-025 app — the backend
and Python suite are untouched (X).

## Phases

- **Phase 0 — Research** (`research.md`): the grounded wire shapes (from `envelope.py`); the
  reasoning-entry-vs-field decision (a distinct `reasoning` entry that interleaves in stream
  order); the usage model (`{ last, total }` accumulator over `turn-completed`, hidden when all
  zero); the question option-selection model (single/multi over the existing `answers: string[]`,
  since the wire `Question` carries no multi-select flag) + the `text` field correction; and the
  graceful-degradation rules.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the extended
  `ConversationEntry` (+ `reasoning`) and `ChatState` (+ `usage`); the corrected question shape;
  the signals contract (event → view-model → presentation); and a quickstart driving a
  reasoning-emitting backend + the web gate.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD, P1 → P3 — reducer reasoning + test; ReasoningBlock
  + MessageList wiring; question options + corrected field + dialog; usage accumulator + indicator
  + header; App wiring; docs/board; gates.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
