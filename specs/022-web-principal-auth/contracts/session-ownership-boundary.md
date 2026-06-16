# Contract: Per-principal session ownership

Every session belongs to the principal that opened it; the web/API enforces it on listing
and every per-session route. Live ownership is in the web/API registry; durable ownership
is the unit-021 checkpoint metadata.

## Obligations

1. **Ownership at open (FR-005)**: the principal that opens a session OWNS it; ownership is
   set at the boundary (`SessionEntry.owner` + `principal_id` in the session's checkpoint
   metadata), never read from the client.
2. **Scoped listing (FR-006)**: `GET /sessions` returns only summaries whose
   `principal_id` equals the caller's id.
3. **Not-found, not forbidden (FR-007)**: every per-session route — events, submit,
   approvals, questions, cancel, history, resume, artifacts — returns **404** when the
   session is not owned by the caller. It MUST NOT return a distinguishable 403 (no
   existence leak).
4. **Durable across restarts (FR-008)**: the owner persists in `SessionMetaPayload.principal_id`
   (surfaced on `SessionSummary.principal_id`), so a fresh process over the same storage
   still scopes listing and resume per principal.
5. **No core change (FR-010)**: the runtime loop, gateway, and event bus are unchanged;
   the `principal_id` plumbing is optional (`default None`) — with it unset every existing
   path is byte-identical. No new runtime dependency.
6. **Metadata-only (FR-009)**: responses never carry conversation content; a denied or
   not-found response carries only the fixed public-safe envelope.

## Scoping matrix (two principals A, B)

| Action by B on A's session | Result |
|---|---|
| `GET /sessions` | A's session absent from B's list |
| history / events / submit / resume / artifacts / cancel | `404` (no data, no existence) |
| (A on A's own) | succeeds as before |

## Non-obligations

- No concurrent multi-user execution (the host stays single + sequential; the existing
  `409` on a second active run is unchanged).
- No roles/permissions beyond ownership.
- Ownerless legacy durable sessions (pre-022) are listed to **no** principal.

## Rollback (Constitution X)

Revert `Authenticator` to `→ bool` + the router-level dependency, drop `SessionEntry.owner`
and the ownership checks, and remove the optional `principal_id` field from the checkpoint
metadata / `SessionSummary` / recorder / controller / host. The runtime core is untouched,
so rollback is local to `webapi` + the additive metadata field.
