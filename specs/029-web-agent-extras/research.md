# Phase 0 Research: Web Agent Parity Extras

All frontend-only, building on units 025–027 (+ 028). No `[NEEDS CLARIFICATION]` markers; the open
items were library/approach choices.

## R1 — i18n: a small in-house module

- **Decision**: an in-house i18n — per-locale string maps (`en`, `zh-TW`), a `t(key, locale)` lookup,
  an `I18nProvider` + `useTranslation()` hook exposing `t` + `locale` + `setLocale`, the choice
  persisted in `localStorage["loopplane-locale"]` (the unit-025 theme pattern), and a **fallback to
  English** when a key is missing in the active locale (and to the key only as a last resort — but
  the maps are kept complete). A `LanguageSwitcher` (in the header) changes the locale.
- **Rationale**: a dictionary + lookup satisfies FR-001/002/003 with no dependency; "add a language"
  = add a string map (FR-002). Only UI chrome strings go through `t()`; assistant content is rendered
  as-is (FR-004). A library (react-i18next) is heavier than needed for two static locales.
- **Alternatives considered**: react-i18next / FormatJS (extra deps + config for a small static set)
  — rejected.

## R2 — Code syntax highlighting: rehype-highlight in the unit-025 Markdown

- **Decision**: add **`rehype-highlight`** to the unit-025 `Markdown` (`rehypePlugins={[rehypeHighlight]}`),
  keeping raw HTML disabled. It highlights fenced code by language and **falls back to plain text**
  for an unknown/absent language (its own behavior — FR-005). A small set of `.hljs` / `.hljs-*`
  token rules bound to the theme tokens (light/dark) is added to `styles.css` (no big prebuilt theme
  import, so it respects the unit-025 theme).
- **Rationale**: the idiomatic react-markdown highlighting path; language-aware + graceful by default;
  reuses the existing renderer. A hand-rolled highlighter is large and inferior.
- **Alternatives considered**: `react-syntax-highlighter` (replaces the renderer's code path, heavier);
  Prism/Shiki (heavier / async) — rejected for a markdown-integrated plugin.

## R3 — Command palette: trigger + parse + 027-sourced mentions

- **Decision**: the composer watches its text. A leading `/` opens the palette with the
  **frontend-doable** commands (currently: toggle the inspection panel). An `@` token (`@` + a query)
  opens autocomplete sourced from the unit-027 inspection client — **skills** (`inspectSkills`) and
  **tools** (`inspectTools`); selecting a command runs its callback, selecting a mention inserts
  `@<name>` into the prompt. **Backend-semantic** commands (compact/schedule/plan) are **not** listed
  (FR-007).
- **`@file` note**: the spec lists "`@file` / `@skill`", but unit 027 inspects skills/tools/MCP/memory
  — there is **no frontend file inventory** (unit-028 uploads use a capability model with no listing
  endpoint). So the mention source is **skills + tools** (the 027 data that exists); `@file` has no
  data source and is not offered. This is the faithful, data-backed reading of "autocomplete from the
  unit-027 inspection data".
- **Rationale**: reuses the 027 client; scoped to frontend actions so no backend is needed. Graceful:
  no inspection data → no `@` matches, the `/` commands still work (edge case).

## R4 — Client-side cost estimate

- **Decision**: a bundled **`pricing`** table mapping a model id → `{ input, output }` price per **1M
  tokens** + `estimateCost(usage, model) -> number | null` (`null` when `model` is null or has no
  entry). The unit-026 `UsageIndicator` shows the estimate (e.g., `~$0.0123 (est.)`) when non-null,
  computed from the unit-026 usage × the price for the **unit-028 selected model**; with no entry it
  shows token counts only (FR-008). The value is always **labeled an estimate** and never presented
  as authoritative.
- **Rationale**: reuses the 026 usage + the 028 selected model; a pure function is trivially testable.
  Prices drift, so it is explicitly a client-side estimate (server-side pricing is deferred).
- **Note**: the unit-026 `turn-completed` usage carries no model id, so the estimate uses the
  session's **selected model** (028) as the price key; the default host (no selection) has no price →
  no cost (graceful).

## R5 — Graceful degradation (FR-009)

- missing translation → English fallback (never blank/key); unknown code language → plain monospace;
  no 027 data → no `@` matches (palette still works for `/`); no price entry → token counts only.

## R6 — Dependencies

- **One new dep**: `rehype-highlight` (highlighting). i18n, the palette, and pricing are **in-house**
  (no new dep). Raw HTML stays disabled in the markdown (no injection — VII).

**Output**: all choices resolved; no open clarifications. `@file` is scoped to the data-backed
skills/tools mentions; authoritative pricing + backend-semantic commands are out of scope.
