# Phase 1 Data Model: Web Agent Parity Extras

Frontend-only view/preference types. No backend/persistent model change.

## i18n (`apps/web/src/i18n/`)

```ts
export type Locale = "en" | "zh-TW";
export type StringKey = keyof typeof en;          // the key set is the English map's keys

// strings.ts — the single place to add a locale (FR-002):
export const en: Record<string, string> = { "composer.send": "Send", "header.inspect": "Inspect", ... };
export const zhTW: Record<string, string> = { "composer.send": "傳送", "header.inspect": "檢視", ... };
export const LOCALES: { id: Locale; label: string }[] = [ { id: "en", label: "English" }, { id: "zh-TW", label: "繁體中文" } ];

// i18n.tsx:
export function t(key: string, locale: Locale): string;   // active map[key] ?? en[key] ?? key (FR-003)
export function I18nProvider(props): JSX.Element;          // holds locale; persists to localStorage["loopplane-locale"]
export function useTranslation(): { t: (key: string) => string; locale: Locale; setLocale: (l: Locale) => void };
```

| Concept | Definition |
|---|---|
| Stored locale | `localStorage["loopplane-locale"]` ∈ `{ "en", "zh-TW" }`; absent → `"en"` (or the browser default if desired) |
| Lookup | `active[key] ?? en[key] ?? key` — English fallback, never blank (FR-003) |
| Scope | UI chrome only; assistant content is never passed through `t()` (FR-004) |

## Command palette (`CommandPalette`)

```ts
export type PaletteCommand = { id: string; label: string; run: () => void };

interface CommandPaletteProps {
  // the current composer text drives the trigger; the palette is shown when text starts with "/"
  // or contains a trailing "@<query>" token.
  text: string;
  commands: PaletteCommand[];                 // frontend-doable only (e.g. toggle inspection)
  loadMentions: (query: string) => Promise<string[]>;  // from 027 inspectSkills/inspectTools
  onRunCommand: (id: string) => void;
  onInsertMention: (name: string) => void;    // inserts "@<name>"
}
```

- `/` → list `commands` (frontend-doable); selecting calls `onRunCommand`.
- `@<query>` → `loadMentions(query)` returns matching skill/tool names; selecting calls
  `onInsertMention`. No data → no matches (graceful).
- Backend-semantic commands are simply **not** in `commands` (FR-007).

## Pricing / cost estimate (`apps/web/src/pricing.ts`)

```ts
export interface ModelPrice { input: number; output: number; }   // USD per 1,000,000 tokens
export const PRICE_TABLE: Record<string, ModelPrice> = { /* bundled, public example prices */ };

// null when model is null or absent from the table (graceful — FR-008):
export function estimateCost(usage: TokenUsage, model: string | null): number | null;
//   = model && PRICE_TABLE[model]
//       ? (usage.input_tokens * price.input + usage.output_tokens * price.output) / 1e6
//       : null;
```

The `UsageIndicator` (026) renders the estimate when non-null, e.g. `~$0.0123 (est.)`, alongside the
token totals; otherwise it shows the counts only. The estimate is always labeled `est.` and never
authoritative.

## State / wiring

| Field | Where | Meaning |
|---|---|---|
| `locale` | `I18nProvider` | the active UI language (persisted) |
| cost estimate | `App` → `ChatHeader` → `UsageIndicator` | `estimateCost(state.usage.total, selectedModel)` (028 model) |
| palette commands | `App` → `Composer` | `[{ id: "toggle-inspect", label, run: () => setShowInspect(...) }]` |
| mention source | `Composer` → `CommandPalette` | `loadMentions` over the 027 inspection client (skills + tools) |
