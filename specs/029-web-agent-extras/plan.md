# Implementation Plan: Web Agent Parity Extras

**Branch**: `029-web-agent-extras` (main-only) | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/029-web-agent-extras/spec.md`

## Summary

The final **frontend-only** parity polish over units 025–028 — **no backend change, no ADR**. Four
self-contained additions, each consuming data/UI the app already has and degrading gracefully:

1. **i18n** — a tiny in-house locale module: a `t(key)` lookup over per-locale string maps
   (**English** + **Traditional Chinese**), a `useTranslation` hook + provider, a `LanguageSwitcher`,
   the choice persisted in `localStorage` (the unit-025 theme pattern), and a **fallback to English**
   for a missing key (never a blank or a raw key). Only UI chrome is localized; assistant content is
   not translated.
2. **Code syntax highlighting** — add `rehype-highlight` to the unit-025 `Markdown` component so
   fenced code blocks get **language-aware** highlighting; an unknown/absent language falls back to
   plain monospace (rehype-highlight's own behavior). A small set of `.hljs-*` token styles bound to
   the theme tokens (light/dark) is added to the stylesheet.
3. **Command palette** — the composer detects a leading `/` (frontend commands) or an `@` token
   (mentions) and shows a `CommandPalette`: `/` lists **frontend-doable** commands (toggle the
   inspection panel); `@` autocompletes **skills/tools** from the unit-027 inspection client
   (`inspectSkills`/`inspectTools`); selecting a command runs it, selecting a mention inserts
   `@<name>`. Backend-semantic commands (compact/schedule/plan) are **not** offered.
4. **Client-side cost estimate** — a bundled `pricing` table (model id → input/output price per
   1M tokens) + `estimateCost(usage, model)`; the unit-026 `UsageIndicator` shows an **estimated**
   cost (clearly labeled) from the unit-026 usage × the price for the session's selected model
   (unit 028); **no price entry → token counts only** (no cost), never authoritative.

Frontend-only: the web/API host, its event/endpoint contract, and the Python package are
**untouched**; the `apps/web` gate stays green. One new dependency (`rehype-highlight`); i18n,
palette, and pricing are in-house (no new dep). Each item degrades gracefully when its input is
absent (FR-009). Backend-semantic slash commands + authoritative server-side pricing + machine
translation of agent content are **out of scope**.

## Technical Context

**Language/Version**: TypeScript 5.6 + React 18 (the existing `apps/web` toolchain).

**Primary Dependencies**: React + Vite + Vitest + Testing Library + `react-markdown` + `remark-gfm`
(025/026). **New**: `rehype-highlight` (^7) for code highlighting (pulls `lowlight`/`highlight.js`).
i18n / command palette / pricing are **in-house** (no new dep).

**Storage**: `localStorage` for the locale choice (the unit-025 theme-persistence pattern; the
access token + theme are untouched).

**Testing**: Vitest + jsdom. New unit/component tests: the i18n `t()` lookup + fallback; the
`LanguageSwitcher`; the `Markdown` code block carries an `hljs`/language class; the `CommandPalette`
(slash commands; `@` autocomplete from a stubbed inspection client; backend-semantic absent); the
`pricing` `estimateCost` (+ a no-price fallback); the `UsageIndicator` shows the estimate. Existing
025–028 tests stay green (localized strings: tests query by stable roles/labels or the English
default).

**Target Platform**: the browser SPA (units 025–028).

**Project Type**: web frontend — additive presentation under `apps/web/src/`. Python untouched.

**Performance Goals**: highlighting bounded to the rendered block; i18n is an O(1) map lookup. No
hard numeric target.

**Constraints**: frontend-only (no backend/contract/Python change, FR-009); only UI chrome localized
(assistant content untranslated, FR-004); missing translation → English fallback (FR-003); palette
offers **only** frontend-doable actions (FR-007); cost is a **labeled estimate**, graceful when no
price (FR-008); each item degrades gracefully when its input is absent; no secret/legacy UI
committed (FR-010 / VII); the web gate stays green.

**Scale/Scope**: an i18n module + provider + switcher + two locale string maps; a Markdown
highlighting addition + token CSS; a `CommandPalette` + composer wiring; a `pricing` table + the
`UsageIndicator` cost; tests + docs/board. Four user stories P1–P4.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS** (no ADR).*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–010; SC-001–006). | PASS |
| II — Greenfield | All new modules/components written fresh; no legacy UI copied (VII). | PASS |
| III — Harness before automation | Presentational polish; no loop automation. | PASS |
| IV — Boundary Clarity | UI-only; the runtime/host seam is untouched (the palette/cost consume the existing client + events). | PASS |
| V — Tool Gateway Ownership | Untouched — the UI executes no tool (the palette `@`-mention only inserts a reference string). | PASS |
| VI — Event Bus Ownership | Untouched — the cost reads the existing unit-026 usage; no event change. | PASS |
| VII — Public-Safe | The bundled price table is public, generic numbers (no secret); no path/internal name; design fresh. | PASS |
| VIII — No SDK Replacement | `rehype-highlight` is a presentation plugin in the isolated `apps/web` toolchain, not the runtime. | PASS |
| IX — Reference, not clone | Conventional i18n / palette / highlighting, written for this app. | PASS |
| X — Testable Evolution | Per-item unit/component tests; **rollback** = revert the `apps/web` diff → the units-025–028 UI returns. | PASS |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/029-web-agent-extras/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   └── extras.md            # i18n / highlighting / palette / cost contracts
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/web/src/
├── i18n/
│   ├── i18n.tsx             # NEW — Locale type; en + zh-TW string maps; t(); I18nProvider + useTranslation; localStorage persist + English fallback
│   └── strings.ts           # NEW — the en + zh-TW UI-string maps (the single place to add a locale)
├── pricing.ts               # NEW — bundled price table (model -> per-1M input/output) + estimateCost(usage, model)
├── components/
│   ├── LanguageSwitcher.tsx # NEW — pick the UI language (in the header)
│   ├── CommandPalette.tsx   # NEW — slash commands + @-mention autocomplete (027 data)
│   ├── Markdown.tsx          # EDIT — add rehype-highlight (raw HTML still disabled)
│   ├── Composer.tsx          # EDIT — detect `/` and `@`; show the CommandPalette; run command / insert mention
│   ├── ChatHeader.tsx        # EDIT — host the LanguageSwitcher; pass the cost estimate to UsageIndicator
│   └── UsageIndicator.tsx    # EDIT — show the estimated cost when present (labeled an estimate)
├── main.tsx                  # EDIT — wrap <AppRoot/> in <I18nProvider>
└── App.tsx                   # EDIT — compute estimateCost(usage, selectedModel); pass a palette command (toggle inspect) + the inspection client to the Composer; use t() for key chrome
```

