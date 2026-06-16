# Research: Web Principal Authentication & Per-Principal Session Scoping (unit 022)

Phase 0 decisions. Backend only; additive, fail-safe, no new dependency.

## R1 — Identity-bearing verifier shape

- **Decision**: `Authenticator = Callable[[str | None], Awaitable[Principal | None]]`;
  the verifier maps the credential to a `Principal` or returns `None` to deny.
  `Principal` is a small frozen value with an opaque `id`. `DENY_ALL` returns `None`.
- **Rationale**: The current boolean admits/denies but cannot identify the caller, so
  ownership is impossible. Returning the principal is the minimal change that yields
  identity while preserving the pluggable, embedder-injected seam.
- **Alternatives**: a separate "who am I" call alongside the bool — rejected (two seams,
  racy); a request-scoped context global — rejected (implicit, harder to test).

## R2 — FastAPI injection of the principal

- **Decision**: `make_auth_dependency(auth)` returns a dependency that **resolves a
  `Principal`** (raising `401` on `None`/raise), and each route declares
  `principal: Principal = Depends(require)`. Replace the router-level
  `dependencies=[Depends(...)]` (whose return value is discarded) with the per-route
  parameter dependency so handlers receive the identity **and** are still gated.
- **Rationale**: A router-level dependency cannot inject a value into handlers; a
  per-route `Depends` both authenticates and hands the route the principal.

## R3 — Reference authenticator (host ships no credential store)

- **Decision**: ship `token_authenticator(tokens: Mapping[str, str]) -> Authenticator`
  that reads a `Bearer <token>` authorization value and maps the token to
  `Principal(id=...)` via the supplied `{token: principal_id}` mapping; unknown/missing →
  `None`. For dev/demo/tests only; real deployments inject their own (OAuth/JWT/etc.).
- **Rationale**: Keeps Constitution VII — the host stores no credentials; the mapping is
  injected by the embedder. The frontend already sends a bearer credential.

## R4 — 404, not 403, for non-owners

- **Decision**: every per-session route returns **404 not-found** when the session is not
  owned by the caller — never a 403 that confirms the session exists.
- **Rationale**: A distinguishable 403 leaks the existence (and ids) of other principals'
  sessions. 404 reveals nothing (FR-007, Constitution VII).

## R5 — Live vs. durable ownership

- **Decision**: two complementary records of ownership:
  - **Live**: `SessionEntry.owner` in the web/API session registry — for the interactive
    routes (events/submit/approvals/questions/cancel) held in the lifespan task group.
  - **Durable**: `SessionMetaPayload.principal_id` in the checkpoint metadata — surfaced
    on `SessionSummary.principal_id`, so the listing and the resume/history/artifact gates
    can scope sessions that outlive the process.
- **Rationale**: The interactive registry is in-memory and ephemeral; durable scoping
  (US2) needs the owner on disk, which is exactly the unit-021 seam (FR-008).

## R6 — `resume` needs no controller change

- **Decision**: `controller.resume` is **unchanged**. The owner is already on the durable
  meta (written at creation); the web/API checks the **listed** owner
  (`host.list_sessions()[…].principal_id`) before calling `resume`, so a non-owner is
  rejected at the boundary and never reaches the controller.
- **Rationale**: Minimizes the runtime footprint; ownership is enforced at the transport,
  and re-reading the meta in resume would be redundant.

## R7 — Additive, optional plumbing (zero behavior change)

- **Decision**: `principal_id` is added as `str | None = None` to `SessionMetaPayload`,
  `SessionSummary`, `SessionRecorder`, `controller.create_session`/`_assemble`/`_Session`,
  and `host.run`/`host.session`. Every default is `None`.
- **Rationale**: With `principal_id` unset, the serialized records, the listings, and the
  runtime paths are byte-identical — existing tests and embedders are unaffected. Only the
  web/API, which now supplies an owner, exercises the field.

## R8 — Breaking change + drift obligation

- **Decision**: the `Authenticator` return-type change (`bool → Principal | None`) is a
  **breaking change** to unit 011's web/API auth surface; record it in `CHANGELOG.md`.
  Add `Principal` (and the reference `token_authenticator`) to `webapi.__all__` and the
  matching `docs/api-reference.md` section (unit-014 drift contract).
- **Rationale**: 011 is a later-phase contract (not 001/002), so evolving it is allowed,
  but it must be announced and kept drift-free.

## R9 — Out of scope (confirmed)

- Login UI + browser E2E (`apps/web`) → unit 023. Concurrent multi-user execution (a host
  per principal) — the single sequential host is unchanged. Roles/permissions, password
  storage, token issuance/rotation, and a specific IdP — embedder's verifier owns these.
  Ownerless legacy durable sessions are listed to no one (safe default).
