# Implementation Plan: Web Interaction Resilience & States

**Branch**: `032-web-interaction-resilience` (main-only autopilot) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/032-web-interaction-resilience/spec.md`

## Summary

Make interactions feel robust and finished, **entirely on the frontend**: promote the
approval/question dialogs to **true modals** (backdrop, focus trap, Esc-safe-cancel, keyboard-
navigable options, focus restored on close); add a **Retry** action to the connection-error banner
plus brief **toasts** for transient feedback; and add **loading skeletons**, a **richer empty
state**, and **first-run example prompts**. No backend change, no ADR. The final unit of the
product-polish sprint (030–032).

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (`apps/web`).

**Primary Dependencies**: none new — a small in-house `Modal` + `useFocusTrap` + `Toast` (no a11y/UI library).

**Storage**: none.

**Testing**: `vitest` (focus-trap + Esc + option keyboard nav; error Retry; toast show/dismiss; skeleton; empty-state prompt).

**Target Platform**: browser SPA.

**Project Type**: web frontend only — no backend, no event/endpoint change.

**Constraints**: frontend-only; Esc resolves to the safe default (deny/cancel) — never an implicit approval; the `apps/web` gate stays green; each item degrades gracefully.

**Scale/Scope**: 2 dialogs → modals, 1 banner + a toast system, skeleton/empty/onboarding states.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First** ✅ — traces to `spec.md` (FR-001…FR-009, SC-001…SC-006).
- **II. Greenfield** ✅ — written fresh; no legacy/private UI copied.
- **IV/V/VI. Boundaries** ✅ — no runtime boundary touched: modals/toasts/skeletons are presentational;
  Retry **reuses** the existing stream-establishment path (`ensureSession`/`readEvents`); the Tool
  Gateway (V) and Event Bus (VI) are untouched. No backend change.
- **VII. Public-Safe** ✅ — no private path/name/secret.
- **X. Testable Evolution** ✅ — Vitest covers modals, retry, toasts, skeletons, empty state;
  **rollback = revert the `apps/web` diff** → unit 031. **No ADR** (frontend-only).

**Result: PASS — no ADR, no Complexity Tracking entries.**

## Project Structure

### Documentation (this feature)

```text
specs/032-web-interaction-resilience/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/interaction-resilience.md
└── tasks.md            # (/speckit-tasks)
```

### Source Code (repository root)

```text
apps/web/src/
├── components/Modal.tsx        # new — backdrop + role="dialog" + aria-modal wrapper
├── hooks/useFocusTrap.ts       # new — trap Tab focus, Esc -> onClose, restore focus on unmount
├── components/Toast.tsx        # new — ToastProvider + useToast() + auto-dismissing container
├── components/Skeleton.tsx     # new — small shimmer placeholder
├── components/ApprovalDialog.tsx   # wrap body in Modal; Esc = deny
├── components/QuestionDialog.tsx   # wrap body in Modal; Esc = cancel; option keyboard nav
├── components/ErrorBanner.tsx      # gains onRetry
├── components/MessageList.tsx      # richer empty state + first-run example prompts (onExample)
├── components/Sidebar.tsx          # skeleton while loading
├── App.tsx                         # retry handler (re-establish stream); ToastProvider; loading flags; example prompts -> send
└── styles.css · i18n/strings.ts
```

**Structure Decision**: A small in-house modal + focus-trap + toast (no new dependency), wrapping
the existing unit-025/026 dialogs and banner, plus skeleton/empty/onboarding states.

## Complexity Tracking

> No Constitution violations — no entries. (Frontend-only; no ADR.)
