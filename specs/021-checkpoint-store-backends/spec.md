# Feature Specification: Checkpoint Store Backends

**Feature Branch**: `021-checkpoint-store-backends` (main-only autopilot; no dedicated branch)

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Gap-closure Phase B (unit 021): turn the checkpoint store from a single concrete filesystem class into an interface with two interchangeable implementations — the existing filesystem store (kept as the default, unchanged) and a new optional SQLite store that proves the seam is real. The database backend is supported, not required; the runtime core and all existing contracts are unchanged. Multi-user/`principal_id` and any networked database (Postgres) are deferred to Phase C; the SQLite store uses only the Python standard library so there is no new runtime dependency and it runs fully offline."

## Overview

The runtime persists each session's history through a single durable seam — the
**checkpoint store** — which today exists only as one concrete filesystem class. The
runtime controller, the recorder, and host assembly all reach for that one class, so
there is **no seam to provide durable storage any other way** without editing the
runtime. Constitution Principle IV names Checkpoint as a runtime component that must
have a clear, documented boundary; right now that boundary is an implementation, not an
interface.

This unit extracts the checkpoint store into an **interface** with exactly its current
public surface (durable append, ordered load with problem reporting, session listing)
and provides **two interchangeable implementations** behind it: the existing
**filesystem store**, retained as the **default with unchanged behavior**, and a new
**SQLite store** that proves the seam is real. The database backend is **supported, not
required** — an embedder who does not opt in sees no change, no new dependency, and the
same default gates. The SQLite store reuses the existing record encoding and
corrupt-record handling, uses only the Python standard library (so it adds no
third-party runtime dependency and runs entirely offline), and is selected through an
additive, defaulted host-configuration choice. Multi-user scoping and any networked
database (e.g., Postgres) are explicitly **out of scope**, reserved for the later
multi-user phase; this unit keeps the interface single-tenant, keyed by session.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a durable backend behind one interface (Priority: P1)

A host developer configures the runtime to persist sessions through either the
filesystem store (the default) or the SQLite store, and the runtime appends, resumes,
and lists sessions **identically through whichever backend is selected** — with no
change to the runtime core.

**Why this priority**: An interface with two interchangeable, behavior-equivalent
backends is the entire point of the unit; it proves the checkpoint boundary is a real
seam and unblocks the later database-backed, multi-user phase.

**Independent Test**: Run one shared contract suite against both implementations and
assert, **parameterized over both backends**, that append-then-load returns the records
in order and that session listing reports the same identity and recency ordering.

**Acceptance Scenarios**:

1. **Given** a runtime configured with the SQLite store, **When** a session records history and is then loaded, **Then** the records come back in append order and a subsequent run can resume from them.
2. **Given** the same session activity recorded against each backend in turn, **When** each store is loaded and listed, **Then** the reconstructed records and the listed identity/recency ordering are equivalent.

### User Story 2 - Existing deployments are unaffected (Priority: P2)

An embedder who does not opt into another backend keeps the filesystem store with
**byte-identical behavior**, **no configuration change**, and **no new runtime
dependency**.

**Why this priority**: The abstraction must do no harm; extracting an interface and
adding a backend is only acceptable if every existing user is unchanged by default
(Constitution X — incremental, reversible evolution).

**Independent Test**: Build the runtime from the default configuration and assert it
still constructs the filesystem store; run the pre-existing filesystem checkpoint
behavior unchanged; confirm the core install adds no new dependency.

**Acceptance Scenarios**:

1. **Given** the default host configuration, **When** the runtime is assembled with durable storage, **Then** it uses the filesystem store and the existing checkpoint behavior is unchanged.
2. **Given** no durable storage configured, **When** the runtime runs, **Then** the no-store path behaves exactly as before.

### User Story 3 - Corrupt or missing data degrades safely in both backends (Priority: P3)

Both backends survive corrupt or partial data the same way: a single unreadable record
is skipped and reported without failing the whole load, and a missing/never-written
store lists as empty rather than erroring.

**Why this priority**: Resilience parity is what makes the two backends truly
interchangeable; a backend that crashes on a bad record or a missing store is not a
drop-in replacement.

**Independent Test**: Seed each backend with a corrupt record among good ones and assert
load returns the good records plus a reported problem; point each backend at a missing
store and assert an empty listing.

**Acceptance Scenarios**:

1. **Given** a session whose stored stream contains one corrupt record, **When** it is loaded, **Then** the good records load and the corrupt one is reported as a skipped problem — for both backends.
2. **Given** a store that was never written, **When** sessions are listed, **Then** the result is empty and no error is raised — for both backends.

### Edge Cases

