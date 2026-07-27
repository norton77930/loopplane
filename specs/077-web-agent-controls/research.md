# Research: Web Agent Controls

## Decision 1: Use one host-owned, read-only control projection plus per-run permission selection

**Decision**: Add a safe agent-control projection for an owned session and permit an optional host-approved permission-mode name on each run submission. The selection applies only to that accepted run, is not stored in checkpoint/session metadata, and is validated by the host before the existing Gateway decide-stage policies enforce it. The same projection exposes authoritative ephemeral `active_run` and `last_accepted_run` posture recorded only after host acceptance; the client never treats its draft/request echo as effective. Browser-selectable modes are default-off and never include `bypassPermissions` or an equivalent approval bypass.

**Rationale**: Existing named permission modes and plan-mode policy are assembled on the host and enforced at the Tool Gateway. A per-run request preserves those ownership boundaries while avoiding browser-managed durable policy state. A safe projection is required because the current Web surface cannot authoritatively distinguish configured modes, plan behavior, rule posture, or budget-guard availability.

**Alternatives considered**:

- Client-only mode state: rejected because presentation would be mistaken for enforcement.
- Mutable host-global `RuntimeConfig`: rejected because browser mutation of startup configuration is out of scope.
- Durable per-session permission state: rejected because it would require new persistence/checkpoint semantics and an ADR/human gate.
- WebAPI-owned in-memory mode map: rejected because transport would own authorization semantics and reload/restart behavior would be ambiguous.
- Reassembling a separate Gateway for every run: rejected because it increases lifecycle complexity and risks changing Gateway ownership/stage behavior.

## Decision 2: Reuse plan-mode question/approval semantics without a direct exit toggle

**Decision**: Entry into plan posture is a host-approved per-run mode selection. During that run, the existing plan-mode state and decide-stage policy remain authoritative. Exit continues through the existing `exit_plan_mode` question and human answer path; the Web control surface may explain and present the pending request but cannot directly deactivate plan mode.

**Rationale**: Unit 038 already defines a per-run plan state and an explicit approved exit. Reusing the existing question transport preserves approval ordering and avoids an event-schema change.

**Alternatives considered**:

- A Web “turn plan off” mutation: rejected because it bypasses the existing exit request and approval semantics.
- A new plan lifecycle event: rejected because existing normalized question/approval events already carry the interaction and an event contract change would require a separate gate.

## Decision 3: Project permission rules as a bounded summary, not an editor

**Decision**: Show only safe posture metadata such as whether explicit rules are configured, their host-defined default decision category, which decision categories are present, the current/default named mode, and the allowed per-run choices/actions. Do not send raw tool patterns, field matchers, regex/glob expressions, private identifiers, or a browser-editable rule set.

**Rationale**: Unit 039 owns rule matching and deny-wins precedence. A summary meets the user need to understand posture without exposing policy internals or creating a second rule authoring/enforcement surface.

**Alternatives considered**:

- Full browser rule editor: rejected as a new policy-management product surface with validation, persistence, audit, and precedence decisions outside 077.
- Client evaluation of rules: rejected as a direct violation of host/Gateway enforcement ownership.

## Decision 4: Reuse authoritative cost endpoints and add only safe budget-guard posture

**Decision**: Consume the existing owner-scoped session-cost and caller-monthly-cost reads. Preserve exact decimal strings and `null`/availability states. The new agent-control projection may add host-calculated guard posture (`disabled`, `within`, `near`, `exceeded`, or `unknown`) and whether message/session/monthly/pre-turn guards are enabled, but it does not expose provider rates, raw estimates, ledger keys, or private host configuration. Cost views refresh after settled runs and explicit control refresh; no new push event is introduced.

**Rationale**: Existing cost accounting and budget enforcement are already authoritative. The Web currently has only a bundled local estimate, which cannot represent ledger availability, unpriced usage, or guard outcomes honestly.

**Alternatives considered**:

- Continue showing local price-table estimates as authoritative: rejected because unknown/unpriced values could be misrepresented and server guards may differ.
- Add cost/budget streaming events: rejected because polling after state changes is sufficient and an event-schema change is out of scope.
- Expose full budget configuration: rejected because the browser needs safe status, not raw runtime configuration.

## Decision 5: Reuse context binding, upload submission, and artifact references without new durability

**Decision**: Reuse the existing workspace-context list/detail/bind actions and current session context metadata. Submit completed upload references through the existing run-upload field rather than concatenating frontend control syntax into the user's prompt. For each explicitly sent, principal-owned non-image upload, backend assembly may create one compact JSON handoff containing only the server-generated reference and constant `read_upload` reader; maximum 8 handoffs per run and 256 UTF-8 bytes each. The host projects `attach_non_image_upload` only when the existing Gateway description advertises `read_upload`; stale/direct submissions without that action fail before model execution. WebAPI only assembles validated metadata and never resolves, authorizes, or invokes the tool. Preserve artifact references from normalized tool-completion state, but do not call the existing raw-content artifact retrieval route from agent controls. A resource action may add only the opaque reference to editable composer input so an explicit later send can use an existing authorized handoff/Gateway path. Show only references observed for the current session; do not add an upload/artifact index, content browser, retention model, or cross-principal sharing.

**Rationale**: Existing ownership checks already protect context binding, upload assembly, and artifact retrieval. The missing work is Web transport/state/presentation convergence, not a new storage boundary.

