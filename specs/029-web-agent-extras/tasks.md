---
description: "Task list for unit 029 — Web Agent Parity Extras (frontend-only; i18n / highlighting / palette / cost)"
---

# Tasks: Web Agent Parity Extras

**Input**: Design documents from `specs/029-web-agent-extras/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/extras.md

**Tests**: REQUIRED (Constitution X). Vitest + jsdom. Write the per-feature tests FIRST and confirm
they FAIL. Existing 025–028 tests stay green (query by stable roles/labels or the English default).

**Scope guard**: **frontend-only** under `apps/web/` — no backend/contract/Python change. One new
dep (`rehype-highlight`); i18n / palette / pricing are in-house. Each item **degrades gracefully**
when its input is absent. The web gate (`tsc` + `vitest` + `vite build`) is green at the implement
commit.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 [P] Add `rehype-highlight` (^7) to `apps/web/package.json`; run `npm install`; confirm the
  baseline gate runs. i18n / command palette / pricing add **no** dependency.

---

## Phase 2: User Story 1 - Use the app in your language (Priority: P1) 🎯 MVP

**Goal**: localized UI chrome + a language switcher (en + zh-TW), persisted, with an English fallback.

**Independent Test**: switch language → strings change; reload → persists; a missing key → English.

- [ ] T002 [P] [US1] Write `apps/web/src/__tests__/i18n.test.tsx` FIRST (FAIL): `t(key)` returns the
  active locale's string; a key missing in zh-TW falls back to English; the provider persists the
  choice to `localStorage` and restores it.
- [ ] T003 [US1] Create `apps/web/src/i18n/strings.ts` (the `en` + `zh-TW` UI-string maps + `LOCALES`)
  and `apps/web/src/i18n/i18n.tsx` (`t(key, locale)` with English fallback; `I18nProvider` persisting
  `localStorage["loopplane-locale"]`; `useTranslation()`). Make T002 pass.
- [ ] T004 [US1] Create `apps/web/src/components/LanguageSwitcher.tsx`; wrap `<AppRoot/>` in
  `<I18nProvider>` in `apps/web/src/main.tsx`; host the switcher in `ChatHeader`; route the key chrome
  strings (composer Send/placeholder, header labels, Inspect, dialog actions, empty states) through
  `useTranslation().t`. Add `apps/web/src/__tests__/LanguageSwitcher.test.tsx`.

**Checkpoint**: the UI localizes between en + zh-TW, persists, and falls back.

---

## Phase 3: User Story 2 - Read code with syntax highlighting (Priority: P2)

**Goal**: language-aware highlighting of assistant code blocks, with a plain fallback.

**Independent Test**: a fenced block with a language renders highlighted; unknown → plain monospace.

- [ ] T005 [US2] Add `rehype-highlight` to `apps/web/src/components/Markdown.tsx`
  (`rehypePlugins={[rehypeHighlight]}`, raw HTML still disabled); add theme-bound `.hljs` / `.hljs-*`
  token rules to `apps/web/src/styles.css`. Extend `apps/web/src/__tests__/Markdown.test.tsx`: a
  ` ```js ` block's `<code>` carries an `hljs` (+ language) class; an unknown language renders without
  error.

**Checkpoint**: code blocks highlight by language; unknown languages fall back cleanly.

---

## Phase 4: User Story 3 - Command palette (slash & @-mentions) (Priority: P3)

**Goal**: a composer palette — `/` frontend commands + `@` skill/tool autocomplete from 027 data.

**Independent Test**: `/` lists frontend commands; `@q` autocompletes from inspection; selecting
works; backend-semantic commands absent.

- [ ] T006 [P] [US3] Write `apps/web/src/__tests__/CommandPalette.test.tsx` FIRST (FAIL): `/` lists
  the frontend command(s) and selecting calls `onRunCommand`; `@q` shows matches from a stubbed
  `loadMentions` and selecting calls `onInsertMention("<name>")`; a backend-semantic command (e.g.
  "compact") is not present.
