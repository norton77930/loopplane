# Quickstart: Web Agent Parity Extras

Validates the four frontend-only extras and proves the web gate stays green. No backend change.

## Prerequisites

- The `apps/web` toolchain installed (`cd apps/web && npm install` — pulls the new
  `rehype-highlight`).

## Automated gate (authoritative)

```bash
cd apps/web
npm run typecheck     # tsc --noEmit (strict) — clean
npm test              # vitest run — i18n / switcher / palette / pricing / markdown / usage suites pass
npm run build         # tsc + vite build — static assets emit
```

The Python suite is unaffected (frontend-only); `git diff` touches no `src/loopplane/**` or
`openspec/`.

## Manual QA (against a live host)

1. **i18n** — switch the language to Traditional Chinese; the UI chrome localizes; reload — the
   choice persists; a missing string falls back to English (FR-001/002/003, SC-001). Assistant
   output is not translated (FR-004).
2. **Highlighting** — send a prompt that returns fenced code with a language; the block renders
   **syntax-highlighted**; an unknown-language block renders as plain monospace (FR-005, SC-002).
3. **Palette** — type `/` in the composer → the frontend command(s) (toggle inspection) appear and
   selecting runs it; type `@` + a query → skill/tool matches from the inspection data autocomplete
   and selecting inserts `@<name>`; backend-semantic commands are absent (FR-006/007, SC-003).
4. **Cost** — with a selected model that has a bundled price, a completed turn shows an **estimated**
   cost next to the usage (labeled `est.`); a model with no price entry shows token counts only
   (FR-008, SC-004).

## Expected outcome

All four extras work and degrade gracefully (SC-001..004); the automated gate is green; the backend +
Python suite are untouched (SC-005); a public-safety scan is clean (SC-006).

## Rollback

Revert the `apps/web` diff (the i18n module + provider/switcher, the Markdown highlighting + CSS, the
CommandPalette + composer wiring, the pricing + UsageIndicator cost, and the `rehype-highlight` dep).
The units-025–028 UI returns; the backend and Python suite are untouched (Constitution X).
