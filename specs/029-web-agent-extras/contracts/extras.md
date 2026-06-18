# Contract: Parity Extras (frontend-only)

Four additive, frontend-only features over units 025–028. No backend/contract change; each degrades
gracefully when its input is absent.

## i18n (FR-001–004)

- A `t(key)` lookup over per-locale string maps (`en`, `zh-TW`); `useTranslation()` exposes
  `t`/`locale`/`setLocale`; the `LanguageSwitcher` changes the locale; the choice persists in
  `localStorage`.
- **Fallback**: `active[key] ?? en[key] ?? key` — a missing translation falls back to English, never
  a blank (FR-003). Adding a locale = adding a string map (FR-002).
- **Scope**: only UI chrome is localized; assistant/agent content is never translated (FR-004).

## Code syntax highlighting (FR-005)

- The unit-025 `Markdown` adds `rehype-highlight` (raw HTML still disabled). A fenced block with a
  language is highlighted (its `<code>` carries `hljs` + a language class); an unknown/absent
  language falls back to plain monospace. `.hljs-*` token styles are theme-bound (light/dark).

## Command palette (FR-006/007)

- The composer shows a palette when its text starts with `/` (frontend commands) or has a trailing
  `@<query>` (mentions).
- `/` → the **frontend-doable** commands (toggle the inspection panel); selecting runs it.
- `@<query>` → **skill/tool** matches from the unit-027 inspection client (`inspectSkills` +
  `inspectTools`); selecting inserts `@<name>`. No 027 data → no matches (the `/` commands still
  work).
- **Backend-semantic** commands (compact/schedule/plan) are **never** listed (FR-007). `@file` has no
  frontend inventory and is not offered (the mentions are the data-backed skills/tools).

## Client-side cost estimate (FR-008)

- A bundled `PRICE_TABLE` (model → per-1M input/output) + `estimateCost(usage, model)` (`null` when
  no model/entry). The unit-026 `UsageIndicator` shows the estimate (labeled `est.`) from the
  unit-026 usage × the price for the unit-028 selected model; **no price entry → token counts only**,
  never authoritative (FR-008).

## Frontend-only guarantee (FR-009)

- No web/API host, event/endpoint, or Python change; the `apps/web` gate (`tsc` + `vitest` + `vite
  build`) stays green; the Python suite is unchanged. One new dep (`rehype-highlight`); i18n/palette/
  pricing are in-house. Reverting the `apps/web` diff restores the units-025–028 UI (X).

## Verification

- `i18n.test.tsx`: `t()` returns the active locale's string; a missing key falls back to English;
  the provider persists + restores the locale.
- `LanguageSwitcher.test.tsx`: lists en + zh-TW; selecting changes the rendered strings.
- `Markdown.test.tsx` (extended): a fenced ` ```js ` block's `<code>` carries an `hljs`/language
  class; an unknown language still renders (no error).
- `CommandPalette.test.tsx`: `/` lists the frontend command(s) and selecting runs it; `@q`
  autocompletes from a stubbed inspection client and selecting inserts `@<name>`; a backend-semantic
  command is absent.
- `pricing.test.ts`: `estimateCost` computes from usage × price; returns `null` for an unknown model.
- `UsageIndicator.test.tsx` (extended): shows the labeled estimate when a cost is supplied; hides it
  when null.
