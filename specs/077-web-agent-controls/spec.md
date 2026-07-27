# Feature Specification: Web Agent Controls

**Feature Branch**: `077-web-agent-controls`

**Created**: 2026-07-27

**Status**: Draft

**Input**: Add host-owned, metadata-first, default-preserving Web controls for plan and permission posture, cost and budget visibility, workspace/file/artifact references, and deterministic follow-up suggestions after unit 081, while reusing existing enforcement and ownership boundaries.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Control Plan And Permission Posture Safely (Priority: P1)

A signed-in user can understand the current execution posture for an owned session, request one of the permission modes explicitly exposed by the host, enter plan posture through the existing plan mode, and review an exit-plan request through the existing approval experience. The Web surface explains the effective high-level restrictions without exposing internal rule expressions or creating a second enforcement path.

**Why this priority**: Plan and permission posture directly affect whether the agent may act, ask for approval, or remain read-only. A control that is visually convincing but disconnected from existing enforcement would create the highest-risk form of false safety.

**Independent Test**: For one owned session, expose a host-approved set of permission modes, select a non-plan mode and plan mode, submit turns, observe the resulting existing approval/plan behavior, review an exit-plan request, and verify another principal cannot inspect or change the session posture.

**Acceptance Scenarios**:

1. **Given** an owned session and a host-exposed current permission posture, **When** the user opens agent controls, **Then** the current mode, plan state, safe summary, and available actions are shown without internal rule expressions or host configuration details.
2. **Given** a host-approved mode is selectable, **When** the owner requests that mode for the next run in the current session, **Then** that run uses the existing permission enforcement path and the displayed posture refreshes to the authoritative accepted result without creating durable session configuration.
3. **Given** the owner selects the existing plan mode, **When** the next eligible turn begins, **Then** the normal read-only planning restrictions apply and tool approval precedence remains unchanged.
4. **Given** the agent requests exit from plan mode, **When** the owner approves or denies that request, **Then** the existing approval path determines the result; no direct Web action bypasses the exit request or approval ordering.
5. **Given** the host does not expose mutable permission controls, **When** the user opens agent controls, **Then** safe read-only posture remains available and unsupported mutation actions are absent.
6. **Given** another principal or a non-owned session identifier, **When** plan or permission posture is listed, opened, or changed, **Then** the response does not disclose whether the private session or posture exists.

---

### User Story 2 - Understand Cost And Budget Status Honestly (Priority: P1)

A signed-in user can see the current session spend, their current monthly spend, applicable budget limits or guard status that the host safely exposes, and whether a value is known, unavailable, or unpriced. The interface never presents missing or unpriced information as zero cost and never reveals another principal's usage or host-private pricing configuration.

**Why this priority**: Cost and budget controls are only trustworthy when unknown data is represented honestly and the displayed status matches the existing server-side accounting and pre-turn guard.

**Independent Test**: Exercise priced, unpriced, unavailable, below-limit, near-limit, and exceeded states for two principals; verify all labels and actions are honest, owner-scoped, and consistent with the existing cost and budget outcomes.

**Acceptance Scenarios**:

1. **Given** authoritative priced usage is available, **When** the user opens cost controls, **Then** session and monthly spend are shown using the existing server-side values and currency precision.
2. **Given** usage is unknown, unavailable, or unpriced, **When** cost controls render, **Then** each state is distinguishable and none is displayed as `$0` or equivalent zero spend.
3. **Given** the host exposes an applicable message, session, or monthly limit, **When** usage approaches or exceeds it, **Then** the user sees a safe status and the existing guard remains the sole enforcement authority.
4. **Given** the pre-turn guard refuses a turn, **When** the result is shown, **Then** the user receives the existing public-safe budget outcome without hidden provider rates, token-estimation internals, or host configuration values.
5. **Given** another principal, **When** they request session or monthly cost metadata, **Then** they cannot see or infer the first principal's usage, limits, or pricing availability.

---

### User Story 3 - Work With Session Context And Safe References (Priority: P2)

