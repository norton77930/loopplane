# Feature Specification: Web Capability Delivery Remediation

**Feature Branch**: 081-web-capability-delivery-remediation
**Created**: 2026-07-27
**Status**: Draft
**Input**: Remediate and converge the completed 076 capability-management hardening and 080 frontend presentation work before beginning 077, without rewriting their frozen specification history.

## Clarifications

### Session 2026-07-27

- Q: May managed-MCP update/delete host methods become asynchronous so they can await immediate Gateway retirement and lease-safe shutdown while leaving HTTP routes and JSON responses unchanged? → A: Yes; the maintainer approved converting the public Python host methods to async, with documentation, caller, and contract-test updates in 081.

## User Scenarios & Testing

### User Story 1 - Manage Network MCP Safely (Priority: P1)

An authenticated user can save, reconnect, update, and delete an approved network MCP configuration without browser-originated credentials being persisted and without a removed or failed configuration remaining usable in later turns.

**Why this priority**: MCP configurations can expose external tools. Unsafe endpoint material or stale tool availability would violate the product's credential and authorization boundaries.

**Independent Test**: Configure an approved endpoint, activate its tools, then update, delete, and force a reconnect failure while observing endpoint validation, later tool availability, and an already-running invocation.

**Acceptance Scenarios**:

1. **Given** a valid approved HTTP, SSE, or WebSocket endpoint with no embedded identity or extra URL data, **When** the user saves and reconnects it, **Then** the configuration becomes available only to that principal and exposes public-safe status and tool metadata.
2. **Given** an endpoint containing user information, query data, a fragment, an empty host, an incompatible scheme, or a browser-managed stdio request, **When** the user submits it, **Then** the request is rejected before persistence or connection and the response does not repeat the unsafe value.
3. **Given** an active owner-scoped MCP adapter, **When** its owner updates or deletes the configuration, **Then** new turns can no longer resolve the old tools immediately.
4. **Given** an active owner-scoped MCP adapter, **When** reconnect fails, **Then** new turns can no longer resolve the old tools and the owner sees only a public-safe failed status.
5. **Given** an invocation that already began before update, deletion, or reconnect failure, **When** the adapter is retired, **Then** that invocation may finish and the retired adapter is closed exactly once afterward.
6. **Given** two principals with managed MCP configurations, **When** one principal changes or removes a configuration, **Then** the other principal's scoped tools are unchanged.

---

### User Story 2 - Bind an Allowed Workspace Context (Priority: P2)

An authenticated user can see and bind a host-approved read-only workspace context to a session they own, while contexts not explicitly allowed to that principal remain undisclosed.

**Why this priority**: The existing capability contract promises owned or allowed context binding, but the delivered surface currently exposes only owned contexts.

**Independent Test**: Supply different allowed-context sets for two principals, list and open contexts, bind one to an owned session, and attempt the same operations as an unapproved principal.

**Acceptance Scenarios**:

1. **Given** an owned context and a host-approved read-only context, **When** the user lists workspace contexts, **Then** both are visible with actions appropriate to their scope.
2. **Given** a host-approved read-only context and an owned session, **When** the user binds it, **Then** the session shows the context before the next turn without modifying the shared context.
3. **Given** a context not allowed to the requesting principal, **When** that principal lists, opens, or attempts to bind it, **Then** its existence is not disclosed.
4. **Given** an owned and allowed context with a conflicting identity, **When** the user lists or binds contexts, **Then** the system refuses the ambiguous operation deterministically rather than selecting an unsafe source.
5. **Given** no host-approved context source, **When** users access workspace settings, **Then** the existing owner-only behavior is unchanged.

---

### User Story 3 - Inspect Shared Capabilities Without Mutation (Priority: P2)

An authenticated user can open safe read-only details for shared memory, skills, MCP configurations, and workspace contexts without receiving edit or delete controls or sensitive resource content.

**Why this priority**: Shared capabilities are already presented in settings, but a read-only label alone does not let users understand what is available and can encourage unsafe reuse of editable forms.

**Independent Test**: Open every supported shared capability type and verify the visible metadata, available actions, absence of mutation controls, and absence of sensitive fields.

**Acceptance Scenarios**:

1. **Given** shared memory, **When** the user opens it, **Then** only bounded descriptive metadata and a safe snippet are shown, with no editable full body.
2. **Given** a shared skill, **When** the user opens it, **Then** descriptive metadata and availability are shown without editable instructions.
3. **Given** a shared MCP configuration, **When** the user opens it, **Then** transport, connection status, and safe tool metadata are shown without endpoint URLs, authentication material, or raw connection errors.
4. **Given** a shared workspace context, **When** the user opens it, **Then** safe metadata and an allowed bind action may be shown without update or delete actions.
5. **Given** a resource whose projected actions do not include open, **When** settings renders it, **Then** no detail action is offered even if its scope resembles another shared resource.

