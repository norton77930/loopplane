# Feature Specification: Web Agent Parity Extras

**Feature Branch**: `029-web-agent-extras` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "The remaining frontend-only polish that brings the web UI to parity with a modern agent app, none of it needing a backend change or an ADR: (1) internationalization — localize the UI strings with a language switcher (at least English and Traditional Chinese, with structure to add more); (2) code syntax highlighting — language-aware highlighting for fenced code blocks in assistant markdown; (3) a command palette — slash commands and @-mentions for the frontend-doable actions: toggle the inspection panel, and @file / @skill autocomplete that reads the unit-027 inspection data, with a palette UI (backend-semantic commands like compacting a conversation or scheduling are out of scope — they need backend support); (4) a client-side cost estimate — multiply the unit-026 token usage by a bundled price table to show an estimated cost, with authoritative server-side pricing left as a future refinement. All frontend-only, building on units 025–027."

## Overview

After units 025–027 (the overhaul, the extra signals, and the inspection panels) and unit 028
(model selection + attachments), the web UI matches the core of a modern agent app. What
remains to reach **parity** is a set of **frontend-only** refinements that need **no backend
change and no ADR** — they consume what the UI already has:

1. **Internationalization (i18n)** — the UI strings are **localized** with a **language
   switcher** (at least **English** and **Traditional Chinese**, with the structure to add
   more), and the choice is remembered.
2. **Code syntax highlighting** — fenced code blocks in assistant markdown get **language-aware
   highlighting**, building on the unit-025 markdown rendering.
3. **A command palette** — **slash commands** and **@-mentions** for the **frontend-doable**
   actions: toggle the inspection panel, and **@file / @skill** autocomplete that reads the
   **unit-027** inspection data, presented through a palette UI. Backend-semantic commands
   (compacting a conversation, scheduling, plan mode) are **out of scope** — they need backend
   support.
4. **A client-side cost estimate** — the **unit-026** token usage multiplied by a **bundled
   price table** to show an **estimated** cost alongside usage; authoritative **server-side
   pricing** is a future refinement (out of scope).

