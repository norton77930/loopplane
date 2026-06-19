# Tasks: Web Interaction Resilience & States

**Feature**: `specs/032-web-interaction-resilience` | **Input**: plan.md, spec.md, research.md, data-model.md, contracts/

Frontend-only, no backend, no ADR. **TDD**: write the failing test before the implementation.
Stories P1 → P3 (US1 true modals, US2 retry + toasts, US3 skeletons + empty/onboarding).

## Phase 1: Setup

- [ ] T001 Establish a clean baseline: run `npm --prefix apps/web test` and confirm green before changes.

## Phase 2: User Story 1 — True modals (P1)

- [ ] T002 [P] [US1] Write `apps/web/src/__tests__/useFocusTrap.test.tsx` (FAIL first): Esc calls `onClose`; Tab/Shift+Tab cycle focus within; focus is restored to the opener on unmount.
- [ ] T003 [US1] Create `apps/web/src/hooks/useFocusTrap.ts` to pass T002.
- [ ] T004 [P] [US1] Write `apps/web/src/__tests__/Modal.test.tsx` (FAIL first): renders `role="dialog"` + `aria-modal`; a backdrop click calls `onClose`.
- [ ] T005 [US1] Create `apps/web/src/components/Modal.tsx` (backdrop + focus-trapped panel) to pass T004.
- [ ] T006 [US1] Wrap `ApprovalDialog` in `Modal` (Esc → **deny**); extend `apps/web/src/__tests__/ApprovalDialog.test.tsx` (focus trapped; Esc denies).
- [ ] T007 [US1] Wrap `QuestionDialog` in `Modal` (Esc → **cancel**; options keyboard-navigable); extend `apps/web/src/__tests__/QuestionDialog.test.tsx`.

## Phase 3: User Story 2 — Retry + toasts (P2)

- [ ] T008 [P] [US2] Write/extend `apps/web/src/__tests__/ErrorBanner.test.tsx` (FAIL first): a **Retry** button fires `onRetry`.
- [ ] T009 [US2] Add an `onRetry` prop + Retry button to `apps/web/src/components/ErrorBanner.tsx`.
- [ ] T010 [P] [US2] Write `apps/web/src/__tests__/Toast.test.tsx` (FAIL first): `useToast().notify(msg)` shows a toast that auto-dismisses.
- [ ] T011 [US2] Create `apps/web/src/components/Toast.tsx` (`ToastProvider` + `useToast`) to pass T010.
- [ ] T012 [US2] Wire `App.tsx`: `retry()` re-establishes the stream via `ensureSession`/`readEvents` and clears the error (toast on failure); pass `onRetry` to `ErrorBanner`; wrap the tree in `<ToastProvider>`.

## Phase 4: User Story 3 — Skeletons, empty state, onboarding (P3)

- [ ] T013 [P] [US3] Extend `apps/web/src/__tests__/MessageList.test.tsx` (FAIL first): an empty conversation renders example prompts; clicking one calls `onExample`; `loading` shows a skeleton.
- [ ] T014 [US3] Create `apps/web/src/components/Skeleton.tsx` (shimmer placeholder).
- [ ] T015 [US3] Add a richer empty state + first-run example prompts (`onExample`) + a `loading` skeleton to `apps/web/src/components/MessageList.tsx`; `App` passes `onExample={send}` + a loading flag; `Sidebar` shows a skeleton while loading.

## Phase 5: Polish & cross-cutting

- [ ] T016 Run the web gate: `npm --prefix apps/web run typecheck` + `test` + `build`.
- [ ] T017 [P] Add an "Interaction resilience (unit 032)" section to `docs/web-frontend.md`.

## Dependencies

- **US1 (T002–T007)**, **US2 (T008–T012)**, **US3 (T013–T015)** are independent and can land in any
  order; within each, the `[P]` test tasks precede their implementation.
- TDD throughout; Polish (T016–T017) last.

## Parallel opportunities

- The test tasks T002 / T004 / T008 / T010 / T013 touch different files and can be drafted in parallel.

## MVP scope

**US1** (true modals) is the highest-impact, accessibility-critical increment; US2 (retry + toasts)
and US3 (skeletons + onboarding) complete the polish.
