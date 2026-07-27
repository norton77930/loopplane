# Feature Specification: Web Capability Management Hardening

**Feature Branch**: `076-web-capability-management-hardening`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Harden web capability management into a product-usable settings surface: durable owner-scoped capability state, shared read-only host capabilities, principal-safe memory/skills/MCP/runtime activation, real MCP reconnect, independent Capability Settings view, catalog-only model defaults, mutation gate, public-safe errors, rollback guidance, and full acceptance coverage."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Memory And Skills End-To-End (Priority: P1)

A signed-in user can open the capability settings surface, review memory entries and skills available to them, create or update their own memory entries and skills, import a valid skill, open details for owned items, delete owned items, and then see those owned capabilities take effect for their later chat sessions. Shared host-provided memory or skills remain visible only as read-only metadata where appropriate.

**Why this priority**: Memory and skills are the highest-value capability settings because they directly affect the agent's context and available actions. They also expose the most important owner-scoping and runtime-activation risks.

**Independent Test**: Create one memory entry and one skill as an owner, verify they appear in the settings surface with editable actions, verify another user cannot see or mutate them, verify shared host entries remain read-only, and verify the owner's later session can use the owned capability while a non-owner session cannot.

**Acceptance Scenarios**:

1. **Given** a signed-in user with capability mutations enabled, **When** the user creates, opens, updates, and deletes an owned memory entry, **Then** each action succeeds only for that owner and the settings surface shows refreshed status after each action.
2. **Given** a signed-in user with capability mutations enabled, **When** the user creates or imports a valid skill, **Then** the skill appears with availability status, can be opened and deleted by the owner, and becomes available only to that owner's later sessions.
3. **Given** a second signed-in user, **When** they list, open, mutate, delete, import over, or attempt to use the first user's memory or skill, **Then** the resource is not disclosed and the action fails without revealing whether the resource exists.
4. **Given** shared host-provided memory or skills, **When** a user views capability settings, **Then** shared items are identifiable as read-only and cannot be modified or deleted through the management surface.

---

### User Story 2 - Manage MCP And Workspace Contexts (Priority: P2)

A signed-in user can add or update their own MCP configurations, reconnect a configuration, see public-safe connection status, delete owned MCP configurations, create or select workspace contexts, bind a session to an owned or allowed context, and see the active context before sending a turn.

**Why this priority**: MCP connections and workspace contexts affect the tools and working context available to the agent. The feature is not product-usable unless changes are durable, owner-scoped, and reflected in later runtime behavior.

**Independent Test**: Add an MCP configuration, reconnect it, verify refreshed public-safe status and owner-visible tool availability, delete it, create a workspace context, bind it to a session, and verify a different principal cannot see, bind, reconnect, or delete those resources.

**Acceptance Scenarios**:

1. **Given** a signed-in user with capability mutations enabled, **When** the user adds or updates an MCP configuration and reconnects it, **Then** the configuration is saved, a public-safe status is shown, and available MCP tools are scoped to that owner.
2. **Given** a saved MCP configuration that cannot connect, **When** the user reconnects it, **Then** the settings surface shows a public-safe failure state without raw paths, private host details, stack traces, or credential-like values.
3. **Given** an owned workspace context, **When** the owner binds it to a session, **Then** the session summary and chat header show the active context before the next turn is sent.
4. **Given** another signed-in user, **When** they list, bind, reconnect, mutate, or delete resources owned by the first user, **Then** those resources are not disclosed and the operation fails safely.

---

### User Story 3 - Manage Schedules And Model Defaults (Priority: P3)

A signed-in user can create, open, update, enable, disable, run now, and delete owned schedules. The user can select a default model only from the host-provided catalog, and the browser surface never asks for provider credentials or MCP authentication tokens.

**Why this priority**: Schedules and defaults round out capability settings, but they are less foundational than memory, skills, MCP, and workspace context. They still require strong owner scoping and rollback behavior before the feature is complete.

**Independent Test**: Create and update a schedule, disable and re-enable it, run it immediately, delete it, select a model default from the catalog, verify invalid defaults cannot be selected, and verify credential fields are absent from the browser surface.

**Acceptance Scenarios**:

