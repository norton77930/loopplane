# Research: Web Message Actions (031)

Grounded in the current `apps/web`. No NEEDS CLARIFICATION remain.

## D1 — Regenerate the last response (frontend-only)

**Decision**: Add a `regenerate()` to `App` that reverse-scans `state.entries` for the last
`{ kind: "user" }` entry and re-runs it via the **existing** `send()` path (`ApiClient.submit`
over the live session); disabled while a run is in flight and when there is no prior user turn.

**Rationale**: Re-running a turn is the existing submit action with a remembered prompt — no new
endpoint, no backend change. `App.send` and the `userPrompt` reducer already take a plain string.

**Alternatives**: a dedicated `/regenerate` endpoint — rejected (needs backend; the existing
submit re-runs the turn already).

## D2 — Copy a message (graceful)

**Decision**: A tiny `lib/clipboard.ts` `copyText(text)` using `navigator.clipboard.writeText`
with a `document.execCommand("copy")` textarea fallback when the async clipboard API is
unavailable or rejects.

**Rationale**: The async Clipboard API is not universally available (older browsers, insecure
contexts); the `execCommand` fallback keeps copy working without an unhandled error (FR-002).

## D3 — Code-block copy button

**Decision**: Override the `pre` renderer via react-markdown `components={{ pre }}` in
`Markdown.tsx` to wrap each fenced block with a copy button that copies the block's exact text;
the unit-029 `rehype-highlight` highlighting is unchanged.

**Rationale**: react-markdown already supports component overrides; the `pre` node's text content
is the exact code — copyable without re-deriving it. No new dependency.

**Alternatives**: a rehype plugin to inject buttons — rejected (heavier; the component override is
local and dependency-free).

## D4 — No new dependency / no ADR

Nothing new is added to `package.json`; no runtime boundary is crossed (the UI consumes events it
already receives and reuses the existing send path) → **no ADR**. Rollback = revert the diff.
