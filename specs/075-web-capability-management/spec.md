# Feature Specification: Web Capability Management

**Feature Branch**: `[075-web-capability-management]`

**Created**: 2026-06-29

**Status**: Draft

**Input**: User description: "Continue the parity roadmap after 074 with web capability management: expand the web inspection surface into first-class settings for memory, skills, MCP configuration, projects/workspaces, schedules, and host-provided model defaults. Browser UI must not collect provider credentials unless separately authorized."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Memory And Skills (Priority: P1)

A web user can review, create, update, import, and delete agent memory entries and skills from a capability management surface, with clear status when an item is invalid, unavailable, or blocked by ownership rules.

**Why this priority**: Memory and skills are the highest-value capability controls. They shape what the agent can remember and do, and they build directly on the existing read-only inspection surface.

**Independent Test**: Use only the capability management surface to list memory and skills, open one item, create or update one item, import a skill package, delete one item, and verify the change is reflected after refresh without exposing raw credential material.

**Acceptance Scenarios**:

1. **Given** an authenticated web user with existing memory entries, **When** the user opens memory management, **Then** the user sees owned entries with enough metadata to review and select them.
2. **Given** an authenticated web user creates or updates a memory entry, **When** the user saves valid content, **Then** the entry is retained and appears on the next refresh.
3. **Given** an authenticated web user imports a valid skill, **When** the import completes, **Then** the skill appears with its name, description, source, and availability status.
4. **Given** a memory entry or skill cannot be loaded or validated, **When** the user views it, **Then** the UI shows a public-safe problem state without leaking local paths, credentials, or raw internal errors.

---

### User Story 2 - Manage MCP And Workspace Context (Priority: P2)

A web user can manage configured MCP connections and bind sessions to a project or workspace context so future sessions can start with the correct capability and working-context selection.

**Why this priority**: MCP and project/workspace context are the next layer of capability parity. They determine what external tool surfaces and working scopes are available to a session.

**Independent Test**: Add or update an MCP configuration, reconnect it, remove it, create or select a project/workspace context, bind a session to that context, and verify non-owned or unavailable contexts are not usable.

**Acceptance Scenarios**:

1. **Given** an authenticated web user opens MCP settings, **When** the user adds or updates a valid connection configuration, **Then** the connection appears with a status and tool inventory summary.
2. **Given** an MCP connection is unhealthy, **When** the user requests reconnect, **Then** the system attempts reconnect and reports a public-safe success or failure state.
3. **Given** a project or workspace is available to the user, **When** the user selects it for a session, **Then** the session clearly shows the active context and uses it for future turns.
4. **Given** a project, workspace, or MCP connection is not owned or no longer available, **When** the user attempts to select or mutate it, **Then** the action is rejected without revealing whether another user owns it.

---

### User Story 3 - Manage Schedules And Model Defaults (Priority: P3)

A web user can view, create, update, delete, and run schedules on demand, and can choose default models only from the provider/model catalog already configured by the host.

**Why this priority**: Schedules and model defaults round out capability management but are less critical than direct memory, skill, MCP, and workspace controls.

**Independent Test**: Create a schedule, update its trigger and enabled state, run it immediately, delete it, choose a default model from the host-provided catalog, and verify the browser never asks for provider credentials.

**Acceptance Scenarios**:

1. **Given** an authenticated web user creates a valid schedule, **When** the schedule is saved, **Then** it appears in the schedule list with status, next-run information when available, and ownership metadata.
2. **Given** a schedule exists, **When** the user runs it now, **Then** the system starts the scheduled action or returns a public-safe reason it cannot run.
3. **Given** the host provides a model catalog, **When** the user selects a default model, **Then** future sessions can use that default without the browser collecting provider credentials.
4. **Given** the host does not provide a model catalog or the selected model is removed, **When** the user opens model defaults, **Then** the UI shows an unavailable or fallback state without blocking other capability settings.

---

### Edge Cases