1. **Given** a signed-in user with capability mutations enabled, **When** the user creates, opens, updates, disables, enables, runs now, and deletes a schedule, **Then** each action is reflected in the settings surface and remains scoped to that owner.
2. **Given** a disabled schedule, **When** the user runs it immediately, **Then** the operation is refused with a public-safe message and the disabled state remains visible.
3. **Given** a host-provided model catalog, **When** the user sets a default model, **Then** only catalog entries can be selected and the selected default is applied to that owner.
4. **Given** the capability settings surface, **When** the user reviews MCP and model settings, **Then** no provider credential, API key, secret, token, or MCP authentication token field is rendered or persisted in the browser.

---

### Edge Cases

- Capability mutation is disabled by host policy: users can still inspect read-only capability metadata, but mutation actions are hidden or fail with a public-safe disabled message.
- Durable capability storage is unavailable: mutation actions fail safely without falling back to non-durable state that appears successful.
- A resource is deleted while the settings surface is open: refresh or next action shows a public-safe unavailable state and does not reveal owner-private details.
- A saved resource name collides with a shared read-only host resource: the owned resource must not overwrite the shared resource, and actions must make the scope clear.
- A user changes a capability while a session is already running: the current turn remains stable, and the changed capability applies only to later eligible turns or sessions.
- A reconnect operation returns partial MCP availability: healthy tools remain visible to the owner and failures are shown as public-safe status details.
- A browser request attempts to configure an MCP stdio command: the managed request is refused without executing or persisting the command, while host-configured shared stdio MCP remains available read-only.
- A managed network MCP URL is not approved by host policy: save and reconnect fail without contacting the endpoint or disclosing policy internals.
- A user attempts direct access to another user's capability by known identifier: the response must not reveal whether the resource exists.
- A schedule has no executable instruction or the host has no schedule runner: run-now fails safely and leaves the saved schedule intact.
- Existing chat, session, inspection, and desktop compatibility flows are used while capability settings are open: those flows continue to work.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an independent capability settings surface for mutable capability management while preserving the existing read-only inspection surface.
- **FR-002**: The system MUST keep host-provided shared capabilities visible only as read-only metadata unless they are explicitly user-owned.
- **FR-003**: Users MUST be able to list, open, create, update, delete, and see refreshed status for owned memory entries.
- **FR-004**: Users MUST be able to list, open, create or update, import, delete, and see refreshed validity and availability status for owned skills.
- **FR-005**: Owned memory entries and owned skills MUST become available to the owner's later eligible sessions and MUST NOT become visible or usable by other principals.
- **FR-006**: Users MUST be able to list, open, add or update, reconnect, delete, and see public-safe status for owned MCP configurations.
- **FR-007**: Owned MCP configurations MUST become available only to the owner's later eligible sessions after a successful reconnect or activation.
- **FR-008**: Users MUST be able to list, open, create or select, update, remove, and bind owned workspace contexts to owned sessions.
- **FR-009**: A session bound to a workspace context MUST show the active context before the user sends a turn.
- **FR-010**: Users MUST be able to list, open, create, update, delete, enable, disable, run now, and see refreshed status for owned schedules.
- **FR-011**: Users MUST be able to select model defaults only from a host-provided model catalog.
- **FR-012**: Browser surfaces MUST NOT collect, display, persist, or transmit provider credentials, API keys, secrets, tokens, or MCP authentication tokens.
- **FR-013**: Capability state created through the settings surface MUST be durable across host restarts when durable host storage is configured.
- **FR-014**: If durable capability storage is not configured or is unavailable, mutation attempts MUST fail safely and MUST NOT report success for non-durable state.
- **FR-015**: Capability management actions MUST preserve principal scoping: non-owned resources MUST NOT be visible, mutable, executable, reconnectable, importable over, bindable, or deletable.
- **FR-016**: Direct requests for non-owned capability identifiers MUST fail without revealing whether the resource exists.
- **FR-017**: Capability mutation failures MUST return public-safe messages that avoid raw internal paths, raw stack traces, credential-like values, private hostnames, and private implementation names.
- **FR-018**: The system MUST provide a host-controlled capability mutation gate that can disable mutation surfaces while preserving read-only inspection and existing chat/session behavior.
- **FR-019**: Existing chat, session management, live transport, REST/SSE compatibility, read-only inspection, and desktop compatibility behavior from 074 and 075 MUST remain available.
- **FR-020**: The feature MUST include automated acceptance coverage for durable storage, owner/shared scoping, runtime activation, MCP reconnect, workspace context binding, schedules, model defaults, mutation gating, public-safe errors, and existing compatibility.
- **FR-021**: The feature MUST include rollback guidance that allows disabling or reverting capability mutation surfaces while keeping read-only inspection and chat/session behavior available.
- **FR-022**: The feature MUST NOT copy implementation code, private paths, private names, credentials, tokens, or raw legacy/reference material from any reference repository.
- **FR-023**: Browser-managed MCP reconnect MUST support only host-policy-approved HTTP, SSE, or WebSocket endpoints; browser-managed stdio commands MUST NOT be executed or persisted, while existing host-configured shared stdio MCP remains read-only.
- **FR-024**: Capability management and owner-scoped runtime activation MUST be default-off host options; disabling either option MUST preserve read-only settings, inspection, and existing chat/session behavior.
- **FR-025**: Schedule run-now MUST dispatch the saved instruction through a host-injected runner, MUST refuse disabled or instruction-less schedules, and MUST fail safely when no runner is configured.