---

### User Story 4 - Trust the Delivered Capability Release (Priority: P3)

A maintainer can verify that the capability and presentation work is separated from local artifacts, fully tested from a clean dependency state, accurately documented, and ready before the next roadmap unit begins.

**Why this priority**: The current working tree mixes two completed units and local workflow artifacts, while status and release documents do not consistently describe the same state.

**Independent Test**: Review the changed-file inventory, run all required automated and browser checks, and compare the active feature pointer, roadmap, release notes, and public API documentation.

**Acceptance Scenarios**:

1. **Given** the mixed working tree, **When** delivery changes are classified, **Then** 076, 080, 081, and local or unknown files have explicit non-overlapping ownership and local artifacts are excluded from delivery.
2. **Given** the remediation implementation, **When** the required backend, web, desktop, browser, architecture, and public-safety checks run, **Then** fresh literal results are recorded and historical counts are not reused as evidence.
3. **Given** successful verification, **When** progress documents are synchronized, **Then** the active feature pointer, roadmap status, release notes, and any changed public surface describe one consistent state.
4. **Given** any failed or skipped required check, **When** completion is reported, **Then** the unit remains unverified and the failure or skip reason is recorded.
5. **Given** unit 081 is not yet verified, **When** roadmap work is selected, **Then** unit 077 does not begin implementation.

### Edge Cases

- A syntactically valid URL uses an allowed scheme but has no host.
- An unsafe endpoint is submitted through a non-browser caller that bypasses request validation.
- Stored legacy state contains an endpoint that no longer satisfies the safe endpoint rules.
- Adapter connection succeeds but status persistence or registry replacement fails.
- Adapter retirement happens concurrently with one or more in-flight invocations.
- A delete request names a missing or shared MCP configuration.
- The allowed-context source fails, returns duplicate identities, or changes authorization between list and bind.
- A session belongs to another principal even though the context is allowed to the caller.
- A shared resource contains sensitive internal fields that must not appear in its projection.
- Mutation or runtime activation is disabled while read-only settings remain available.
- Narrow-screen, keyboard, reduced-motion, forced-color, or non-English presentation is used for a shared detail view.
- A full verification failure is caused by a known intermittent test; the isolated rerun result must be recorded without hiding the original failure.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST accept browser-managed MCP configurations only for approved HTTP, SSE, or WebSocket network endpoints.
- **FR-002**: The system MUST reject browser-managed stdio configurations without persisting or executing their command or arguments.
- **FR-003**: The system MUST reject MCP endpoints with missing hosts, incompatible schemes, embedded user information, query data, or fragments before persistence or connection.
- **FR-004**: MCP endpoint validation MUST also protect direct domain and persistence entry points that do not pass through browser request validation.
- **FR-005**: MCP validation and connection failures MUST expose fixed public-safe outcomes without repeating submitted endpoint data, credentials, private paths, or raw adapter errors.
- **FR-006**: The existing host-owned endpoint approval policy MUST remain mandatory and default-deny for browser-managed network MCP.
- **FR-007**: Updating or deleting an owned active MCP configuration MUST immediately remove its previous tools from new owner-scoped resolution.
- **FR-008**: A failed reconnect MUST immediately remove the previous tools from new owner-scoped resolution and persist only a public-safe failed status.
- **FR-009**: Retiring an adapter MUST allow already-started invocations to finish and MUST close that adapter exactly once after its final active use.
- **FR-010**: MCP lifecycle changes for one principal MUST NOT add, remove, replace, or disclose another principal's scoped tools.
- **FR-011**: Successful reconnect MUST continue to replace managed adapters only through the existing authorized tool-management boundary.
- **FR-012**: The host MAY provide a principal-aware source of allowed read-only workspace contexts; when absent, owner-only behavior MUST remain unchanged.
- **FR-013**: Workspace context lists and details MUST include only contexts owned by or explicitly allowed to the requesting principal.
- **FR-014**: An allowed read-only workspace context MAY be opened and bound to a session owned by the requesting principal, but MUST NOT be updated or deleted through capability settings.
- **FR-015**: Context access and binding failures MUST avoid disclosing whether a non-visible context or non-owned session exists.
- **FR-016**: Conflicting owned and allowed context identities MUST be handled deterministically and fail safely.
- **FR-017**: Shared memory, skill, MCP, and workspace context rows MUST derive available interactions from projected actions rather than scope labels alone.
- **FR-018**: Shared capability details MUST expose only the per-type public-safe field allow-lists defined by this unit; shared memory snippets MUST contain at most the first 160 Unicode code points, and no nested provider metadata may bypass those allow-lists.
- **FR-019**: Shared capability details MUST NOT expose editable full memory content, skill instructions, MCP endpoint URLs, authentication material, private paths, or raw host and adapter failures.
- **FR-020**: Shared capability details MUST NOT offer create, update, delete, reconnect, enable, disable, set, or clear actions unless the resource is owned and the existing capability contract explicitly allows the action.
- **FR-021**: The application MUST have one supported capability settings experience and MUST NOT retain a separately reachable legacy mutable settings surface.
- **FR-022**: Existing mutation and runtime activation gates MUST remain independently host-controlled and default off.
- **FR-023**: Existing chat, session, transport, inspection, attachment, schedule, model-default, and owner capability behavior MUST remain compatible.
- **FR-024**: The remediation MUST NOT alter the runtime event contract, checkpoint record contract, tool-management SPI or stage order, external dependencies, or existing default values.
- **FR-025**: The completed 076 and 080 specification and task histories MUST remain frozen; remediation requirements, validation, and rollback guidance MUST be recorded under 081.
- **FR-026**: Local workflow artifacts and files without confirmed delivery ownership MUST be excluded from staged delivery changes.
- **FR-027**: Completion evidence MUST come from fresh backend, web, desktop, browser, architecture-boundary, formatting, type, build, and public-safety checks.
- **FR-028**: Required verification failures or skips MUST be reported literally and MUST prevent a Verified status until resolved or explicitly accepted by the maintainer.
- **FR-029**: Once verification succeeds, the active feature pointer, roadmap, release notes, and changed public-surface documentation MUST be synchronized in the same delivery unit.
- **FR-030**: Unit 077 implementation MUST remain blocked until unit 081 is Verified.

