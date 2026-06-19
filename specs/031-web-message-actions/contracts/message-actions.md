# Contract: Web Message Actions (031)

Frontend component/helper contracts. No HTTP/API change (the backend, its events, and endpoints
are untouched).

## `lib/clipboard.ts`

```text
copyText(text: string): Promise<boolean>
  # navigator.clipboard.writeText(text); on absence/rejection, fall back to a hidden
  # <textarea> + document.execCommand("copy"). Resolves true on success, false on total
  # failure. Never throws.
```

## `MessageList`

- Each message row exposes, on hover, a **Copy** action (copies the message text via `copyText`)
  and — for the latest assistant response — a **Regenerate** action.
- New props: `onRegenerate?: () => void` and `canRegenerate?: boolean` (App passes a handler and
  gates it on "not running and a prior user turn exists"). Copy is self-contained in the component.

## `Markdown`

- Fenced code blocks render with a **copy button** (via `components={{ pre }}`) that copies the
  block's exact text; the unit-029 highlighting is unchanged. Non-code markdown is unaffected.

## `App`

- `regenerate()` finds the last `{ kind: "user" }` entry in `state.entries` and calls the existing
  `send(text)`; it is a no-op when running or when there is no prior user turn.
