# Data Model: Web Agent Controls

No new durable record or migration is introduced. Agent-control data is either a safe host projection, existing owner-scoped cost/context/resource metadata, per-run request metadata, or derived client presentation state.

## 1. AgentControlProjection

An ephemeral, owner-scoped read model for one session.

| Field | Type | Rules |
|---|---|---|
| `session_id` | opaque string | Must identify a session owned by the requesting principal; non-owner and missing remain indistinguishable. |
| `permission` | `PermissionPosture` | Host-calculated safe projection; never supplied by the browser. |
| `budget` | `BudgetGuardPosture` | Host-calculated safe status; raw provider/config/ledger internals excluded. |
| `actions` | set of action names | Empty when only read-only posture is available; may include `select_permission_mode` and `attach_non_image_upload` only when the host advertises the corresponding safe capability. |

**Persistence**: none.

**Identity**: `(principal, session_id)` at request time; principal is never included in the response.

## 2. PermissionPosture

The safe description of current host policy capabilities.

| Field | Type | Rules |
|---|---|---|
| `default_mode` | mode identifier or `null` | Existing host default represented by a documented public identifier; no raw config object. |
| `selectable_modes` | ordered list of `PermissionModeOption` | Host-approved only; empty by default; excludes `bypassPermissions` and equivalents. |
| `selection_scope` | constant `run` | Prevents the UI from presenting the choice as durable session/global configuration. |
| `rules_configured` | boolean | Indicates whether explicit rules participate in enforcement. |
| `rule_default` | `allow`, `ask`, `deny`, or `null` | Safe decision category only. |
| `rule_decisions` | ordered unique subset of `allow`, `ask`, `deny` | No tool names, fields, patterns, regex, globs, or values. |
| `plan_entry_available` | boolean | True only when the host exposes the existing plan mode as selectable. |
| `plan_exit_requires_approval` | constant `true` when plan mode exists | Documents that no direct browser exit is available. |
| `active_run` | `AcceptedRunPosture` or `null` | Authoritative current in-memory run posture; absent when no run is active. |
| `last_accepted_run` | `AcceptedRunPosture` or `null` | Last host-accepted run posture retained only for display during the live host session; never checkpoint-rebuilt. |

**Validation**:

- Unknown mode identifiers are rejected before a run begins.
- Duplicate selectable identifiers are invalid host configuration and fail closed to no mutable action.
- `bypassPermissions` and any mode classified as approval-bypassing are never projected.
- Rules remain enforced with existing deny-wins composition; this projection cannot alter precedence.

## 3. AcceptedRunPosture

Authoritative ephemeral metadata recorded only after host validation accepts a run.

| Field | Type | Rules |
|---|---|---|
| `mode` | public mode identifier or `host-default` | Never copied from an unvalidated browser value. |
| `state` | `active` or `settled` | `active_run` uses `active`; `last_accepted_run` uses `settled`. |
| `plan_active` | boolean | Reads the existing per-run plan holder while active; false for settled display metadata. |

**Persistence**: in-memory host/controller session metadata only. It has no policy effect, is not written to checkpoint, and becomes unavailable after host rebuild/restart.

## 4. PermissionModeOption

A browser-safe choice that may be submitted for one run.

| Field | Type | Rules |
|---|---|---|
| `id` | stable mode identifier | Accepted only if present in the current host projection. |
| `kind` | `standard` or `plan` | Presentation metadata; enforcement remains host-owned. |
| `summary` | public-safe summary key | Localized by the client; no raw rule/config text. |

## 5. RunPermissionSelection

Optional metadata supplied with a run/turn request.

| Field | Type | Rules |
|---|---|---|
| `permission_mode` | mode identifier or omitted | Applies only to the submitted run; omission preserves current behavior exactly. |

**Lifecycle**:

1. `draft` — selected locally but not authoritative.
2. `submitted` — included with explicit user send.
3. `accepted` — host validated ownership and allow-list; existing policy enforces the run.
4. `active-plan` — accepted mode is plan and the run remains active.
5. `exit-pending` — existing `exit_plan_mode` question awaits a human answer.
6. `settled` — run terminated/completed; selection has no durable effect.
7. `rejected` — invalid/unavailable mode; no run starts under that selection.

No transition writes checkpoint/session configuration. A new run requires a new explicit submission or omission.

## 6. BudgetGuardPosture

A safe view over existing cost accounting and enforcement configuration.

| Field | Type | Rules |
|---|---|---|
| `tracking` | `available`, `unavailable`, or `unknown` | Does not imply zero spend. |
| `pricing` | `priced`, `partially_unpriced`, `unpriced`, or `unknown` | Distinguishes missing pricing from true zero. |
| `message_guard` | `enabled`, `disabled`, or `unknown` | Does not expose the raw configured cap. |
| `session_guard` | `disabled`, `within`, `near`, `exceeded`, or `unknown` | Calculated by the host from authoritative spend/cap when available. |
| `monthly_guard` | `disabled`, `within`, `near`, `exceeded`, or `unknown` | Calculated only for the requesting principal and current month. |
| `pre_turn_guard` | `enabled`, `disabled`, or `unknown` | Describes availability; actual refusal remains the existing guard outcome. |

