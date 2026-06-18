# Quickstart: Web Agent Signals

Validates the three signals end-to-end against the **existing** backend and proves the web gate
stays green. Frontend-only — no backend change.

## Prerequisites

- The `apps/web` toolchain installed (`cd apps/web && npm install`) — **no new dependency**.
- For manual QA of reasoning: a unit-011 host backed by a model that emits reasoning (the
  Anthropic adapter maps `thinking_delta`s). Reasoning/options/usage are otherwise validated by
  the component + reducer tests with canned events.

## Automated gate (authoritative)

```bash
cd apps/web
npm run typecheck     # tsc --noEmit (strict) — clean
npm test              # vitest run — reducer + new component + updated suites pass
npm run build         # tsc + vite build — static assets emit
```

The Python suite is unaffected (frontend-only); `git diff` touches no `src/loopplane/**` or
`openspec/`.

## Manual QA (against a live host)

1. **Reasoning** — send a prompt to a reasoning-emitting model; a **distinct, de-emphasized
   thinking block** streams above the answer and can be **collapsed** (FR-001/002, SC-001). With a
   non-emitting model, **no block** appears (graceful).
2. **Question options** — when the agent asks a question with options, the dialog shows
   **selectable choices**; selecting one (or several) and sending submits them; a question with no
   options shows the **free-text** field (FR-003/004/005, SC-002).
3. **Token usage** — after a turn, the header shows the **turn's usage** and a **session total**
   (input/output, plus cached/reasoning when present); a turn with all-zero usage shows **nothing**
   (FR-006/007/008, SC-003).

## Expected outcome

All three signals render when present and **vanish cleanly** when absent (SC-004); the automated
gate is green; the backend + Python suite are untouched (SC-005); a public-safety scan of the diff
is clean (SC-006).

## Rollback

Revert the `apps/web` diff (the reasoning entry + usage accumulator + question options + the two
new components). The unit-025 app returns; the backend and Python suite are untouched (X).