### Key Entities

- **Owned Capability Resource**: A capability item created or imported by a principal, such as memory, skill, MCP configuration, workspace context, schedule, or model default.
- **Shared Host Capability**: A host-configured capability visible as public-safe read-only metadata and not mutable through the user's settings surface.
- **Capability Settings State**: Durable per-principal state for user-owned capability resources and defaults.
- **Capability Operation Result**: Public-safe outcome for create, update, delete, reconnect, bind, run-now, enable, disable, or default-selection actions.
- **MCP Connection Status**: Public-safe availability state and summary for a managed MCP configuration after save or reconnect.
- **Workspace Context Binding**: Association between an owned session and an owned or allowed workspace context.
- **Mutation Gate**: Host-controlled setting that determines whether mutable capability actions are available.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A signed-in user can complete the memory create, open, update, delete, and later-session activation flow in under 2 minutes in automated acceptance scenarios.
- **SC-002**: A signed-in user can create or import a valid skill and see its refreshed availability state in 100% of skill-management acceptance tests.
- **SC-003**: Cross-principal capability access attempts for memory, skills, MCP configurations, workspace contexts, schedules, and model defaults disclose zero owner-private resource details in automated tests.
- **SC-004**: Saved owned MCP configurations, workspace contexts, schedules, and model defaults remain available after a host restart in durable-storage acceptance tests.
- **SC-005**: MCP reconnect tests cover both successful refresh and public-safe failure states with no raw internal details exposed.
- **SC-006**: Workspace context binding tests verify that an owned session shows the selected context before a turn is sent.
- **SC-007**: Schedule tests cover create, open, update, enable, disable, run-now, disabled run-now refusal, and delete flows.
- **SC-008**: Model-default tests verify that only host catalog entries can be selected and that no credential-like fields are rendered.
- **SC-009**: Mutation-gate tests verify that mutations can be disabled while read-only inspection and chat/session behavior remain available.
- **SC-010**: Existing 074 and 075 compatibility tests continue to pass after capability hardening is added.
- **SC-011**: Public-safety scans over changed files report no private paths, raw reference material, credentials, tokens, or credential-like values.
- **SC-012**: Managed MCP acceptance tests prove that stdio and policy-denied network endpoints make zero connection attempts while approved network endpoints can reconnect.
- **SC-013**: Schedule acceptance tests prove that run-now invokes the injected runner exactly once for an enabled schedule and never invokes it for disabled, instruction-less, non-owned, or unavailable schedules.

## Assumptions

- This feature is inserted as a new 076 roadmap unit; the previously planned web-agent-controls unit is postponed and renumbered.
- Existing authenticated principals and session ownership behavior remain the identity source for capability ownership.
- Host-provided capabilities may be listed as shared read-only metadata when that metadata is already public-safe.
- Capability changes apply to later eligible turns or sessions; an already-running turn does not change mid-flight.
- API and UI changes are additive; existing 074 and 075 behavior remains a compatibility baseline.
- Browser credential collection for provider or MCP authentication remains out of scope.
- Hosts explicitly enable capability mutations and runtime activation; both remain disabled when their configuration is absent.
- Network MCP management uses a host-supplied, default-deny endpoint policy. Browser-managed stdio remains out of scope for this unit.
- Periodic schedule orchestration remains owned by the existing Phase-3 scheduler; this unit's run-now action dispatches one saved instruction through a host-injected runner.
