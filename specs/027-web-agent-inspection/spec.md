# Feature Specification: Web Agent Inspection Panels

**Feature Branch**: `027-web-agent-inspection` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-19

**Status**: Draft

**Input**: User description: "Make the agent's available capabilities and context inspectable from the web UI. The runtime already has the data internally — loaded skills (and their load problems), registered tools, connected MCP servers, and recalled memory/knowledge — but none of it is exposed over the web/API host, so the UI cannot show it. Add **additive, read-only** web/API inspection endpoints (skills, tools, MCP servers, memory) backed by new host query methods that compose the existing internal layers, and render them as read-only **inspection panels** in the unit-025 web UI (a right-side panel with tabs). Metadata-only — no secrets, no raw tool input/output, no file contents; the panels never execute a tool or mutate state. This is additive: the runtime core, the Tool Gateway, the Event Bus, and existing endpoints are unchanged. Out of scope (need a constitution ADR): model selection/switching and file upload. Also out of scope: executing or editing anything from the panels (read-only), and cost/pricing."

## Overview

The unit-025 / unit-026 web UI shows the **conversation** — messages, tool calls, dialogs,
reasoning, usage — but gives no view of the agent's **available capabilities and context**:
which **skills** are loaded (and whether any failed to load), which **tools** are registered,
which **MCP servers** are connected (and what they expose), and what **memory / knowledge**
has been recalled. A backend capability audit found that this data **already exists inside
the runtime** (the skills loader and `skill_problems`, the toolkit catalog, the MCP adapter,
and the recall/memory layer) but is **not exposed over the web/API host**, so the UI cannot
render it.

