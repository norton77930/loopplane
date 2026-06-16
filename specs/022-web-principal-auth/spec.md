# Feature Specification: Web Principal Authentication & Per-Principal Session Scoping

**Feature Branch**: `022-web-principal-auth` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Gap-closure Phase C, backend only (unit 022): the web/API host authenticates with an identity-less boolean — it admits/denies a request but never identifies the caller, so sessions have no owner and any authenticated request can reach any session. Make authentication identity-bearing (return a principal instead of a bool, keeping the pluggable default-deny seam), scope every session operation to the principal that owns it (a non-owner gets a not-found, never another principal's data), and record the owner in the durable checkpoint metadata so scoping survives restarts (the `principal_id` deferred from unit 021). The single sequential host is unchanged — this is ownership scoping, not concurrent multi-user execution. The login UI and end-to-end browser flow are deferred to unit 023."

## Overview

The web/API host (unit 011) authenticates with an **identity-less boolean**: its
`Authenticator` admits or denies a request but never says *who* the caller is. As a
result **sessions have no owner** — the session listing returns every session, and every
per-session route accepts any session id from any authenticated caller. One
authenticated client can read, drive, resume, or fetch artifacts for **another client's**
session. This blocks LoopPlane from safely serving more than one principal.

This unit makes authentication **identity-bearing** and scopes every session operation to
its owner. The pluggable, fail-safe, **default-deny** boundary is kept, but the verifier
now returns a **principal identity** (or denies). The principal that opens a session
**owns** it; the listing returns only the caller's own sessions, and every per-session
route returns a **not-found** result for a session the caller does not own (existence is
never revealed). The owner is recorded in the session's **durable checkpoint metadata**
(the `principal_id` seam deferred from unit 021), so listing and resume stay scoped per
principal **across restarts**, not just for in-memory sessions. The host ships **no
credential store**; a single **reference authenticator** maps a configured token→principal
mapping for development and tests, and embedders may inject their own verifier
(OAuth/JWT/etc.). This is **backend only** and is **ownership scoping, not concurrent
execution** — the single sequential host is unchanged; the login UI and browser
end-to-end flow are deferred to unit 023.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A principal sees and drives only their own sessions (Priority: P1)

An authenticated caller opens sessions, lists them, and drives them. The listing and
every per-session route are **scoped to the caller**: a session owned by a different
principal is invisible in the listing and returns a not-found result on direct access.

**Why this priority**: Per-principal ownership scoping is the entire point of the unit;
without it the host cannot serve more than one user safely.

**Independent Test**: With two principals, each opens a session; assert each lists only
its own session and that either principal's direct access to the other's session id is a
not-found result (no data, no existence signal).

**Acceptance Scenarios**:

1. **Given** two authenticated principals A and B who have each opened a session, **When** A lists sessions, **Then** A sees only A's session and not B's.
2. **Given** A's session id, **When** B requests that session's history / events / submit / resume / artifacts, **Then** B receives a not-found result that reveals no data and no existence.
3. **Given** A's own session id, **When** A drives or inspects it, **Then** A succeeds as before.

### User Story 2 - Ownership survives a restart (Priority: P2)

A session's owner is recorded in its durable record metadata, so after the host restarts,
listing and resume remain scoped to the owning principal.

**Why this priority**: Durable per-principal scoping is what makes the feature real for a
running product; in-memory-only ownership would leak every session after a restart.

**Independent Test**: Principal A opens and persists a session; restart the host over the
same storage; assert A can list and resume the session and B cannot.

**Acceptance Scenarios**:

1. **Given** a durable session owned by A, **When** the host restarts over the same storage, **Then** A's listing includes it and a resume by A succeeds.
2. **Given** the same restarted host, **When** B lists or tries to resume A's session, **Then** it is excluded from B's listing and a resume attempt is a not-found result.

### User Story 3 - Default-deny and public-safety hold (Priority: P3)

With no authenticator injected, every request is denied. A verifier that raises denies.
No credential or principal value ever appears in a response or error.

**Why this priority**: The boundary's safety posture (Constitution VII) must be preserved
while it gains identity; a regression here is a security defect.

**Independent Test**: Run with no authenticator and assert every route denies; inject a
raising verifier and assert denial; inspect denied and successful responses for any
credential or principal leakage.

**Acceptance Scenarios**:

1. **Given** no authenticator, **When** any route is requested, **Then** it is denied with a fixed unauthorized result that never echoes the credential.
2. **Given** a verifier that raises, **When** a request is verified, **Then** the request is denied (fail-safe), not admitted.
3. **Given** any response or error, **When** it is inspected, **Then** it contains no credential and no principal token.

### Edge Cases

- **Missing or invalid credential** → denied (default-deny), credential never echoed.
- **Authenticated caller, another principal's session** → a not-found result (existence not revealed), never a "forbidden" that confirms the session exists.
- **Verifier raises** → denied (fail-safe), consistent with the current boundary.
- **Ownerless legacy durable session** (recorded before this unit) → owned by no principal, so it is **not listed to anyone** and not resumable through the scoped routes (no silent global visibility); it remains on disk untouched.
- **One principal, many sessions** → all of that principal's sessions are listed to them.
- **Concurrent open while a run is active** → the existing single-sequential-host conflict result is unchanged (this unit does not add concurrent execution).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The authentication boundary MUST **identify the caller**: the verifier maps the request credential to a **principal identity**, or denies. (It no longer returns a bare allow/deny.)
- **FR-002**: A **principal** MUST carry an opaque identifier sufficient to scope ownership; this unit defines **no roles or permissions** beyond ownership.
- **FR-003**: The boundary MUST remain **default-deny and fail-safe**: with no authenticator injected every request is denied; a verifier that raises denies; the denial is a fixed unauthorized result that **never echoes the credential**.
- **FR-004**: A single **reference authenticator** MUST be provided that maps a configured token→principal mapping (for development and tests); the host MUST ship **no credential store**, and embedders MUST be able to inject their own verifier.
- **FR-005**: The principal that opens a session **owns** it; ownership MUST be established at the boundary and **never trusted from the client**.
- **FR-006**: The session **listing** MUST return only the **caller's own** sessions.
- **FR-007**: Every **per-session operation** (events, submit, approvals, questions, cancel, history, resume, artifacts) MUST return a **not-found** result when the session is not owned by the caller — it MUST NOT reveal the session's existence (i.e., not-found, not a distinguishable "forbidden").
- **FR-008**: A session's **owner MUST be recorded in its durable record metadata** so listing and resume stay scoped per principal **across restarts**, reusing the unit-021 checkpoint seam (the deferred `principal_id`).
- **FR-009**: No **credential**, **principal token**, or internal detail MUST leak in any response or error; responses stay **metadata-only** (Constitution VII).
- **FR-010**: The **runtime core, loop, gateway, and event bus MUST be unchanged**; the change is confined to the web/API auth boundary, the web/API session registry/ownership, and the owner field on the checkpoint/session metadata. **No new runtime dependency.**
- **FR-011**: The public API reference and the package's public surface MUST stay in sync (the web/API package gains the **principal** type); the changelog MUST record the unit; the verifier's **return-type change** (allow/deny → principal) MUST be noted as a **breaking change** to the unit-011 web/API auth surface.

### Key Entities

- **Principal**: an authenticated caller's identity — an opaque identifier that is the unit of ownership and scoping. No roles/permissions in this unit.
- **Authenticator (verifier)**: the pluggable boundary that maps a request credential to a principal (or denies). Default-deny, fail-safe, embedder-injected; one reference token→principal implementation ships.
- **Session ownership**: the association of a session — live and durable — with the principal that opened it; enforced at the boundary for listing and every per-session route.
- **Durable owner metadata**: the owner identifier recorded in the session's checkpoint metadata so scoping survives a restart.

### Out of Scope

- The **login UI** and the end-to-end browser flow in the web frontend — deferred to **unit 023** (the frontend already sends a bearer credential; a screen to obtain/set it is the next unit).
- **Concurrent multi-user execution** (a host per principal): the web/API host stays **single and sequential**; this unit adds **ownership scoping, not concurrency**.
- **Roles, permissions, or authorization** beyond simple ownership.
- **Credential/password storage, token issuance, rotation, or refresh**, and integration with a specific external identity provider — embedders supply their own verifier.
- **Migrating** pre-existing ownerless durable sessions to an owner (they are treated as owned by no principal and are simply not listed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An authenticated caller can open, list, and drive only the sessions **they own**.
- **SC-002**: A second principal **cannot see** (the listing excludes them) or **touch** (direct access returns a not-found result) the first principal's sessions.
- **SC-003**: Durable sessions remain scoped to their owner **across a restart** — the owner lists and resumes them; another principal cannot.
- **SC-004**: With **no authenticator**, every request is denied, and **no credential or principal value** appears in any response or error.
- **SC-005**: The full quality gate stays green with **no new runtime dependency**, and the runtime core is **unchanged**.

## Assumptions

- **Bearer credential**: the credential is the request's authorization value (typically a bearer token); the reference authenticator maps tokens to principals; real deployments inject their own verifier.
- **Ownership, not concurrency**: scoping is about visibility/access; the existing single-active-run behavior of the host is unchanged.
- **Ownerless legacy sessions**: durable sessions recorded before this unit have no owner and are **not listed to any principal** (a safe default — no silent global visibility); they are left on disk.
- **Checkpoint seam reused**: the owner travels in the session's checkpoint metadata (unit 021); no new storage backend is introduced.
- **Additive, reversible**: the change is confined to the web/API auth boundary, web/API session ownership, and one owner metadata field; reverting restores the identity-less boundary (Constitution X rollback).