Tests (`apps/web/src/__tests__/`): `i18n.test.tsx`, `LanguageSwitcher.test.tsx`,
`CommandPalette.test.tsx`, `pricing.test.ts`, plus extensions to `Markdown.test.tsx` (hljs class)
and `UsageIndicator.test.tsx` (cost). Styles: `.hljs-*` token rules in `styles.css`.

Edited (docs / drift): `docs/web-frontend.md` (+ a parity-extras section), `CHANGELOG.md` (029),
`docs/loopplane-agent-board.md` (029 → Verified; the web-UI extension complete), `CLAUDE.md`
(marker → 029 plan).

**Structure Decision**: Each extra is a thin, additive layer over an existing surface — i18n wraps
the app in a provider + a `t()` lookup (in-house, so adding a locale is just another string map);
highlighting is a one-plugin addition to the unit-025 `Markdown`; the palette is a composer overlay
reading the unit-027 inspection client; the cost is a pure function over the unit-026 usage + the
unit-028 selected model. Nothing touches the backend or a runtime boundary (no ADR). Reverting the
`apps/web` diff restores the units-025–028 UI (X).

## Phases

- **Phase 0 — Research** (`research.md`): the in-house i18n decision (vs. a library) + the
  fallback/persist model; `rehype-highlight` (vs. a hand-rolled highlighter) + the theme-bound token
  CSS; the palette trigger/parse model + the @-mention source (027 skills/tools; `@file` has no
  frontend inventory → scoped to skills/tools); the client-side pricing/estimate model + the
  graceful no-price path; and the graceful-degradation rules.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): the `Locale`/string-map +
  `t()`; the palette-entry + parse model; the price-table + `estimateCost`; the contracts; and a
  quickstart.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD, P1 → P4 — i18n module + switcher + provider; Markdown
  highlighting + CSS; the CommandPalette + composer wiring; pricing + the UsageIndicator cost;
  docs/board; the web gate.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
