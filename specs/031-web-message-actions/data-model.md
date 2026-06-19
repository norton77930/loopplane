# Data Model: Web Message Actions (031)

Frontend-only — no persisted entities, no new wire types. UI concepts only:

| Concept | Shape | Notes |
|---------|-------|-------|
| **Message action** | a per-message affordance: `Copy` (message text) or `Regenerate` (re-run the last user turn) | shown on hover; Regenerate enabled only when not running and a prior user turn exists |
| **Code-block action** | a `Copy` button on a fenced code block | copies the block's exact text, excluding surrounding prose |
| **Clipboard helper** | `copyText(text: string): Promise<boolean>` | `navigator.clipboard` with an `execCommand` fallback; resolves `false` on total failure (never throws) |

No reducer/state shape changes: `regenerate` reuses the existing `send()` path and the last
`{ kind: "user" }` entry from `state.entries`.
