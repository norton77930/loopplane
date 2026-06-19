# Data Model: Web Interaction Resilience & States (032)

Frontend-only — no persisted entities, no new wire types. UI concepts only:

| Concept | Shape | Notes |
|---------|-------|-------|
| **Modal** | `Modal({ onClose, label, children })` | backdrop + `role="dialog"` + `aria-modal`; uses `useFocusTrap` |
| **Focus trap** | `useFocusTrap(onClose: () => void)` → `ref` | traps Tab within; Esc → `onClose`; restores focus on unmount |
| **Toast** | `{ id: number; message: string }` + `useToast().notify(message)` | auto-dismissing (a few seconds) |
| **Skeleton** | `Skeleton({ rows? })` | shimmer placeholder while loading |
| **Example prompt** | a string chip in the empty state | clicking it calls the existing `send(prompt)` |

No reducer/state shape changes. Retry reuses `ensureSession`/`readEvents`; the error status already
exists in the unit-025 view model.