**Presentation threshold**: `near` means authoritative tracked spend is at least 80% but below 100% of the applicable cap. This threshold affects presentation only and never changes enforcement.

**Failure rules**:

- Missing price, ledger failure, or unavailable accounting maps to an unknown/unavailable state, never zero.
- Exact cap/provider rate/ledger key/raw estimate fields are absent.
- A `budget-exceeded` termination remains authoritative even if a subsequent refresh cannot calculate posture.

## 7. CostView

Existing owner-scoped session and caller-month views consumed without changing backend accounting.

| Field | Type | Rules |
|---|---|---|
| `amount` | exact decimal string, `null`, or unavailable response | `"0"` is known zero; `null` is not tracked and must not render as zero. |
| `scope` | `session` or `principal-month` | Scopes remain visually and semantically distinct. |
| `currency` | existing USD contract | Client formats only after preserving exact server value. |

## 8. WorkspaceBindingView

Existing session context metadata plus host-projected actions.

| Field | Type | Rules |
|---|---|---|
| `bound_context` | safe context summary or `null` | Existing session projection is authoritative. |
| `available_contexts` | owner/allowed safe projections | Actions determine whether bind is permitted. |
| `actions` | safe action set | Bind is shown only when projected. |

Binding changes session metadata through the existing owner/session path. It does not copy ownership or establish a new filesystem/repository boundary.

## 9. SafeResourceReference

A session-associated upload or artifact reference already known to the Web client.

| Field | Type | Rules |
|---|---|---|
| `reference` | opaque reference | Never parsed into or replaced with a path. |
| `kind` | `upload` or `artifact` | Determines the existing authorized action path. |
| `label` | bounded public label | Upload filename or safe artifact label; must support long-text wrapping. |
| `status` | `uploading`, `ready`, `failed`, `available`, `expired`, or `unavailable` | Client/server outcome, not inferred resource ownership. |
| `actions` | subset of `attach-reference`, `inspect-metadata`, `remove-from-draft`, `retry` | Action availability is authoritative; `attach-reference` for a non-image upload requires top-level `attach_non_image_upload`; no execute/share/raw-open action. |
| `content` | always absent | Agent controls never fetch raw resource content into the browser. |

**Source**:

- Upload references come from the current draft/upload response and are submitted through the existing structured upload field.
- Artifact references come from current-session normalized tool completion and may be attached as opaque editable input for a later explicit send; the raw-content artifact retrieval route is not used by agent controls.
- No reference index, cross-session discovery, or durable browser cache is added.

## 10. NonImageUploadHandoff

Backend-owned metadata assembled only after explicit send and existing upload ownership validation.

| Field | Type | Rules |
|---|---|---|
| `type` | constant `loopplane_upload_reference` | Fixed server-owned discriminator. |
| `reference` | existing server-generated opaque reference | JSON-escaped; no user filename, MIME string, path, content, or arbitrary metadata. |
| `reader` | constant `read_upload` | Descriptive handoff only; WebAPI never resolves, authorizes, or invokes the tool. |

**Bounds and eligibility**:

- At most 8 non-image handoffs per accepted run.
- Each compact UTF-8 JSON handoff is at most 256 bytes.
- Image uploads continue through the existing image-block path and do not receive this handoff.
- The principal-owned upload is resolved and validated before metadata assembly.
- `attach_non_image_upload` is projected only when the existing host/Gateway tool description advertises `read_upload`.
- If availability changes or a stale/direct client submits a non-image reference without that action, the request fails publicly and safely before model execution.
- WebAPI may assemble only the validated metadata block; all later `read_upload` resolution, authorization, invocation, timeout, and error normalization remain inside the existing Tool Gateway.

## 11. FollowUpSuggestion

Pure client presentation data.

| Field | Type | Rules |
|---|---|---|
| `id` | deterministic key | Stable for the same visible state; not a server identifier. |
| `text` | localized user-input proposal | Editable and never presented as assistant-authored output. |
| `reason` | internal client enum | Derived only from visible settled state. |
| `priority` | small integer | Deterministic ordering; at most three visible suggestions. |

**Lifecycle**: `derived` → `selected` → `editable draft` → optional ordinary `sent`, or `dismissed/stale`.

A suggestion becomes stale and is removed/rederived when session, locale, permission selection, workspace binding, attachment state, or relevant terminal outcome changes.

## 12. AgentControlsViewState

Transport-neutral UI state used to preserve conversation behavior.

| Field | Type | Rules |
|---|---|---|
| `load_state` | `idle`, `loading`, `ready`, `refreshing`, `failed` | Existing content remains visible during safe refresh where possible. |
| `projection` | `AgentControlProjection` or `null` | Cleared on principal/session change. |
| `selected_mode` | mode identifier or `null` | Draft choice only until accepted; never labelled effective prematurely. |
| `cost_state` | session/month cost availability/value | Unknown/unpriced/unavailable remain distinct. |
| `references` | ordered `SafeResourceReference` list | Current session/draft only. |
| `suggestions` | up to three `FollowUpSuggestion` values | Purely derived; no network/model/tool side effect. |
| `error` | public-safe message key or `null` | No raw exception/input/config content. |

Opening/closing this state must not reset chat messages, streaming status, pending interactions, composer draft, inspection selection, or scroll position.
