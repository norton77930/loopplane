# Implementation Plan: Web Message Actions

**Branch**: `031-web-message-actions` (main-only autopilot) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/031-web-message-actions/spec.md`

## Summary

Give each message the actions of a modern agent app — **copy**, **regenerate**, and a
**code-block copy** button — **entirely on the frontend**. Copy uses the clipboard API (with a
fallback); regenerate re-runs the last user turn through the **existing** send path; the
code-block button copies the exact fenced code via react-markdown's component override. No
backend change, no ADR.

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (`apps/web`).

**Primary Dependencies**: existing `react-markdown` (component override for code blocks); **no new dependency**.

**Storage**: none.

**Testing**: `vitest` (clipboard helper, message copy, regenerate, code-block copy).

**Target Platform**: browser SPA.

**Project Type**: web frontend only — no backend, no event/endpoint change.

**Constraints**: frontend-only; reuse the existing `ApiClient.submit` send path; degrade gracefully when the clipboard API is unavailable; the `apps/web` gate stays green.

**Scale/Scope**: per-message hover affordances + a code-block button.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First** ✅ — traces to `spec.md` (FR-001…FR-007, SC-001…SC-005).
- **II. Greenfield** ✅ — written fresh; no legacy/private UI copied.
- **IV/V/VI. Boundaries** ✅ — no runtime boundary touched: regenerate **reuses** the existing
  submit path; the Tool Gateway (V) and Event Bus (VI) are untouched (the UI only consumes events
  it already receives). No backend change.
- **VII. Public-Safe** ✅ — no private path/name/secret.
- **X. Testable Evolution** ✅ — Vitest covers each action; **rollback = revert the `apps/web` diff**
  → unit 030. **No ADR** (frontend-only, no boundary crossed).

**Result: PASS — no ADR, no Complexity Tracking entries.**

## Project Structure

### Documentation (this feature)

```text
specs/031-web-message-actions/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/message-actions.md
└── tasks.md            # (/speckit-tasks)
```

### Source Code (repository root)

```text
apps/web/src/
├── lib/clipboard.ts            # new — copyText(): navigator.clipboard + execCommand fallback
├── components/MessageList.tsx  # per-message hover actions: Copy + Regenerate
├── components/Markdown.tsx     # code-block copy button via react-markdown components={{ pre }}
└── App.tsx                     # regenerate() — resubmit the last user turn via the existing send path

apps/web/src/__tests__/
├── clipboard.test.ts · MessageList.test.tsx (extend) · Markdown.test.tsx (extend)
```

**Structure Decision**: Small additive frontend edits to the unit-025 message list + markdown
renderer, plus a tiny `lib/clipboard.ts` helper and a `regenerate` handler in `App`.

## Complexity Tracking

> No Constitution violations — no entries. (Frontend-only; no ADR.)
