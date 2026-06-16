# Implementation Plan: Web Principal Authentication & Per-Principal Session Scoping

**Branch**: `022-web-principal-auth` (main-only) | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/022-web-principal-auth/spec.md`

## Summary

Make the web/API host's auth boundary **identity-bearing** and scope every session
operation to its owner. `webapi/auth.py` gains a small public `Principal` (an opaque
`id`); `Authenticator` changes from `→ bool` to `→ Principal | None` (the verifier maps
the credential to a principal or denies); `DENY_ALL` returns `None`; `make_auth_dependency`
now **resolves a `Principal`** and is injected into each route. A reference
`token_authenticator({token: principal_id})` ships for dev/tests (host keeps **no
credential store**). In `webapi/app.py`, the principal that opens a session **owns** it
(tracked on `SessionEntry.owner`), the listing returns only the caller's sessions, and
every per-session route returns **404** (never 403) for a session the caller does not own.
For **durable** scoping (across restarts), the owner is threaded — **additively, default
`None`** — into the checkpoint metadata via the unit-021 seam: `SessionMetaPayload.principal_id`
→ written by `SessionRecorder` → surfaced on `SessionSummary.principal_id` by both backends
→ read by the web/API listing. The runtime loop/gateway/event-bus are untouched; the
plumbing is optional metadata with no behavior change when `principal_id` is `None`. Login
UI + E2E are unit 023; concurrent multi-user execution stays out of scope.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: no new runtime dependency. FastAPI stays the `web` extra (the
boundary already lives there); the runtime core install is unchanged.

**Storage**: reuses the unit-021 checkpoint metadata (the owner rides in `SessionMetaPayload`);
no new store, no schema migration (the field defaults to `None`).

**Testing**: `pytest`. New web/API tests drive the FastAPI app with a reference
token→principal authenticator: two principals, ownership scoping (list + per-session 404),
durable scoping across a fresh app over the same storage, default-deny with no
authenticator, and a public-safety assertion that no credential/principal leaks. Plus a
checkpoint round-trip for the new `principal_id` field. All offline.

**Target Platform**: a Python library (embeddable runtime + its web/API transport)

**Project Type**: library — additive change to `loopplane.webapi` plus optional
`principal_id` metadata plumbing through `checkpoint` → `controller` → `host`.

**Performance Goals**: unchanged; ownership checks are O(1) live-registry lookups and a
filter over the existing session listing.

**Constraints**: runtime loop/gateway/event-bus **unchanged**; `principal_id` is an
**optional, default-`None`** addition (existing behavior byte-identical when unset);
default-deny + fail-safe preserved; **404 not 403** for non-owners (no existence leak); no
credential/principal in any response/error; no new dependency.

**Scale/Scope**: `webapi` (auth + app + sessions + `__init__`) and **additive** owner
plumbing across `checkpoint` (records/base/file/sqlite/recorder) + `controller` + `host`;
api-reference/changelog/board updates; a new web/API auth-scoping test module.

## Constitution Check

*GATE: evaluated before Phase 0 and re-checked after Phase 1. Result: **PASS**.*

| Principle | Gate | Verdict |
|---|---|---|
| I — Spec-First | Traces to `spec.md` (FR-001–011). | PASS |
| II — Greenfield | `Principal`, the reference authenticator, and the scoping are written fresh. | PASS |
| III — Harness before automation | Transport-boundary security; adds no loop automation. | PASS |
| IV — Boundary Clarity | Strengthens the auth boundary (identity) and session ownership; consumers still reach the runtime only through `loopplane.host`. | PASS |
| V — Tool Gateway Ownership | Untouched — no tool resolution/execution. | PASS |
| VI — Event Bus Ownership | Untouched — the web/API still consumes the normalized stream; no re-emit. | PASS |
| VII — Public-Safe | Default-deny preserved; 401/404 never echo the credential; responses stay metadata-only; the owner id is a host-supplied principal, not a secret. | PASS (FR-003, FR-009) |
| VIII — No SDK Replacement | No framework adopted; FastAPI stays a transport extra; the runtime core is unchanged. | PASS (FR-010) |
| IX — Reference, not clone | The auth model is re-derived for LoopPlane's seam, not cloned. | PASS |
| X — Testable Evolution | Two-principal + restart + default-deny tests; rollback = revert the boundary to `→ bool` and drop the optional `principal_id` field. | PASS |

No violations — Complexity Tracking is intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/022-web-principal-auth/
├── plan.md / research.md / data-model.md / quickstart.md
├── contracts/
│   ├── auth-principal.md            # Principal, Authenticator (→Principal|None), default-deny, reference verifier
│   └── session-ownership-boundary.md # ownership scoping, 404-not-403, durable owner, no-leak, no core change
├── checklists/requirements.md
└── tasks.md                         # created by /speckit.tasks
```

