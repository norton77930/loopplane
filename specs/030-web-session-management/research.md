# Research: Web Session Management (030)

All decisions are grounded in the current `main` code. No NEEDS CLARIFICATION remain.

## D1 — How to persist an updatable title

**Decision**: Persist the title in the **existing** `SessionMetaPayload.label`
(`src/loopplane/checkpoint/records.py`) by **appending a fresh `SessionMetaRecord`** on rename,
and changing the meta-pick in listing/rebuild from the **first** session-meta to the **last**.

**Rationale**: The store is **append-only** (Constitution IV; `checkpoint/base.py`). Appending a
new meta record honours that. `rebuild_session` already overwrites `result.label` for each
session-meta it sees, so "last meta wins" is **already** the resume behaviour — listing just needs
to match it. The `label` field is already plumbed end-to-end to `SessionSummaryView.label` and
`GET /v1/sessions`; it is simply never updated today. This is the smallest correct change.

**Alternatives considered**:
- *In-place mutation of the first meta record* — violates the append-only contract (IV).
- *A new `session-title` record kind* — would touch `RECORD_KINDS`, both stores, and `rebuild.py`
  for no benefit, since `SessionMetaRecord` already carries `label`.

## D2 — Delete semantics

**Decision**: **Real removal**. `FileCheckpointStore.delete_session` removes the session directory
(idempotent — a no-op if absent); `SqliteCheckpointStore.delete_session` runs
`DELETE FROM records WHERE session_id = ?`.

**Rationale**: Matches the user-facing verb (the session is gone after reload/restart). The store
has **no** `deleted`/soft-hide concept today; a soft delete would add a flag plus filtering in four
readers (both `list_sessions`, both load/rebuild paths) — more surface for less clarity.

**Alternatives considered**: *Soft-delete flag* — rejected (wider surface, durable records have no
"hidden" notion).

## D3 — Routes, ownership, and the live session

**Decision**: `PATCH /v1/sessions/{id}` (rename) and `DELETE /v1/sessions/{id}` (delete) in
`webapi/app.py`, both resolved through the existing `_owned_or_404` so a non-owner (or unknown id)
gets a **404** with no existence leak. `DELETE` cancels a live in-memory session entry first (set
its close), then deletes the durable records.

**Rationale**: Mirrors the existing per-session routes (`cancel`, `history`) and their scoping
(`GET /v1/sessions` already filters by `principal.id`; `_owned_or_404` already resolves the durable
owner). No new authorization model.

## D4 — Boundary-safe call chain

**Decision**: **webapi route → `LoopPlaneHost` method → `RuntimeController` method →
`CheckpointStore` method**.

**Rationale**: The contract test (`tests/contract/test_webapi_boundary.py`) restricts
`loopplane.webapi` to importing only `loopplane.{events,host,webapi}`. `host.py` already imports the
controller and the controller already owns the checkpoint store, so the new methods ride existing,
permitted internal imports — the boundary test stays green.

## D5 — Extending the session summary contract

**Decision**: Extend `SessionSummaryView` (and its `_SummaryLike` Protocol) from `{session_id,
label}` to `{session_id, label, last_active_at, created_at}` (the source `SessionSummary` already
carries the timestamps).

**Rationale**: The sidebar needs **recency** for grouping; today the frontend type
(`apps/web/src/api/types.ts`) wrongly declares `last_active_at` (which the server never sends) and
ignores `label`, so the sidebar shows the raw id. This fixes the contract end-to-end. The pinned
field-set assertions in `test_webapi_boundary.py` and `test_webapi_us4.py` are updated as part of
this unit's diff.

## D6 — Frontend recency grouping

**Decision**: A small **pure** helper (`apps/web/src/lib/sessionGroups.ts`) buckets sessions into
**Today / Yesterday / Earlier** by the viewer's local day from `last_active_at`.

**Rationale**: Simple, unit-testable, no dependency; grouping is a presentational concern over the
new timestamp field.

## D7 — Deleting the currently-open session

**Decision**: When the open session is deleted, the app returns to the **empty / new-conversation**
state (clear the active session, reset the view).

**Rationale**: Avoids dangling state pointing at a removed session; matches the spec's FR-006.

## No-dependency / no-ADR note

No new runtime or frontend dependency. The change extends a **declared interface** additively and
touches neither the Tool Gateway (V) nor the Event Bus (VI) → **no ADR** (same posture as 027/028).
Rollback is reverting the diff.
