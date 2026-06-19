# Tasks: Web Message Actions

**Feature**: `specs/031-web-message-actions` | **Input**: plan.md, spec.md, research.md, data-model.md, contracts/

Frontend-only, no backend, no ADR. **TDD**: write the failing test before the implementation.
Stories P1 → P3 (US1 copy, US2 regenerate, US3 code-block copy).

## Phase 1: Setup

- [ ] T001 Establish a clean baseline: run `npm --prefix apps/web test` and confirm green before changes.

## Phase 2: Foundational (the clipboard helper, shared by US1 + US3)

- [ ] T002 [P] Write `apps/web/src/__tests__/clipboard.test.ts` (FAIL first): `copyText` resolves true via `navigator.clipboard.writeText`, and falls back to `execCommand` (resolving without throwing) when the async API is absent/rejects.
- [ ] T003 Create `apps/web/src/lib/clipboard.ts` (`copyText(text): Promise<boolean>` — async clipboard + `execCommand` fallback, never throws) to pass T002.

## Phase 3: User Story 1 — Copy a message (P1)

- [ ] T004 [P] [US1] Extend `apps/web/src/__tests__/MessageList.test.tsx` (FAIL first): a message exposes a **Copy** action that calls the clipboard helper with the message text (user + assistant).
- [ ] T005 [US1] Add a per-message **Copy** action (using `copyText`) to `apps/web/src/components/MessageList.tsx`, with brief confirmation.

## Phase 4: User Story 2 — Regenerate the latest response (P2)

- [ ] T006 [P] [US2] Extend `apps/web/src/__tests__/MessageList.test.tsx` (FAIL first): **Regenerate** invokes the handler; it is shown on the latest assistant message and disabled when `canRegenerate` is false.
- [ ] T007 [US2] Add `regenerate()` to `apps/web/src/App.tsx` (reverse-scan `state.entries` for the last `{ kind: "user" }`, call the existing `send()`; no-op while running or with no prior turn) and pass `onRegenerate` + `canRegenerate` to `MessageList`, which renders the Regenerate action.

## Phase 5: User Story 3 — Copy a code block (P3)

- [ ] T008 [P] [US3] Extend `apps/web/src/__tests__/Markdown.test.tsx` (FAIL first): a fenced code block renders a **copy button** that copies the block's exact text.
- [ ] T009 [US3] Override the `pre` renderer in `apps/web/src/components/Markdown.tsx` (`components={{ pre }}`) to add a copy button over fenced code (unit-029 highlighting unchanged).

## Phase 6: Polish & cross-cutting

- [ ] T010 Run the web gate: `npm --prefix apps/web run typecheck` + `test` + `build`.
- [ ] T011 [P] Add a "Message actions (unit 031)" section to `docs/web-frontend.md`.

## Dependencies

- **Foundational (T002–T003)** blocks US1 + US3 (both use the clipboard helper).
- **US1 / US2 / US3** are otherwise independent; US2 depends only on the existing send path.
- TDD: each `[P]` test precedes its implementation.

## Parallel opportunities

- T004 / T006 / T008 test tasks touch different test files / concerns and can be drafted in parallel.

## MVP scope

**US1** (copy a message) alone is a shippable increment; US2 (regenerate) and US3 (code-block copy)
complete the set.