### Source Code (repository root)

```text
src/loopplane/webapi/
├── auth.py        # EDIT — Principal; Authenticator → Principal|None; DENY_ALL→None; make_auth_dependency→Principal; token_authenticator (reference)
├── app.py         # EDIT — inject principal per route; owner on open; list filters by owner; per-session 404 for non-owners; durable-owner check on resume/history/artifacts
├── sessions.py    # EDIT — SessionEntry.owner; run_session carries owner + principal_id into host.session
└── __init__.py    # EDIT — export Principal (+ token_authenticator)

# Additive, optional (default None) owner plumbing — no behavior change when unset:
src/loopplane/checkpoint/records.py   # SessionMetaPayload += principal_id: str | None = None
src/loopplane/checkpoint/base.py      # SessionSummary  += principal_id: str | None = None
src/loopplane/checkpoint/file.py      # list_sessions reads meta.payload.principal_id
src/loopplane/checkpoint/sqlite.py    # list_sessions reads meta.payload.principal_id
src/loopplane/checkpoint/recorder.py  # SessionRecorder += principal_id → SessionMetaPayload
src/loopplane/controller/controller.py# _Session += principal_id; create_session/_assemble += principal_id; in-memory list_sessions includes it
src/loopplane/host/host.py            # run()/session() += principal_id → controller.create_session

tests/
├── contract/    # extend: principal_id checkpoint round-trip (both backends)
└── integration/ # NEW test_webapi_principal_scoping.py — two-principal scoping, restart, default-deny, no-leak
```

Edited (docs / drift):

```text
docs/api-reference.md                # webapi section: + Principal (+ token_authenticator)
CHANGELOG.md                         # + a 022 entry; note the auth return-type breaking change
docs/loopplane-agent-board.md        # + the 022 row + audit; refresh §4 Active Feature
```

**Structure Decision**: The security change is confined to `loopplane.webapi`. Durable
ownership reuses the unit-021 checkpoint seam by adding **one optional metadata field**
(`principal_id`, default `None`) that threads `host.run/session → controller.create_session
→ _assemble → SessionRecorder → SessionMetaPayload`, and is read back through
`SessionSummary.principal_id` by both checkpoint backends. `controller.resume` is **not**
changed — the owner is already on the durable meta, and the web/API gates resume by
checking the listed owner first. The runtime loop, gateway, and event bus are untouched;
with `principal_id` unset every existing path is byte-identical.

## Phases

- **Phase 0 — Research** (`research.md`): identity-bearing verifier shape (`→ Principal | None`)
  and the FastAPI per-route `Depends(Principal)` injection; the reference token→principal
  verifier; **404-not-403** for non-owners (no existence leak); live vs. durable ownership
  (web/API registry owner + checkpoint `principal_id`); why `resume` needs no change; the
  additive optional-field plumbing and its zero-behavior-change invariant; the breaking
  return-type change + drift obligation.
- **Phase 1 — Design** (`data-model.md`, `contracts/`, `quickstart.md`): `Principal`,
  `Authenticator`, the reference verifier; `SessionEntry.owner`; the `principal_id`
  metadata field and its flow; the auth-principal contract and the session-ownership
  boundary; a quickstart driving two principals.
- **Phase 2 — Tasks** (`/speckit.tasks`): TDD — write the two-principal scoping +
  default-deny + restart + no-leak tests first (FAIL), then the `Principal`/verifier, then
  the additive `principal_id` plumbing, then the ownership enforcement in `app.py`, then
  api-reference/changelog/board; run all gates.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*
