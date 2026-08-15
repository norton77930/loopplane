# Feature Specification: Desktop Capability Parity

**Feature Branch**: `083-desktop-capability-parity`
**Status**: Draft
**Depends on**: 078 (Verified), 075, 076, 077, 064, 065
**Input**: Give the Desktop operator the same control over their own agent that the Web operator already has, without importing Web's constraints.

## Why this exists

Web is served across a network to a principal who need not own the machine. Somebody set that deployment up: chose the model, configured MCP servers, decided the budget. Desktop has no such person. The user supplies the key, chooses the folder, and pays for every token — **they are the operator** — and today they have the fewest controls of any surface.

Web presents seven capability-management panels (memory, skills, MCP, workspace contexts, schedules, model defaults, agent controls). Desktop presents three tabs, one of which is a read-only status list. A person can run Desktop all day against their own API key and find nothing on screen telling them what it cost. That is not a feature-count gap; it is the governance surface being thinnest exactly where nobody else is providing it.

This unit closes that, and closes only that. Differences that exist because the two surfaces are genuinely different stay.

## Clarifications

### Session 2026-08-15

- Q: Should Desktop match Web feature-for-feature? → A: No. Parity is scoped to capability management and cost visibility. Attachments, login, and multi-principal scoping are Web-shaped and are explicit non-goals.
- Q: Does this need runtime work? → A: No. Every capability is already a public method on `LoopPlaneHost` (`list/write/get/delete_managed_memory`, `list/write/import/get/delete_managed_skill`, `list/get/upsert/delete_managed_mcp`, `list/upsert/get/delete_workspace_context`, `list/upsert/get/delete_managed_schedule`, `model_default`/`set_model_default`, `session_cost`, `monthly_spend`). The sidecar already holds a Host and is permitted to import `loopplane.host`.
- Q: Can Web's settings panels be reused directly? → A: Not as they stand. All six take `ApiClient` as a type dependency. `AgentControlsSettings` is the template for the fix: it accepts a narrow `service` interface and already lives in the shared package.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what this is costing (Priority: P1)

A person running Desktop against their own API key wants to know, without hunting, what the current session has spent and what the month has spent so far.

**Why this priority**: They are paying. Every other item in this unit is a convenience by comparison; this one is about not being surprised by a bill.

**Acceptance**:
1. Given a host with pricing configured, when a run completes, then the session's spend is visible in the conversation pane without opening a panel.
2. Given a principal with a monthly ledger, when the user opens cost detail, then the month's spend to date is shown.
3. Given a host with no pricing configured, then the surface says so explicitly and never renders an unpriced or unknown value as `$0`.
4. Given a partially priced session, then partial and complete pricing are visually distinct.

### User Story 2 - Choose a model without restarting (Priority: P1)

A person wants a cheaper model for a routine question and a stronger one for a hard change, in the same sitting.

**Why this priority**: Changing model is a daily action. Today it requires editing settings and relaunching the application, which makes the choice expensive enough that people stop making it.

**Acceptance**:
1. Given a configured provider, when the user opens the model selector, then the models that provider offers are listed with the current one marked.
2. When the user selects a different model, then the next run uses it and no relaunch occurs.
3. Given a run in flight, then the selector is unavailable rather than silently deferred.
4. Given a model id the provider rejects, then the failure is a fixed public message and the previous selection remains in effect.

### User Story 3 - Decide what the agent can reach (Priority: P2)

A person wants to see and change which MCP servers, skills, and memory entries the agent has, from the application rather than by editing files.

**Why this priority**: These decide what the agent can do at all. On Web an operator configured them; on Desktop nobody has.

**Acceptance**:
1. The user can list, inspect, add, and remove MCP server configurations, and a server that fails to connect is reported as unavailable rather than silently absent.
2. The user can list, inspect, add, import, and remove managed skills.
3. The user can list, search, inspect, and remove managed memory entries.
4. No MCP endpoint URL, credential, header, or token supplied for a server is ever returned to the renderer.
5. A mutation attempted while another durable mutation holds the profile lease is refused with a public busy reason, not queued.

### User Story 4 - Manage the rest of the governance surface (Priority: P3)

A person wants schedules, workspace contexts, and the default model to be manageable from the application, matching what Web already offers.

**Acceptance**:
1. The user can list, create, inspect, and cancel managed schedules.
2. The user can list, bind, inspect, and remove workspace contexts, and the current binding is shown.
3. The user can set and clear the model default, chosen from the available catalog rather than typed freely.

### User Story 5 - Ask the host without spending a turn (Priority: P3)

A person wants `/cost`, `/model`, `/memory`, and `/compact` to work in the composer, as they already do on the CLI and Web.

**Acceptance**:
1. A leading `/` opens the command list; a known command answers without a model round-trip.
2. An unknown command returns a normalized message and never reaches the Gateway or the Event Bus.
3. Composer input that is not a command behaves exactly as before.

### Edge Cases

- A capability the host cannot provide (no ledger, no scheduler, no MCP configured) is reported as unavailable with its own reason, never as an empty success state.
- A sidecar that answers `initialize` but whose host lacks a capability must not fail the handshake; capability status is answered per domain by `capabilities.list`.
- A mutation that fails midway leaves the previous configuration in effect; no partial write is published.
- A model selection made while offline is stored and applied on the next successful run rather than lost.
- Restoring a portable backup does not carry provider credentials, so the model selector reports no provider until one is entered again.

## Requirements *(mandatory)*