A signed-in user can see the workspace context bound to the current session, choose an allowed bind action already exposed by the host, and review safe metadata references for uploads or artifacts associated with that session. Opening or using a reference continues through existing ownership and tool boundaries; the control surface does not become a file system, artifact store, or cross-principal sharing system.

**Why this priority**: Users need to understand what workspace and supporting material the agent is using, but raw paths, binary durability, and browser-side execution would cross established security and persistence boundaries.

**Independent Test**: Bind an owned or allowed context to an owned session, list session-safe upload/artifact references, open an authorized reference, and verify non-owner, missing, expired, private-path, and unsupported-reference cases remain non-disclosing and non-executable.

**Acceptance Scenarios**:

1. **Given** an owned session, **When** the user opens workspace controls, **Then** the current bound context and host-projected bind choices are shown using safe metadata and projected actions.
2. **Given** an allowed bind action, **When** the owner selects a context, **Then** the existing session-binding operation updates the authoritative session metadata without copying or changing the context's ownership.
3. **Given** session-associated uploads or artifacts, **When** references are listed, **Then** only safe identifiers, labels, kinds, statuses, and allowed actions are shown; raw local paths and raw content are absent.
4. **Given** an authorized reference can already be used by the agent, **When** the user chooses that action, **Then** only an available projected reference action is offered; non-image upload handoff occurs after explicit send and ownership validation through bounded opaque metadata, while later reading remains Gateway-routed and the controls never fetch raw content into the browser.
5. **Given** an unsupported, expired, missing, or non-owned reference, **When** it is opened, **Then** the outcome is public-safe and does not disclose another principal's path, content, or resource existence.
6. **Given** the host has no safe reference projection, **When** workspace controls render, **Then** the context controls remain usable and the reference section shows a distinct unavailable or empty state without inventing durable content.

---

### User Story 4 - Continue Work With Deterministic Suggestions (Priority: P3)

A user may receive a small set of optional follow-up suggestions derived deterministically from already-visible interface state. Selecting a suggestion places or applies the proposed user input without sending it automatically; any resulting turn still follows the normal authentication, permission, approval, Tool Gateway, Event Bus, and cost paths.

**Why this priority**: Follow-up suggestions improve task continuity, but they must not introduce hidden model/tool calls, surprise cost, or an alternate execution route.

**Independent Test**: Produce suggestions for representative completed, blocked, empty, and error states; select, edit, dismiss, and send a suggestion while proving suggestion generation itself performs no model/tool request and incurs no server-side model cost.

**Acceptance Scenarios**:

1. **Given** a supported visible state, **When** follow-up suggestions appear, **Then** no more than three concise suggestions are shown and generation itself performs no model or tool call.
2. **Given** a suggestion, **When** the user selects it, **Then** it populates or applies editable user input without automatically sending a turn.
3. **Given** the user sends adopted suggestion text, **When** the turn begins, **Then** it follows the same authentication, permission, approval, Gateway, event, and cost behavior as manually entered text.
4. **Given** no deterministic suggestion rule applies or suggestions are disabled, **When** the conversation settles, **Then** no suggestion is shown and no fallback model request occurs.
5. **Given** a locale change, narrow viewport, keyboard navigation, or assistive technology, **When** suggestions are used, **Then** they remain optional, dismissible, localized, and clearly distinct from assistant-authored output.

---

### User Story 5 - Trust The Delivered Agent Controls (Priority: P3)

A maintainer can verify that agent controls are projections over existing authoritative behavior, that two principals remain isolated, and that Web, Desktop consumers, responsive presentation, public documentation, and rollback guidance remain consistent.

**Why this priority**: The controls combine security posture, cost, workspace metadata, and convenience UI. Fresh evidence is required to prevent stale documentation or presentation-only behavior from being mistaken for enforced policy.

**Independent Test**: Run focused and full backend/Web/Desktop checks, a two-principal contract matrix, the required Chromium accessibility/reflow matrix, public-safety and boundary audits, and documentation convergence checks from a reviewed working-tree inventory.

**Acceptance Scenarios**:

1. **Given** all implementation slices are complete, **When** required automated and browser gates run, **Then** fresh literal results, failures, skips, and known limitations are recorded under 077.
2. **Given** plan, permission, cost, workspace, reference, and suggestion controls, **When** two principals exercise every list/detail/action path, **Then** there are zero cross-principal disclosures or mutations.
3. **Given** existing chat, inspection, capability settings, transport, attachment, and Desktop-consumer behavior, **When** agent controls are opened and closed, **Then** those workflows remain compatible and retain their state.
4. **Given** a failed or skipped required gate, **When** completion is evaluated, **Then** 077 remains unverified unless the maintainer explicitly accepts the exact limitation.

### Edge Cases

- A session has no explicit permission mode while the host has a default posture.
- A host exposes a current posture but no selectable modes.
- An explicit rule and a named permission mode interact; deny precedence must remain authoritative.
- A plan-exit request becomes stale, is denied, or belongs to another principal.
- Cost exists for the session but monthly ledger data is unavailable, or the reverse.
- A model is unpriced, usage is partially known, or the pre-turn estimate cannot be computed.
- A limit exists but its exact numeric value is intentionally not exposed by the host.
- A context authorization changes between listing and binding.
- An upload or artifact reference is missing, expired, malformed, unsupported, no longer owned, exceeds the bounded handoff limit, or is submitted after `read_upload` availability changes.
- Safe reference labels or translated control text are unusually long.
- A suggestion is visible while the user changes locale, session, permission posture, or workspace context.
- Agent controls open while a response streams, an approval is pending, or transport reconnects.
- Mutation or runtime activation is disabled while read-only control metadata remains available.
- The working tree still contains frozen 076/080/081 artifacts and protected local workflow files.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide one first-class Web agent-controls surface associated with the current owned session.
- **FR-002**: The surface MUST project authoritative host-owned metadata and actions; visual state MUST NOT be treated as an enforcement authority.
- **FR-003**: The system MUST show the host default posture plus authoritative ephemeral active/last-accepted run mode and active plan state when available, clearly distinguishing them from an unsubmitted draft choice.
- **FR-004**: Permission summaries MUST expose only documented high-level outcomes and MUST NOT expose raw rule expressions, matching inputs, host configuration internals, private identifiers, or credentials.
- **FR-005**: The host MUST control which named permission modes, if any, are selectable for a session.
- **FR-006**: A requested permission mode MUST apply only to one accepted run within an owned session, MUST NOT create durable session or host-global configuration, and MUST use the existing permission enforcement path.
- **FR-007**: Selecting the existing plan mode MUST preserve its read-only restrictions and existing deny/approval precedence.
- **FR-008**: Exiting plan mode MUST use the existing exit request and approval path; the Web surface MUST NOT provide a bypass action that directly disables plan restrictions.
- **FR-009**: Explicit denies and other existing safety deciders MUST continue to take precedence over a selected named mode.
- **FR-010**: When mutable plan or permission actions are unavailable, the system MUST preserve safe read-only posture visibility without displaying ineffective controls.
- **FR-011**: Plan and permission list, detail, and action outcomes MUST preserve session ownership and non-disclosure across principals.
- **FR-012**: The system MUST show authoritative session spend and principal-month spend when each value is available.
- **FR-013**: Known zero spend, unknown spend, unavailable accounting, and unpriced usage MUST be represented as distinct states.
- **FR-014**: Unknown, unavailable, partial, or unpriced cost MUST NOT be displayed as zero currency value.
- **FR-015**: The system MUST show only host-approved budget limit and guard metadata, and the existing server-side checker/guard MUST remain the sole enforcement authority.
- **FR-016**: Cost and budget projections MUST NOT expose another principal's usage, provider rates, raw token-estimation internals, ledger keys, or host-private configuration.
- **FR-017**: Existing budget refusal reasons and public-safe failures MUST remain authoritative and MUST NOT be rewritten into a contradictory client-only status.
- **FR-018**: The system MUST show the current session's bound workspace context and only those bind choices and actions already authorized for the requesting principal.
- **FR-019**: Context binding MUST use the existing owner/session authorization path and MUST NOT copy, re-own, or make shared contexts mutable.
- **FR-020**: The system MAY show upload or artifact references only through a host-owned safe metadata projection associated with the owned session.
- **FR-021**: Safe reference projections MUST exclude raw content, raw local paths, authentication material, provider metadata, and other principals' identifiers.
- **FR-022**: Using a reference MUST attach only its opaque identifier to editable user input or reuse an existing Gateway-routed read action after explicit send; the controls MUST NOT fetch raw resource content into the browser, execute files, or directly read host paths.
- **FR-023**: The feature MUST NOT add binary durability, general file browsing, cross-principal artifact sharing, or a new artifact persistence boundary.
- **FR-024**: Unsupported, expired, missing, malformed, and unauthorized context/reference outcomes MUST be public-safe and non-disclosing.
- **FR-025**: Follow-up suggestions MUST be optional, deterministic from already-visible client state by default, and limited to at most three suggestions at one time.
- **FR-026**: Suggestion generation MUST NOT invoke a model or tool, create hidden server-side usage, or claim to be assistant-authored output.
- **FR-027**: Selecting a suggestion MUST NOT automatically submit a turn and MUST leave the proposed input editable or dismissible.
- **FR-028**: Sending adopted suggestion text MUST use the same authentication, ownership, permission, approval, Gateway, Event Bus, transport, and cost path as manually entered text.
- **FR-029**: Agent controls MUST distinguish loading, empty, read-only, unavailable, unpriced, disabled, pending, denied, and failed states where applicable.
- **FR-030**: All controls and status changes MUST remain usable with keyboard-only navigation, visible focus, suitable announcements, reduced motion, forced colors, and 200%/400% reflow.
- **FR-031**: English and Traditional Chinese MUST remain available, and document language MUST follow the active locale.
- **FR-032**: Opening and closing agent controls MUST preserve the current session, draft, streaming, approval, message, inspection, and scroll state.
- **FR-033**: Existing Web component and API types consumed by Desktop MUST remain source compatible unless a separately approved contract change is required.
- **FR-034**: The feature MUST preserve the Agent Loop, Tool Gateway, Runtime Event Bus, checkpoint schema, permission DSL, pricing/budget accounting, approval ordering, enforcement precedence, dependencies, and existing defaults.
- **FR-035**: The feature MUST NOT expose provider credentials, MCP authentication, raw RuntimeConfig values, private paths, raw artifact content, raw exceptions, or internal implementation names.
- **FR-036**: Any required browser-mutable durable plan/permission/budget semantics, changed approval or enforcement ordering, new artifact persistence/sharing boundary, new dependency/default, or Event Bus/checkpoint/Gateway contract change MUST stop at a maintainer/ADR gate before implementation.
- **FR-037**: Completion evidence MUST include fresh focused/full backend, Web, Desktop, Chromium, architecture-boundary, formatting, typing, build, working-tree ownership, openspec-exclusion, and public-safety results.
- **FR-038**: Required failures and skips MUST be recorded literally and MUST block a Verified status unless explicitly accepted by the maintainer.
- **FR-039**: Completed 076, 080, and 081 specification/task histories MUST remain frozen; protected `.superpowers/**`, raw `openspec/**`, QA artifacts, and unknown user files MUST remain outside any delivery candidate set.
- **FR-040**: No staging, commit, push, pull request, version, tag, release, or deployment is authorized by this specification workflow.
- **FR-041**: Planning and task artifacts MUST define rollback or feature-isolation guidance for every behavior slice and MUST identify the public documentation and status records that require convergence before any Verified transition.
- **FR-042**: Browser-selectable permission modes MUST exclude `bypassPermissions` and any equivalent mode that suppresses the existing authorization or human-approval boundary.
- **FR-043**: The host projection MUST expose active and last-accepted run posture as non-durable display metadata, including the effective public mode identifier and active plan flag; this metadata MUST have no enforcement effect and MUST become unavailable after host rebuild/restart rather than being reconstructed from checkpoint state.
- **FR-044**: A non-image upload reference MAY be attached only after explicit send, existing principal ownership validation, and host confirmation that `read_upload` is available; the backend handoff MUST contain only bounded server-generated opaque-reference metadata, and unavailable capability MUST remove the attach action and reject stale/direct submissions before model execution.