- [ ] T007 [US3] Create `apps/web/src/components/CommandPalette.tsx` (trigger on leading `/` or a
  trailing `@<query>`; render commands / mention matches; keyboard/click select). Wire it into
  `apps/web/src/components/Composer.tsx`; `apps/web/src/App.tsx` supplies the frontend command
  (`toggle inspection`) and a `loadMentions(query)` reading `client.inspectSkills` + `inspectTools`
  (027); selecting a mention inserts `@<name>` into the composer text.

**Checkpoint**: the palette offers frontend commands + 027-sourced mentions; backend-semantic absent.

---

## Phase 5: User Story 4 - See an estimated cost (Priority: P4)

**Goal**: a client-side estimated cost from the 026 usage × a bundled price table, labeled an estimate.

**Independent Test**: usage + a price entry → an estimated cost; no entry → counts only (no error).

- [ ] T008 [P] [US4] Write `apps/web/src/__tests__/pricing.test.ts` FIRST (FAIL): `estimateCost`
  computes `(input*price.input + output*price.output)/1e6` for a priced model; returns `null` for an
  unknown/null model.
- [ ] T009 [US4] Create `apps/web/src/pricing.ts` (`PRICE_TABLE` + `estimateCost(usage, model)`);
  extend `apps/web/src/components/UsageIndicator.tsx` to show a labeled estimate when a `cost` prop is
  non-null; `apps/web/src/App.tsx` computes `estimateCost(state.usage.total, selectedModel)` and
  passes it through `ChatHeader` → `UsageIndicator`. Extend
  `apps/web/src/__tests__/UsageIndicator.test.tsx` (shows the labeled estimate; hides it when null).

**Checkpoint**: an estimated cost shows when priced; token counts only otherwise.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T010 [P] `docs/web-frontend.md`: add a **Parity extras (029)** section (i18n / highlighting /
  palette / cost).
- [ ] T011 [P] `CHANGELOG.md`: add a `029` entry under Added.
- [ ] T012 [P] `docs/loopplane-agent-board.md`: set **029 → Verified** with a status-evidence note;
  mark the **web-UI extension (025–029) COMPLETE** in §3/§4 and the banner.
- [ ] T013 Run the gates: `apps/web` `npm run typecheck` + `npm test` + `npm run build` green;
  confirm the **Python suite is unchanged** (no `src/loopplane/**` diff); public-safety scan clean
  (the bundled price table is generic public numbers; no secret/path/internal name; no legacy UI
  copied — VII).
- [ ] T014 Final review: confirm **frontend-only**, graceful degradation for each item, and the
  rollback (revert the `apps/web` diff → units 025–028); commit
  (`feat: implement LoopPlane web-agent-extras`).

---

## Dependencies & Execution Order

- **Setup (T001)** precedes the stories.
- **US1 (T002–T004)** is the MVP (i18n) and independent.
- **US2 (T005)** is an independent Markdown addition.
- **US3 (T006–T007)** reuses the 027 inspection client (skills/tools).
- **US4 (T008–T009)** reuses the 026 usage + the 028 selected model.
- **Polish (T010–T014)** depends on all four stories; the web gate runs green before the commit.

### Within each story / parallel opportunities

- Tests first and FAIL before implementation (T002, T006, T008).
- T002 / T006 / T008 are independent `[P]`; docs T010/T011/T012 are independent `[P]` files.

---

## Implementation Strategy

MVP = US1 (i18n — the broadest parity item). Then US2 (highlighting) → US3 (palette) → US4 (cost) →
polish. Each is a thin additive layer over an existing surface and degrades gracefully.

## Notes

- i18n is in-house (a string map + `t()` + provider + switcher); adding a locale = adding a map.
- Highlighting is `rehype-highlight` on the unit-025 `Markdown`; unknown languages fall back to plain.
- The palette is scoped to **frontend-doable** actions + 027-sourced skill/tool mentions;
  backend-semantic commands are out of scope (FR-007); `@file` has no frontend inventory.
- The cost is a **client-side estimate** (026 usage × a bundled price for the 028 selected model),
  labeled an estimate; no price entry → counts only. Server-side pricing is deferred.
- **Rollback**: revert the `apps/web` diff → the units-025–028 UI returns; backend + Python untouched (X).