Every item is **frontend-only**: it consumes data and surfaces the UI already has (markdown,
the unit-026 usage, the unit-027 inspection lists) and changes **nothing** on the backend — the
web/API host, its event/endpoint contract, and the Python package are **untouched**, and the
`apps/web` toolchain and its isolated CI gate are reused. The design is **written fresh** —
**no private or legacy UI is copied** (Constitution VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use the app in your language (Priority: P1)

A user switches the UI language and the interface strings are shown in that language; the
choice is remembered across reloads. At least **English** and **Traditional Chinese** are
available, and adding another language is a matter of providing its strings.

**Why this priority**: Localization is the broadest parity item, touches the whole UI, and is
purely presentational — high value, no risk.

**Independent Test**: Switch the language — UI strings change; reload — the choice persists;
add a language's strings — it appears in the switcher.

**Acceptance Scenarios**:

1. **Given** the app, **When** the user selects a language, **Then** the UI strings render in that language and the choice persists across reloads.
2. **Given** at least English and Traditional Chinese, **When** the switcher is opened, **Then** both are listed; **And** model/agent content (assistant output) is not machine-translated — only UI chrome is localized.

### User Story 2 - Read code with syntax highlighting (Priority: P2)

A user receives an assistant message containing fenced code; the code block is rendered with
**language-aware syntax highlighting**, making it easier to read.

**Why this priority**: Highlighting noticeably improves readability of agent output and is a
self-contained addition to the existing markdown renderer.

**Independent Test**: An assistant message with a fenced code block (with a language hint)
renders highlighted; a block with no/unknown language renders as plain monospace (graceful).

**Acceptance Scenarios**:

1. **Given** a fenced code block with a language, **When** it renders, **Then** it is syntax-highlighted for that language.
2. **Given** a fenced block with no or an unknown language, **When** it renders, **Then** it falls back to plain monospace without error.

### User Story 3 - Command palette (slash & @-mentions) (Priority: P3)

A user types `/` or `@` in the composer and a **palette** offers the **frontend-doable**
actions: a slash command to **toggle the inspection panel**, and **@file / @skill** that
**autocomplete from the unit-027 inspection data**; selecting one inserts/triggers it.

**Why this priority**: A command palette is a power-user affordance that reuses the 027
inspection data; it is scoped to frontend-only actions so it needs no backend.

**Independent Test**: Typing `/` shows the available frontend commands and `@file`/`@skill`
autocomplete from the inspection lists; selecting one performs the action / inserts the
reference; backend-semantic commands are absent (out of scope).

**Acceptance Scenarios**:

1. **Given** the composer, **When** the user types `/`, **Then** a palette lists the frontend-doable commands (e.g., toggle the inspection panel) and selecting one performs it.
2. **Given** the composer, **When** the user types `@file` or `@skill`, **Then** matches autocomplete from the unit-027 inspection data and selecting one inserts the reference.
3. **Given** a backend-semantic command (e.g., compact/schedule), **When** the palette is shown, **Then** it is **not** offered (explicitly out of scope).

### User Story 4 - See an estimated cost (Priority: P4)

A user sees an **estimated cost** for a turn / the session, computed **client-side** from the
unit-026 **token usage** and a **bundled price table**, shown next to the usage; it is clearly
an **estimate**.

**Why this priority**: A cost estimate is useful context and reuses the 026 usage data; it is
last because it is an approximation pending server-side pricing.

**Independent Test**: With token usage present and a price entry for the model, an estimated
cost is shown; with no price entry, only the token counts are shown (graceful); the value is
labeled an estimate.

**Acceptance Scenarios**:

1. **Given** token usage and a bundled price for the model, **When** a turn completes, **Then** an **estimated** cost is shown alongside the usage.
2. **Given** no price entry for the model, **When** a turn completes, **Then** the token counts are shown without a cost (no error), and the estimate is never presented as authoritative.

### Edge Cases

- **A missing translation string** → falls back to the default language (English), never a blank or a key.
- **An unknown code language** → plain monospace fallback.
- **A very large highlighted block** → stays performant (scrolls/collapses), no UI jank.
- **`@file`/`@skill` with no inspection data** (027 unavailable) → the mention simply offers no matches (graceful), the palette still works for frontend commands.
- **A price table missing the current model** → token counts shown, no cost estimate.
- **Right-to-left or long-word languages** (future) → layout tolerates longer strings without breaking.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST **localize its interface strings** and provide a **language switcher**; the choice MUST be **remembered** across reloads.
- **FR-002**: At least **English** and **Traditional Chinese** MUST be available, and adding a language MUST be a matter of **providing its strings** (no code change to the switch mechanism).
- **FR-003**: A **missing translation** MUST **fall back** to the default language, never showing a blank or a raw key.
- **FR-004**: Only **UI chrome** is localized; **assistant/agent content is not machine-translated**.
- **FR-005**: Fenced **code blocks** in assistant markdown MUST be rendered with **language-aware syntax highlighting**, falling back to plain monospace for no/unknown language.
- **FR-006**: The composer MUST offer a **command palette**: typing `/` lists the **frontend-doable** commands (e.g., toggle the inspection panel) and typing `@file` / `@skill` **autocompletes from the unit-027 inspection data**; selecting an entry performs the action or inserts the reference.
- **FR-007**: **Backend-semantic** commands (e.g., compact, schedule, plan mode) MUST **not** be offered by the palette (they are out of scope and need backend support).
- **FR-008**: The UI MUST show an **estimated cost** computed **client-side** from the unit-026 token usage and a **bundled price table**, clearly **labeled an estimate**; with no price entry it MUST show token counts only (no cost), never presenting the estimate as authoritative.
- **FR-009**: Every item MUST be **frontend-only** — no change to the web/API host, its event/endpoint contract, or the Python package; the `apps/web` gate MUST stay green; each item **degrades gracefully** when its inputs are absent.
- **FR-010**: **No committed artifact** may contain a private path, internal name, IP, key, token, or secret, and **no private or legacy UI may be copied**.

### Key Entities

- **Locale**: a language's UI strings plus the remembered active selection (English + Traditional Chinese to start).
- **Highlighted code block**: a fenced code block rendered with language-aware highlighting (plain fallback).
- **Palette entry**: a frontend-doable slash command or an `@file`/`@skill` mention sourced from the unit-027 inspection data.
- **Cost estimate**: a client-side estimate = token usage × a bundled price-table entry, labeled an estimate.

### Out of Scope

- **Backend-semantic slash commands** (compact a conversation, schedule, plan mode) — need backend support; a later unit.
- **Authoritative server-side pricing** — the cost shown here is a **client-side estimate**; a server pricing source is a future refinement.
- **Machine translation of assistant/agent content** — only UI chrome is localized.
- **Any backend change** — the web/API host, its events/endpoints, and the Python package are unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can switch the UI language between at least **English and Traditional Chinese**, the choice **persists**, and a missing string **falls back** without a blank/key.
- **SC-002**: Assistant code blocks render with **language-aware highlighting**, with a plain fallback for unknown languages.
- **SC-003**: The composer offers a **palette** for frontend commands and `@file`/`@skill` autocomplete from the unit-027 data; backend-semantic commands are **absent**.
- **SC-004**: An **estimated** cost is shown from the unit-026 usage and a bundled price table, **labeled an estimate**, with a graceful no-price fallback.
- **SC-005**: Every item is **frontend-only** — the `apps/web` gate (type check + tests + build) is **green**, and the **Python suite and the backend contract are unchanged**.
- **SC-006**: **No committed artifact** contains a private path, internal name, IP, key, token, or secret (a **clean scan**), and **no private or legacy UI is copied**.

## Assumptions

- **Builds on 025–027**: reuses the unit-025 shell + markdown, the unit-026 token usage (for the cost estimate), and the unit-027 inspection data (for `@file`/`@skill`); sequenced after them.
- **Frontend-only, no ADR**: every item is presentational or consumes existing data; nothing touches a runtime boundary, so **no ADR and no backend change** is needed (unlike 028).
- **Estimate, not invoice**: the cost is an explicit client-side **estimate** from a bundled price table; prices drift, so it is never presented as authoritative (server-side pricing is deferred).
- **Additive, reversible**: removing these restores the units-025–028 UI; the backend and Python suite are unaffected (Constitution X rollback).
- **Fresh design, public-safe (VII)**: the implementation is written fresh; no private or legacy UI is copied.