### Key Entities

- **Managed MCP Configuration**: An owner-scoped network tool source with a name, transport, safe endpoint, connection status, public-safe problem summary, projected tools, and allowed actions.
- **Scoped Adapter Lifecycle**: The current, retired, leased, and closed states governing whether owner-scoped tools can be newly resolved and when their adapter may be closed.
- **Allowed Workspace Context**: A host-approved, principal-visible, read-only workspace projection that may be opened or bound to an owned session without becoming user-owned mutable state.
- **Shared Capability Projection**: Bounded metadata and explicit actions for a host-provided memory, skill, MCP configuration, or workspace context.
- **Delivery Ownership Bucket**: The classification of a changed file or hunk as 076, 080, 081, or local/unknown for safe staging and review.
- **Verification Evidence**: Fresh literal automated and manual results, including failures, skips, public-safety outcomes, and rollback guidance.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All tested endpoint variants containing embedded identity, query data, fragments, missing hosts, incompatible schemes, or browser-managed stdio are rejected before persistence or connection, with zero submitted unsafe values present in user-visible failures.
- **SC-002**: In every tested update, deletion, and failed-reconnect scenario, new turns lose access to the retired owner-scoped tools immediately while every already-started invocation completes and the retired adapter closes exactly once.
- **SC-003**: Across a two-principal authorization matrix, there are zero cases where one principal can list, open, bind, resolve, mutate, or infer another principal's private capability or session.
- **SC-004**: Every allowed shared context can be opened and bound by an approved principal within the normal settings workflow, while every unapproved principal receives a non-disclosing outcome.
- **SC-005**: All supported shared capability types provide a useful read-only detail view with zero editable controls and zero sensitive endpoint, credential, instruction, full-body, private-path, nested-provider-field, or raw-error disclosures; every shared memory snippet is at most 160 Unicode code points.
- **SC-006**: The supported settings experience remains usable without horizontal overflow at the required desktop, tablet, mobile, and high-reflow widths, and all actions remain keyboard reachable in both supported locales and visual themes.
- **SC-007**: One fresh delivery run completes every required backend, web, desktop, build, browser, architecture, and public-safety check with literal results recorded; no historical result count is reused as current evidence.
- **SC-008**: The delivery inventory contains zero local workflow artifacts and zero unclassified files in the reviewed delivery set.
- **SC-009**: The active feature pointer, roadmap status, release notes, and changed public-surface documentation agree on the same completed unit before 077 begins.

## Assumptions

- Existing authentication, principal ownership, session ownership, tool authorization, endpoint policy, and capability mutation gates remain the authority for this remediation.
- Browser-managed MCP authentication material remains out of scope; endpoints requiring embedded URL credentials or query-based authentication must be configured through a future host-owned mechanism rather than this surface.
- Allowed workspace contexts are supplied by an optional host-owned source and are not copied into each principal's durable mutable settings.
- Shared capability detail is metadata-first and intentionally more restrictive than owner detail.
- Unit 076 and 080 artifacts are historical records after their current Verified designation; corrections are specified and validated only in 081.
- Existing local workflow artifacts under `.superpowers/` are not product deliverables and remain untouched.
- Commit, push, release, version, tag, and deployment operations require separate maintainer approval.
- Unit 077 remains the next product capability unit after this remediation is Verified.