### Key Entities

- **Agent Control Projection**: The safe, owner-scoped summary of available plan, permission, cost, workspace, reference, and suggestion controls for one session.
- **Execution Posture**: The current named permission mode, plan state, safe restriction summary, and host-projected actions for an owned session.
- **Cost And Budget Status**: Owner-scoped session/month values, availability/pricing states, optional host-approved limits, and guard outcome metadata.
- **Workspace Binding Summary**: The authoritative current context plus host-projected context choices and bind actions for one owned session.
- **Safe Resource Reference**: Session-associated upload or artifact metadata containing only safe identity, label, kind, status, and projected actions.
- **Follow-Up Suggestion**: Optional deterministic user-input text derived from already-visible state, never an assistant message or automatically submitted turn.
- **Delivery Ownership Bucket**: The 077/frozen-history/local classification applied to every changed file or hunk during later implementation and delivery review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every tested permission mode and plan-state scenario, displayed posture and available actions agree with the authoritative host result, with zero client-only enforcement decisions.
- **SC-002**: Across the tested explicit-rule and named-mode matrix, there are zero cases where a mode overrides an existing deny or approval requirement.
- **SC-003**: Across two principals, there are zero successful cross-principal reads, mutations, approvals, bindings, cost disclosures, or reference disclosures through agent controls.
- **SC-004**: Every tested known-zero, known-nonzero, unknown, unavailable, partial, and unpriced cost state is displayed distinctly, with zero unknown or unpriced values represented as zero.
- **SC-005**: Every displayed workspace/upload/artifact reference contains only documented safe metadata/actions with zero raw path/content/credential/provider/cross-principal disclosure; every non-image attach action requires projected `read_upload` availability, and all over-8, over-256-byte, stale, unavailable, or non-owned handoffs are rejected before model execution.
- **SC-006**: Suggestion generation produces no model/tool/network request attributable to generation, displays no more than three options, and submits zero turns until the user explicitly sends one.
- **SC-007**: Owners can reach and understand each agent-control category within two navigation actions, and can return to the unchanged conversation in one action.
- **SC-008**: Required controls remain reachable without document-level horizontal overflow at 1440, 1024, 768, 640, 375, and 320 CSS-pixel widths in both supported locales; keyboard, focus return, reduced-motion, and forced-color scenarios have zero blocking failures.
- **SC-009**: Existing chat, streaming, approval, inspection, capability settings, attachment, session, and Desktop-consumer regression suites have zero feature-caused failures.
- **SC-010**: One fresh delivery run records every required automated/browser/public-safety result and contains zero frozen-history edits, protected local artifacts, raw openspec paths, staged unknown files, or unclassified delivery candidates.

## Assumptions

- Existing authentication and session ownership remain the authority for every control and metadata projection.
- Existing plan mode, permission rules/modes, approval handling, cost accounting, budget guards, workspace binding, attachments, artifact handoff, and Gateway-routed reads remain authoritative and are reused rather than reimplemented.
- Permission selection, where host-authorized, is submitted per run within an owned session and does not create browser-controlled durable session or host-global configuration.
- A host may expose posture, budget, or reference metadata as read-only or unavailable; the Web surface does not invent unsupported authority.
- Follow-up suggestions use deterministic rules over already-visible client state and do not require a provider credential, model call, tool call, or server-side pricing change.
- Desktop and CLI receive no first-class control surface in 077; Desktop compatibility is limited to preserving shared Web component/type consumers.
- Binary durability, cross-principal sharing, remote-control semantics, and broad file-system browsing remain deferred to separately specified units.
- Any planning discovery that crosses FR-036 requires explicit maintainer approval and an ADR when the affected architecture boundary requires one.
