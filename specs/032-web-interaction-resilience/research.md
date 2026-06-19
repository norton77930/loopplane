# Research: Web Interaction Resilience & States (032)

Grounded in the current `apps/web`. No NEEDS CLARIFICATION remain.

## D1 — True modals (in-house, no dependency)

**Decision**: A small `Modal` component (a backdrop + `role="dialog"` + `aria-modal="true"`) and a
`useFocusTrap(onClose)` hook (trap Tab/Shift+Tab within the dialog, **Esc → onClose**, restore focus
to the previously-focused element on unmount). Wrap the existing `ApprovalDialog`/`QuestionDialog`
bodies; **Esc resolves to the safe default** (deny for approval, cancel for the question).

**Rationale**: The dialogs already render inline; promoting them is additive presentational +
behavior. An in-house trap avoids a new dependency (the repo deliberately avoids heavy deps) and the
safe-default Esc guarantees dismissal can never imply approval (FR-002).

**Alternatives**: a focus-trap / headless-UI library — rejected (a new dependency for a small,
well-understood behavior).

## D2 — Connection retry

**Decision**: `ErrorBanner` gains an `onRetry`; `App` passes a handler that re-establishes the live
stream via the existing `ensureSession` / `readEvents` path and clears the error status. A failed
retry surfaces a toast and preserves the conversation.

**Rationale**: Reuses the existing stream-establishment path — no backend change. The current banner
is passive text; a Retry makes the failure recoverable (FR-004).

## D3 — Toasts

**Decision**: A `ToastProvider` (context) + `useToast()` returning `notify(message)`, rendering a
container of brief, **auto-dismissing** toasts (a few seconds). Used for rename/delete/copy success
and retry failure.

**Rationale**: A lightweight in-house toast (context + timeout) is enough; no dependency. Auto-dismiss
keeps it non-intrusive (FR-005).

## D4 — Loading skeletons, empty state, first-run prompts

**Decision**: A small `Skeleton` shimmer used by `Sidebar`/`MessageList` while loading; a richer
empty conversation view in `MessageList` with **example-prompt chips** that call the existing `send()`
(passed as `onExample`).

**Rationale**: Skeletons make fetches feel responsive; example prompts lower the blank-page barrier
(FR-006/007). All presentational, reusing the existing send path.

## D5 — Pre-existing gap (out of scope)

Re-opening a past session renders empty (the unit-011 `history` endpoint is metadata-only). The
richer empty state here is **not** a fix for that — restoring history content needs a backend
decision; explicitly out of scope (noted in `spec.md`).

## No new dependency / no ADR

Nothing is added to `package.json`; no runtime boundary is crossed → **no ADR**. Rollback = revert
the diff.
