# Contract: Web Interaction Resilience & States (032)

Frontend component/hook contracts. No HTTP/API change (the backend, its events, and endpoints are
untouched).

## `hooks/useFocusTrap.ts`

```text
useFocusTrap(onClose: () => void): RefObject<HTMLDivElement>
  # Attach the ref to the dialog container. While mounted: Tab/Shift+Tab cycle focus within;
  # Escape calls onClose; on unmount, focus returns to the previously-focused element.
```

## `components/Modal.tsx`

```text
Modal({ onClose, label, children }): a backdrop + a focus-trapped panel
  role="dialog", aria-modal="true", aria-label={label}; clicking the backdrop calls onClose.
```

## `components/Toast.tsx`

```text
<ToastProvider> wraps the app; useToast() -> { notify(message: string) }.
  Each toast auto-dismisses after a few seconds; multiple stack.
```

## `components/ApprovalDialog` / `QuestionDialog`

- Rendered inside `Modal`. **Esc** resolves the **safe default** — approval → deny; question →
  cancel (no answer). Options are keyboard-navigable; focus returns to the opener on close.

## `components/ErrorBanner`

```text
ErrorBanner({ onRetry?: () => void })
  # Shows a Retry button when onRetry is given; clicking it re-establishes the stream.
```

## `components/MessageList`

- New prop `onExample?: (prompt: string) => void`: an empty conversation renders a richer empty
  state with example-prompt chips that call `onExample` (App routes it to `send`).
- New prop `loading?: boolean`: shows a `Skeleton` while history loads.

## `App`

- `retry()` re-establishes the stream via `ensureSession`/`readEvents` and clears the error; on
  failure it `notify`s a toast. Wraps the tree in `<ToastProvider>`.