**Alternatives considered**:

- Prompt-injected upload references: rejected because references are structured input and should not become model-visible control syntax by accident.
- New upload/artifact listing endpoints: rejected because they imply new indexing, retention, and discovery semantics.
- Raw path/file browsing: rejected because it exposes private paths and creates browser-side execution/storage responsibilities.

## Decision 6: Generate follow-up suggestions with a pure client-side rules function

**Decision**: Derive at most three localized suggestions from already-visible settled state such as termination reason, context availability, completed attachments, visible tool outcome, or empty-session onboarding. Selection only populates editable composer input. Suggestion generation performs no fetch, model call, tool call, automatic send, or cost-bearing action.

**Rationale**: This improves continuation UX without adding hidden work or another execution path. The ordinary send path remains authoritative after the user chooses to submit.

**Alternatives considered**:

- Model-generated suggestions: rejected because they add hidden latency/cost and require new provider behavior.
- Automatically sending a selected suggestion: rejected because it removes user review and could trigger approvals/tools unexpectedly.
- Backend “smart suggestion” endpoint: rejected because deterministic visible-state rules are sufficient for the current scope.

## Decision 7: Use the existing full-page Settings workspace as the first-class control surface

**Decision**: Add Agent Controls as a first-level category in the current full-page Settings workspace, reusing its session/client injection, tab semantics, loading/error patterns, responsive layout, and state-preserving return to chat. Keep Inspection read-only. The current header may replace its local estimated cost with authoritative compact status and continues to provide the existing Settings entry; it does not gain a competing control drawer. Use the Composer only for the per-run mode choice, completed upload references, adopted suggestion text, and explicit send.

**Rationale**: Unit 080 established Settings as the state-preserving management workspace and Inspection as a read-only runtime view. The current Settings layout already supports keyboard-operated categories, shared/owner projections, session context binding, responsive reflow, and public-safe status handling. This separation avoids turning Inspection into a mutation surface or the Composer into an authorization authority.

**Alternatives considered**:

- New header control drawer: rejected because the existing Settings entry already opens a state-preserving full-page workspace and another entry would compete with it.
- Inspection-panel controls: rejected because Inspection is intentionally read-only and becomes an overlay at narrower widths.
- Composer-only controls: rejected because policy, cost, and context details outlive one draft; only run-specific input belongs there.
- A new route/page outside Settings: rejected because it would duplicate shell/navigation behavior and increase state-restoration risk.

## Decision 8: Preserve transport-neutral state and Desktop compatibility without Desktop parity

**Decision**: Keep shared state/data types and presentational pieces transport-neutral where Desktop already consumes them, but do not add Desktop controls or sidecar operations in 077. Web-only HTTP actions remain behind Web adapters. Desktop typecheck and regression tests prove that shared imports remain source compatible.

**Rationale**: Desktop uses selected shared Web reducers/components but does not expose the full Web shell or HTTP client. First-class Desktop parity requires a separately specified transport contract.

**Alternatives considered**:

- Make Desktop call the Web API client: rejected because its sidecar transport and lifecycle differ.
- Expand 077 into Desktop IPC parity: rejected by the feature non-goals and would require another outward contract/human gate.

## Decision 9: Treat the new outward control contract as an explicit pre-implementation human gate

**Decision**: Planning proposes an additive, typed, owner-scoped read projection for session agent controls, an optional per-run permission-mode field on existing run/turn submission contracts, authoritative ephemeral active/last-accepted posture fields, and the bounded non-image upload-handoff behavior defined above. No implementation may begin until the maintainer approves these exact outward HTTP/live-transport and existing-input semantic additions. Generated Web types must remain backend-owned and regenerated/checked in the same unit.

**Rationale**: The current API exposes cost, contexts, upload submission, artifact retrieval, approvals, and questions, but not authoritative permission posture/selection or budget-guard posture. A client-only substitute would be unsafe. Project governance requires approval before outward HTTP/SSE/WS contract changes.

**Alternatives considered**:

- Omit permission and guard controls: rejected because they are core 077 requirements.
- Hide an untyped payload inside an existing field: rejected because it evades contract review and type drift checks.
- Request an ADR immediately: not required for the proposed design because state remains per-run/non-durable and existing enforcement, event, checkpoint, Gateway, dependency, and default boundaries remain unchanged. If implementation cannot preserve those conditions, stop and propose an ADR before code changes.

## Decision 10: Protect the mixed working tree and frozen history throughout delivery

**Decision**: Treat completed 076/080/081 spec/plan/tasks as immutable. Record all 077 findings, contracts, evidence, rollback, and transition logic under `specs/077-web-agent-controls/`. Maintain separate complete-inventory and delivery-candidate records; exclude `.superpowers/**`, raw `openspec/**`, ignored QA evidence, and unknown user files. No staging/publication action is part of the specification workflow.

**Rationale**: The current tree contains multiple uncommitted units and local artifacts. Hunk-level ownership is necessary to prevent accidental history rewriting or unrelated staging.

**Alternatives considered**:

- Retro-edit Verified unit artifacts: rejected by Spec Kit alignment rules.
- Clean/reset/stash the tree: rejected because it could discard or hide user work.
- Bulk staging by directory: rejected because mixed files and local artifacts require explicit review.