- A memory entry, skill, MCP configuration, project, workspace, schedule, or model is deleted in another tab while the user is editing it.
- A skill import is malformed, duplicates an existing skill, or lacks required metadata.
- An MCP reconnect attempt times out or returns a non-public diagnostic.
- A project/workspace context becomes unavailable after a session is bound to it.
- A schedule is disabled, already running, has an invalid trigger, or targets a capability the user can no longer access.
- The host model catalog changes while the user is selecting a default model.
- A capability action fails because authentication expires mid-edit.
- A capability record contains text that looks like a credential and must not be echoed in logs, errors, or public-safe summaries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a web capability management surface that builds on the existing read-only inspection experience without removing the current inspection views.
- **FR-002**: Users MUST be able to list, open, create, update, and delete owned memory entries.
- **FR-003**: Users MUST be able to list, open, create or update, import, and delete skills with visible validity and availability status.
- **FR-004**: Users MUST be able to list, add or update, delete, and reconnect MCP configurations, and each connection MUST expose a public-safe status summary.
- **FR-005**: Users MUST be able to list, create or select, update, and remove project/workspace contexts available to them.
- **FR-006**: Users MUST be able to bind a session to a project/workspace context and see the active context before sending a turn.
- **FR-007**: Users MUST be able to list, open, create, update, delete, enable or disable, and run schedules immediately.
- **FR-008**: Users MUST be able to select default models only from a host-provided provider/model catalog.
- **FR-009**: The browser UI MUST NOT collect, display, persist, or transmit provider credentials unless a later explicitly authorized feature changes that boundary.
- **FR-010**: Capability management actions MUST preserve principal scoping: non-owned resources MUST NOT be visible, mutable, executable, reconnectable, importable, or deletable.
- **FR-011**: All capability mutation failures MUST return public-safe messages that avoid raw internal paths, raw stack traces, credential-like values, private hostnames, or private implementation names.
- **FR-012**: Existing chat, session management, live transport, REST/SSE compatibility, and desktop compatibility behavior from 074 MUST remain available while capability management is added.
- **FR-013**: Capability lists MUST provide enough metadata for users to identify items without exposing full raw content unless the user explicitly opens an owned item.
- **FR-014**: The feature MUST include automated acceptance coverage for memory, skills, MCP configuration, project/workspace context, schedules, model defaults, principal scoping, public-safe errors, and existing 074 compatibility.
- **FR-015**: The feature MUST include rollback guidance that allows disabling or reverting capability mutation surfaces while keeping read-only inspection and 074 chat/session behavior available.
- **FR-016**: The feature MUST NOT copy implementation code, private paths, private names, credentials, tokens, or raw legacy/reference material from any reference repository.

### Key Entities

- **Memory Entry**: A user-owned or host-available knowledge item with metadata, content summary, editable content when opened, and availability state.
- **Skill**: A reusable agent capability with name, description, source, validation status, import/update metadata, and deletion state.
- **MCP Configuration**: A connection configuration with display name, connection status, exposed tool summary, reconnect state, and public-safe problem details.
- **Project/Workspace Context**: A selectable working context that can be associated with sessions and capability defaults.
- **Schedule**: A user-visible automation definition with trigger information, enabled state, ownership, run status, and run-now behavior.
- **Model Default**: A user preference chosen from the host-provided model catalog, without browser-side provider credential entry.
- **Capability Management Surface**: The web settings area where users review and mutate the above capability records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the primary memory create/update/delete flow in under 2 minutes in automated acceptance scenarios.
- **SC-002**: A user can import or update a valid skill and see its refreshed availability state in 100% of skill-management tests.
- **SC-003**: MCP add/update/reconnect/delete tests cover both success and public-safe failure states with no raw internal details exposed.
- **SC-004**: Project/workspace binding tests verify that a session shows the selected context before a turn is sent.
- **SC-005**: Schedule management tests cover create, update, enable/disable, run-now, and delete flows.
- **SC-006**: Model-default tests verify that only host-provided catalog entries can be selected and that no provider credential fields are rendered.
- **SC-007**: Existing 074 web live/session tests and desktop compatibility tests continue to pass after capability management is added.
- **SC-008**: Public-safety scans over changed files report no private paths, raw reference material, credentials, tokens, or credential-like values.

## Assumptions

- Existing authentication, principal ownership, inspection, session, model catalog, and 074 transport/session-management behavior remain the compatibility baseline.
- Capability mutation surfaces are additive and can coexist with existing read-only inspection views.
- Provider credential entry and browser-side provider setup remain out of scope unless separately authorized.
- Capability records are scoped to the authenticated user or to host-provided shared resources with clear read-only or mutable boundaries.
- Desktop cowork parity is out of scope for 075 except for preserving compatibility; it remains planned for 077.
- Plan mode, permission mode/rules, server-side budget controls, workspace file/artifact panels, and follow-up suggestions are out of scope for 075 and remain planned for 076.
- Claude Code and Orion are behavior references only; implementation is re-derived through LoopPlane specs and tests.
