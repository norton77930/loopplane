# Contract: Agent Control Projection And Per-Run Posture

## Gate status

**APPROVED — 2026-07-27.** The maintainer explicitly approved this additive outward Web/API contract for:

1. the new owner-scoped read route below; and
2. the optional `permission_mode` field on run/turn/live-submit input.

The approval is limited to the local implementation scope recorded in `plan.md`; it does not authorize publication or any architecture expansion.

## Owner-scoped projection

`GET /v1/sessions/{session_id}/agent-controls`

### Ownership

- The caller must own the session.
- Missing and non-owned sessions return the same public-safe not-found outcome.
- The response never contains `principal_id`, raw host configuration, rule match expressions, credentials, paths, or raw errors.

### Response shape

```json
{
  "session_id": "opaque-session-id",
  "permission": {
    "default_mode": null,
    "selectable_modes": [
      {
        "id": "plan",
        "kind": "plan",
        "summary": "permission.mode.plan"
      }
    ],
    "selection_scope": "run",
    "rules_configured": true,
    "rule_default": "ask",
    "rule_decisions": ["deny", "ask", "allow"],
    "plan_entry_available": true,
    "plan_exit_requires_approval": true,
    "active_run": {
      "mode": "plan",
      "state": "active",
      "plan_active": true
    },
    "last_accepted_run": null
  },
  "budget": {
    "tracking": "available",
    "pricing": "priced",
    "message_guard": "enabled",
    "session_guard": "within",
    "monthly_guard": "near",
    "pre_turn_guard": "enabled"
  },
  "actions": ["select_permission_mode", "attach_non_image_upload"]
}
```

### Field constraints

- `selectable_modes` is empty by default and contains only host-approved identifiers.
- `bypassPermissions` and any equivalent approval-bypassing mode are always absent and rejected if submitted.
- `attach_non_image_upload` is present only when the host obtains an existing Gateway tool description for `read_upload`; its presence authorizes metadata handoff eligibility, not tool invocation.
- `selection_scope` is always `run`; no durable mutation action exists.
- `rule_decisions` is a unique decision-category summary only. Tool names, matcher fields, regex, globs, match values, and ordering are absent.
- `active_run` is present only after host validation has accepted and started the current run; `last_accepted_run` is the most recent settled accepted posture retained in live host memory for display.
- Active/last posture mode is a host-derived public identifier or `host-default`, never an unvalidated request echo. It has no enforcement effect, is not checkpointed, and becomes unavailable after host rebuild/restart.
- Budget states use only the enums in `data-model.md`; exact caps/rates/ledger keys/raw estimates are absent.
- Any projection-building ambiguity or invalid host mode configuration fails closed to read-only status with no selection action.

## Per-run permission selection

Existing run, session-turn, and live-submit input gains one optional field:

```json
{
  "prompt": "...",
  "permission_mode": "plan"
}
```

### Semantics

- Omitted field preserves existing behavior exactly.
- The host validates the requested identifier against the current safe projection for the owned session before the run is accepted.
- An accepted identifier influences only the new run's existing permission/plan decide policies.
- It is not written to checkpoint/session metadata and is not a host-global mutation.
- Unknown, unavailable, duplicated, malformed, or approval-bypassing identifiers fail before model/tool execution.
- Public failure contains a stable code/message and never echoes the submitted identifier or host allow-list internals.
- Existing explicit rules and safety deciders retain deny-wins precedence.

## Plan mode lifecycle

- Selecting `plan` enters the existing plan posture for that run.
- The UI labels the selection as `draft` before send. It may label a mode authoritative only after a subsequent owner-scoped agent-control projection returns that mode in `active_run` or `last_accepted_run`; submit payload state or client echo is never sufficient.
- The client refreshes the projection after the existing transport reports run activity and again after the run settles. A fast completed run is confirmed through `last_accepted_run`; an in-flight run is confirmed through `active_run`.
- `exit_plan_mode` remains an agent tool action routed through the existing question event and answer operation.
- Reject, disconnect, timeout, stale request, or non-owner answer keeps plan restrictions active.
- No direct Web mutation clears plan state.
- No event type/schema is added.

## Compatibility

- Existing callers that omit `permission_mode` receive byte-identical default behavior.
- Existing response envelopes remain unchanged except for the new GET route.
- Backend-owned generated Web artifacts are regenerated/verified in the same unit.
- Desktop receives no new sidecar/IPC operation and must remain source compatible with shared types/components.