- **Append durability**: an append MUST be durably persisted before the producing operation returns, so a crash immediately after does not lose the record — for both backends.
- **Recency derivation differs by backend**: the SQLite store derives "last active" from the latest stored record (it has no filesystem timestamp); both backends MUST still order most-recent-first.
- **Mixed/legacy data**: existing on-disk filesystem sessions are read by the filesystem store as before; this unit does **not** migrate them into SQLite (backend choice applies to sessions created under that configuration).
- **Empty session / metadata-only session**: listing and loading behave consistently across backends when a session has only its metadata record.
- **Unset or default backend selector**: resolves to the filesystem store; the runtime never silently requires a database.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The checkpoint store MUST be defined as an **interface** carrying exactly the existing public surface — durable append of a record, ordered load returning the records together with a list of reported problems, and a session listing — so durable storage can be supplied by more than one implementation without changing the runtime core or any existing public contract.
- **FR-002**: The unit MUST provide **two interchangeable implementations** of that interface: the existing **filesystem store** (retained, behavior unchanged) and a new **SQLite store**.
- **FR-003**: The filesystem store MUST remain the **default** and MUST preserve its current behavior exactly; an embedder who does not opt into another backend observes no change.
- **FR-004**: Selecting the SQLite backend MUST be an **additive, defaulted** host-configuration choice; when it is unset the filesystem store (or no store) is used and behavior is unchanged.
- **FR-005**: The SQLite store MUST add **no new third-party runtime dependency** and MUST operate **fully offline** (no network, no external service), so default and CI runs need no extra setup.
- **FR-006**: Both implementations MUST exhibit the **same observable persistence semantics**: durable append (persisted before the operation returns), ordered reconstruction of a session's records, skipping and reporting a corrupt/unreadable record without failing the whole load, and an empty listing for a missing/never-written store.
- **FR-007**: Session listing MUST report identity and recency **ordered most-recent-first** from both backends; the recency signal MAY be derived differently (the SQLite store uses the latest stored record rather than a filesystem timestamp), but both MUST represent most-recent activity and order correctly.
- **FR-008**: The runtime consumers (controller, recorder, host assembly) MUST depend **only on the interface**, and the interface's method signatures MUST be **unchanged** so existing call sites are unaffected.
- **FR-009**: The change MUST be **public-safe** (Constitution VII) and MUST keep the public API reference in sync with the checkpoint package's public surface (the interface plus the two named implementations); the changelog MUST record the unit.
- **FR-010**: Multi-user / per-principal scoping and any networked database backend (e.g., Postgres) MUST be **out of scope**; the interface remains **single-tenant, keyed by session**.

### Key Entities

- **Checkpoint store interface**: the durable session-record boundary the runtime depends on — durable append, ordered load (records + reported problems), and session listing.
- **Filesystem checkpoint store**: the existing default implementation, persisting append-only records per session under a base directory.
- **SQLite checkpoint store**: the new optional implementation, persisting the same records in a local SQLite database, reusing the shared record encoding and corrupt-record handling.
- **Session summary**: the identity-and-recency view returned by listing (session identity, label, created-at, last-active-at).
- **Backend selector**: the additive, defaulted host configuration that picks which store the runtime assembles (default = filesystem).

### Out of Scope

- Multi-user / per-principal scoping and a `principal_id` on the interface — reserved for the later multi-user phase.
- Any networked or remote database backend (e.g., Postgres) — a later optional implementation of the same interface.
- Migrating existing on-disk filesystem sessions into SQLite (no data migration; backend choice applies to sessions created under that configuration).
- Changing the record schema/encoding, the runtime event bus, or the loop/controller/recorder contracts.
- Concurrency beyond the existing per-session serialization model (no multi-process writers, no connection pooling).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One shared contract test suite passes against **both** backends — append/load ordering, corrupt-record skipping, missing-store → empty listing, and recency-ordered listing.
- **SC-002**: With **no configuration change**, an existing embedder's checkpoint behavior is identical and **no new dependency** is introduced; the core install and the default gates are unchanged.
- **SC-003**: A host switches to the SQLite backend with a **single configuration value** and durably persists and resumes a session through it, with **no runtime code change**.
- **SC-004**: The full quality gate stays green (format, lint, strict types, tests, offline build) with the SQLite backend running **entirely offline**.
- **SC-005**: The public API reference matches the checkpoint package's public surface after the change (interface + both implementations), and the public-safety scan is clean.

## Assumptions

- **Shared record semantics**: the SQLite store reuses the existing record encoding and corrupt-record handling, so both backends share record semantics rather than defining a second format.
- **Recency derivation**: "last active" for the SQLite store derives from the latest stored record's timestamp (no filesystem mtime); both backends represent most-recent activity.
- **No migration**: existing filesystem sessions are not migrated into SQLite; backend choice applies to sessions created under that configuration.
- **Single-tenant interface**: the interface stays keyed by session; multi-user/per-principal scoping arrives in a later unit alongside authentication.
- **Standard-library SQLite**: the SQLite store uses the language's standard-library database support, so it adds no third-party runtime dependency and needs no external service.
- **Additive, reversible**: the unit is additive (an extracted interface, a renamed existing default, and one new optional backend); reverting restores the single filesystem class and removes the SQLite store (Constitution X rollback).
