# Quickstart: Web Agent UI

Validates the overhaul end-to-end against the **existing** backend and proves the web gate stays
green. Frontend-only — no backend change.

## Prerequisites

- Node 18+ and the `apps/web` toolchain installed (`cd apps/web && npm install` — this also pulls
  the new `react-markdown` + `remark-gfm`).
- A running unit-011 web/API host for manual QA (the demo/stub backend is fine — it emits the same
  normalized events). Optional for the automated gate, which stubs the network.

## Automated gate (authoritative)

```bash
cd apps/web
npm run typecheck     # tsc --noEmit (strict) — clean
npm test              # vitest run — reducer + component + App integration suites pass
npm run build         # tsc --noEmit && vite build — static assets emit
```

The Python suite is unaffected (frontend-only); from the repo root `pytest` remains green and
`git diff` touches no `src/loopplane/**` or `openspec/`.

## Manual QA (against a live host)

```bash
cd apps/web && npm run dev    # serves the SPA; point it at the unit-011 host
```

1. **Login** — with no token, a centered themed login card with a **masked** field is shown;
   submit a token → the app loads (FR-014; 023 behavior unchanged).
2. **Conversation** — send a prompt; the reply renders as **markdown** (headings/lists/tables/code/
   links), not raw text (FR-001, SC-001).
3. **Tool cards** — each tool call appears **inline** as a collapsible card going **running →
   success/failure**; consecutive calls group readably (FR-002/003, SC-001).
4. **Dialogs** — an approval shows **Allow / Deny / Always-allow-this-session**; a question shows a
   **free-text** field; answering resolves it (FR-004/005, SC-002).
5. **Terminal marker** — when the run ends, a clear **terminated** marker shows the reason
   (FR-006, SC-002).
6. **Status + Stop** — the header shows idle/running/terminated/error; **Stop** cancels an in-flight
   run (FR-009, SC-004).
7. **Error banner** — kill the host mid-stream; a **non-blocking** banner appears and the
   conversation already shown is preserved (FR-010).
8. **Scroll** — scroll up during streaming → a **jump-to-latest** affordance appears; at the bottom
   the view auto-scrolls (FR-011, SC-004).
9. **Sessions** — the sidebar lists sessions (recency) + **New chat**; an empty list shows an empty
   state; selecting one opens it (FR-008).
10. **Theme** — toggle light/dark → the whole UI switches; reload → the choice persists; clear the
    stored choice → it follows the OS preference (FR-013, SC-003).

## Expected outcome

All ten manual checks pass; the automated gate (typecheck + tests + build) is green; the backend and
the Python suite are untouched (SC-005). A public-safety scan of the diff is clean — no secret, path,
internal name, or copied legacy UI (SC-006).

## Rollback

Revert the `apps/web` presentation diff (the new components, the reducer evolution, the stylesheet,
and the two new deps). The api layer, the 023 auth gate, the backend, and the Python suite are
untouched, so the unstyled-but-functional unit-018/023 app returns (Constitution X).