### Functional Requirements

#### Cost and model

- **FR-001**: The conversation pane MUST show the current session's spend when the host can price it, and MUST distinguish "unpriced", "partially priced", and "unavailable" from zero.
- **FR-002**: A cost detail surface MUST show the principal's month-to-date spend from the durable ledger when one is configured.
- **FR-003**: The user MUST be able to select the model for the next run from the configured provider's catalog without relaunching the application.
- **FR-004**: Model selection MUST be refused, with a public reason, while a run is in flight.
- **FR-005**: A rejected model MUST leave the prior selection in effect and surface a fixed public message.

#### Capability management

- **FR-006**: The user MUST be able to list, inspect, add, and remove MCP server configurations.
- **FR-007**: The user MUST be able to list, inspect, add, import, and remove managed skills.
- **FR-008**: The user MUST be able to list, search, inspect, and remove managed memory entries.
- **FR-009**: The user MUST be able to list, create, inspect, and cancel managed schedules.
- **FR-010**: The user MUST be able to list, bind, inspect, and remove workspace contexts, and see the current binding.
- **FR-011**: The user MUST be able to set and clear the model default from the available catalog.
- **FR-012**: Every capability domain MUST report its own availability through the existing `capabilities.list` projection rather than through protocol capability negotiation.

#### Host commands

- **FR-013**: `/cost`, `/model`, `/memory`, and `/compact` MUST be answered in the composer through the existing `CommandRegistry`, with no model round-trip, no Gateway invocation, and no Event Bus emission.
- **FR-014**: An unknown command MUST return the registry's normalized message; non-command input MUST behave exactly as before.

#### Protocol, boundary, and safety

- **FR-015**: New sidecar methods MUST be added to `_DESKTOP_METHOD_NAMES` and to the exact-equality method list in `tests/integration/test_desktop_sidecar.py` in the same change; the protocol major version and the `REQUESTED_CAPABILITIES` enumeration MUST NOT change.
- **FR-016**: The sidecar MUST reach every capability through public `loopplane.host` methods only; it MUST NOT import a store, controller, gateway, or tool module, and MUST NOT execute a tool.
- **FR-017**: Every durable mutation MUST acquire the profile mutation lease and MUST use a main-generated mutation id; a renderer-supplied id MUST be ignored.
- **FR-018**: No MCP endpoint, credential, header, token, absolute path, raw exception, or PID may reach the renderer. Failures MUST map to the fixed public error catalogue.
- **FR-019**: Every new IPC channel MUST validate its sender through the existing trusted-sender guard and MUST have a test proving an untrusted sender is rejected.

#### Presentation

- **FR-020**: The six Web settings panels MUST move to the shared presentation package behind narrow service interfaces, following `AgentControlsSettings`; Web MUST pass an adapter over its existing `ApiClient` and its outward behavior MUST be unchanged.
- **FR-021**: Every string added to the Desktop chrome MUST have an English and a zh-TW entry; the existing coverage test MUST continue to fail when one is missing.
- **FR-022**: The seven fixed packaged-smoke accessible names MUST remain, each resolving to exactly one element, and MUST NOT be translated.

### Non-Goals

- **NG-001**: File attachments. Web needs upload because a browser cannot reach the filesystem; Desktop binds a directory. Adding upload would import Web's constraint.
- **NG-002**: Login, bearer tokens, and multi-principal scoping. Desktop is one local profile behind an OS ownership lock.
- **NG-003**: A native application menu, global keyboard shortcuts, and window-title state. These require `apps/desktop/electron/main.ts` and belong to their own unit.
- **NG-004**: Renaming the seven packaged-smoke accessible names, which requires editing the smoke driver and the renderer contract together.
- **NG-005**: Any change to Web's outward contracts, the Event Bus, checkpoint records, Gateway invocation, termination reasons, the event schema version, or any runtime default.
- **NG-006**: New runtime capability. Every method this unit projects already exists on `LoopPlaneHost`.

### Key Entities

- **Capability projection**: a public-safe, metadata-only view of one managed domain, carrying availability and reason.
- **Managed record**: an MCP server, skill, memory entry, schedule, or workspace context, addressed by an opaque id.
- **Model catalog entry**: an id and label the configured provider offers, with the current selection marked.
- **Cost view**: exact `Decimal` spend or an explicit absence, never coerced to zero.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can read the session's spend without opening a panel, and an unpriced host says so rather than showing `$0`.
- **SC-002**: A person can change the model and see the next run use it, with no relaunch.
- **SC-003**: A person can add and remove an MCP server, a skill, and a memory entry entirely from the application.
- **SC-004**: A public-safety scan over every new projection, error, and log finds no endpoint, credential, path, raw exception, or PID.
- **SC-005**: The packaged smoke passes unchanged, with all seven locators resolving exactly once.
- **SC-006**: Web's contract suites pass unchanged after the presentation extraction, proving its outward behavior did not move.
- **SC-007**: Every added English string has a zh-TW entry.
- **SC-008**: Reverting this unit's commits restores the current Desktop behavior exactly, with no runtime or Web residue.

## Assumptions

- 078 is Verified and its delivery chain is intact; this unit builds on the sidecar protocol it established.
- The user is a single local operator with one Desktop profile, as 078 assumed.
- Pricing, ledger, scheduler, and MCP availability are host configuration; this unit surfaces them and never forces them on.
- Provider credentials remain owned by Electron main under ADR 0016; nothing here moves them.