This unit makes that information **inspectable** from the web UI. It adds **additive,
read-only** web/API inspection endpoints — skills, tools, MCP servers, and memory — backed by
**new host query methods** that compose the existing internal layers, and renders them as
**read-only inspection panels** in the unit-025 shell (a right-side panel with tabs). It is
**metadata-only**: no secrets, credentials, raw tool input/output, or file contents are
exposed, and the panels **never execute a tool or mutate state** — the Tool Gateway
(Constitution V) and the Event Bus (Constitution VI) are untouched. The change is **purely
additive**: the runtime core, the gateway, the event bus, and existing endpoints are
unchanged, and the Python suite stays green. Model selection/switching and file upload — which
would need a constitution ADR — and any execute/edit action from the panels are **out of
scope**. The design is **written fresh** — **no private or legacy UI is copied**
(Constitution VII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the agent's skills and tools (Priority: P1)

A signed-in user opens an inspection panel and sees **what the agent can do**: the **loaded
skills** (with any that failed to load surfaced as a problem) and the **registered tools**
(name and a short descriptor) — so they understand the agent's capabilities before and during
a run.

**Why this priority**: Knowing the agent's tools and skills is the most useful inspection and
the data is already available internally (the skills loader, `skill_problems`, and the toolkit
catalog) — the highest value for an additive, read-only change.

**Independent Test**: With skills and tools configured, a read-only endpoint returns the
skills (with load problems) and the registered tools as metadata, and the panel lists them;
with none configured, the panel shows an empty state.

**Acceptance Scenarios**:

1. **Given** skills are loaded, **When** the user opens the skills panel, **Then** each skill is listed and any skill that failed to load is surfaced as a problem.
2. **Given** tools are registered, **When** the user opens the tools panel, **Then** each tool is listed by name with a short descriptor.
3. **Given** the inspection endpoints, **When** they respond, **Then** the payload is metadata-only and no tool is executed.

### User Story 2 - See connected MCP servers (Priority: P2)

A user opens the MCP panel and sees the **configured/connected MCP servers** and the **tools
each exposes**, so they know which external tool sources are wired in.

**Why this priority**: MCP servers are a key external capability source; surfacing them builds
on the same additive endpoint pattern as US1.

**Independent Test**: With MCP servers configured, a read-only endpoint lists them and the
tools they expose; with none, the panel shows an empty state.

**Acceptance Scenarios**:

1. **Given** MCP servers are configured, **When** the user opens the MCP panel, **Then** each server is listed with the tools it exposes (metadata-only).
2. **Given** no MCP servers, **When** the user opens the MCP panel, **Then** a clear empty state is shown.

### User Story 3 - Browse and search memory (Priority: P3)

A user opens the memory panel and **browses or searches** the recalled memory / knowledge
entries (source and a snippet), so they can see what context the agent is drawing on.

**Why this priority**: Memory visibility is valuable for trust and debugging; it reuses the
existing recall layer and is the most involved of the three (a query), so it is sequenced
last.

**Independent Test**: With memory entries present, a read-only endpoint lists/searches them
(metadata/snippets); a query filters the results; with none, the panel shows an empty state.

**Acceptance Scenarios**:

1. **Given** memory/knowledge entries exist, **When** the user opens the memory panel, **Then** entries are listed with a source and a snippet (metadata-only).
2. **Given** a search query, **When** the user submits it, **Then** the listed entries are filtered to the query.
3. **Given** no entries, **When** the user opens the memory panel, **Then** a clear empty state is shown.

### Edge Cases

- **No skills / tools / MCP servers / memory** → each panel shows a clear empty state, not an error.
- **A skill that failed to load** → surfaced as a problem in the skills panel (the existing `skill_problems` data).
- **A request without (or with wrong) authentication** → rejected by the existing auth boundary; no data leaks.
- **Metadata-only guarantee** → no secrets, credentials, raw tool input/output, file contents, or private paths appear in any inspection payload.
- **Large lists / many memory entries** → the panel scrolls or paginates and stays responsive.
- **An internal layer is absent** (e.g., no MCP configured at all) → the corresponding endpoint returns an empty result, not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The web/API host MUST expose a **read-only** endpoint listing the **loaded skills** and **any skill load problems**, as **metadata only**.
- **FR-002**: The web/API host MUST expose a **read-only** endpoint listing the **registered tools** (name and a short descriptor), as **metadata only**.
- **FR-003**: The web/API host MUST expose a **read-only** endpoint listing the **configured/connected MCP servers** and the **tools each exposes**, as **metadata only**.
- **FR-004**: The web/API host MUST expose a **read-only** endpoint to **list and search memory / knowledge entries** (source and snippet), as **metadata only**.
- **FR-005**: Each inspection endpoint MUST be backed by a **host query method** that composes the **existing** internal layers (skills loader, toolkit catalog, MCP adapter, recall/memory) — no new runtime capability.
- **FR-006**: The web UI MUST present these as **read-only inspection panels** (e.g., a tabbed right-side panel) within the unit-025 shell.
- **FR-007**: Every inspection endpoint and panel MUST be **metadata-only** — no secrets, credentials, raw tool input/output, or file contents — and MUST **never execute a tool or mutate state** (the Tool Gateway, Constitution V, and the Event Bus, Constitution VI, are untouched).
- **FR-008**: Inspection endpoints MUST honor the **existing auth boundary** (a request without/with-wrong credentials is rejected; per-principal scoping is applied where the underlying data is principal-scoped).
- **FR-009**: Each panel MUST **degrade gracefully** to a clear **empty state** when there is nothing to show.
- **FR-010**: The change MUST be **additive** — no change to the runtime core, the Tool Gateway, the Event Bus, or existing endpoints; existing tests stay green and the **Python suite remains green**; the `apps/web` gate stays green.
- **FR-011**: **No committed artifact** may contain a private path, internal name, IP, key, token, or secret, and **no private or legacy UI may be copied** — the design is written fresh.

### Key Entities

- **Skill info**: a loaded skill's metadata (name, brief descriptor) plus any load problem.
- **Tool descriptor**: a registered tool's metadata (name, short description) — never its execution.
- **MCP server info**: a configured/connected MCP server (name) and the tools it exposes.
- **Memory entry preview**: a recalled memory/knowledge entry's source and a snippet (metadata only).
- **Inspection panel**: a read-only web-UI surface (a tab) that renders one of the above lists.

### Out of Scope

- **Model selection / switching** — needs runtime + host-interface changes and a **constitution ADR** (Principle III / VIII); a later unit.
- **File upload / attachments** — needs a content-model + storage + endpoint change and a **constitution ADR** (Principle IV); a later unit.
- **Executing or editing anything from the panels** — these are **read-only**; no running a tool/skill, no editing memory, no changing config.
- **Cost / pricing** — not part of inspection.
- **Any change to the runtime core, the Tool Gateway, the Event Bus, or existing endpoints** — the unit is strictly additive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in user can open panels that list the agent's **skills (with load problems)**, **registered tools**, **MCP servers (and their tools)**, and **memory entries** — each from a read-only endpoint.
- **SC-002**: Every inspection endpoint returns **metadata only**, is **auth-gated**, and **executes no tool / mutates no state** (verified by tests).
- **SC-003**: Each panel shows a **clear empty state** when there is nothing to show.
- **SC-004**: The change is **additive** — the runtime core, the Tool Gateway, the Event Bus, and existing endpoints are **unchanged**, and the **Python suite stays green**.
- **SC-005**: The `apps/web` gate (**type check + component tests + build**) is **green**.
- **SC-006**: **No committed artifact** contains a private path, internal name, IP, key, token, or secret (a **clean scan**), and **no private or legacy UI is copied**.

## Assumptions

- **Composes existing internal layers**: the data is already produced internally (the skills loader and `skill_problems`, the toolkit catalog, the MCP adapter, the recall/memory layer); this unit adds **additive host query methods** and **read-only web/API endpoints** over them — no new runtime capability (confirmed by a backend capability audit).
- **Additive transport, no constitution boundary crossed**: the inspection endpoints are an additive transport over the host (the unit-011 pattern), are metadata-only, execute no tool (V), and re-emit no live bus (VI), so **no ADR is required** (unlike model switching / file upload).
- **Builds on unit 025**: the panels live in the unit-025 shell (a right-side panel); sequenced after 025 (and 026).
- **Auth-consistent**: inspection honors the existing unit-022 auth boundary; principal-scoped data (e.g., memory) is scoped consistently with how it is owned.
- **Additive, reversible**: removing the endpoints and panels restores the prior UI; the backend and the Python suite are otherwise unaffected (Constitution X rollback).
- **Fresh design**: the implementation is **written fresh** with **no private or legacy UI copied** (Constitution VII).
