# Feature Specification: PostgreSQL Checkpoint Backend

**Feature Branch**: `060-postgres-checkpoint`

**Created**: 2026-06-20

**Status**: Draft — **plan STOPs to consult the maintainer (sync/async FORK) + authors an ADR**

**Input**: User description: "A PostgreSQL CheckpointStore backend (gap G19): a third durable session-record store implementing the EXISTING CheckpointStore protocol and reusing the shared record encoding (records.py), behind a new optional `loopplane[postgres]` extra; File + SQLite remain the default (byte-identical when Postgres is not configured). Unit 060, Tier-4. An ADR + a maintainer FORK at plan: sync thread-bridge (recommended — the sync Protocol + call sites stay unchanged) vs an async-Protocol rewrite."

## ⚠️ Boundary note (read first)

The checkpoint layer is a Protocol (`CheckpointStore`, base.py:26) with two backends today — `File`
and `SQLite` — both reusing `records.py` (`serialize_record`/`deserialize_record`) over the same
record shape `(session_id, sequence, recorded_at, data)`. This unit adds a **third backend** behind
the SAME Protocol, host-selected, behind a new import-guarded `loopplane[postgres]` extra; the
default stays File/SQLite (byte-identical). The **FORK is a maintainer consult at plan** — (A) a
**sync thread-bridge** (psycopg run via `anyio.to_thread`; the existing sync Protocol + all call
sites unchanged) vs (B) an **async-Protocol rewrite** (a larger, contract-changing path). An **ADR**
records the chosen model. No runtime/loop/gateway/event change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sessions persist to PostgreSQL (Priority: P1)

An embedder running multiple processes / needing a networked store configures a Postgres checkpoint
backend; sessions append + load + list + delete exactly like the File/SQLite backends, durably in
Postgres.

**Why this priority**: This is gap G19 — the runtime today persists only to a local File or SQLite
store; a networked/shared DB is needed for multi-process / durable deployments.

**Independent Test**: against a Postgres (or a faithful stub), the backend round-trips records
(append → load preserves order + content), lists sessions, sets a title, and deletes a session —
mirroring the existing SQLite backend's contract test.

**Acceptance Scenarios**:

1. **Given** a Postgres backend, **When** records are appended for a session, **Then** `load` returns
   them ordered by `sequence` with content preserved (reusing `records.py`).
2. **Given** a Postgres backend, **When** `list_sessions` / `set_title` / `delete_session` are called,
   **Then** they behave exactly like the SQLite backend (same Protocol contract).

---

### User Story 2 - Default-unchanged + import-guarded (Priority: P1)

With no Postgres configured the runtime uses File/SQLite exactly as today; the new `psycopg`
dependency is behind an optional `loopplane[postgres]` extra (base + non-postgres installs
unaffected).

**Why this priority**: The new backend must impose nothing on existing deployments + must not add a
hard dependency.

**Independent Test**: the default backend selection + the existing checkpoint tests are unchanged;
the Postgres backend is importable only with the extra.

**Acceptance Scenarios**:

1. **Given** no Postgres config, **When** the runtime checkpoints, **Then** behavior is byte-identical
   to today (File/SQLite); the existing checkpoint suite passes unchanged.
2. **Given** the base install (no `postgres` extra), **When** the package is imported, **Then** it
   works (the Postgres backend's `psycopg` import is guarded).

---

### User Story 3 - Same Protocol, same contract (Priority: P2)

The Postgres backend satisfies the EXISTING `CheckpointStore` Protocol — same method shapes
(`append`/`load`/`list_sessions`/`set_title`/`delete_session`), same record encoding, same
corrupt-row tolerance — so it is a drop-in choice.

**Why this priority**: The value is a drop-in third backend, not a new contract; the chosen
sync/async model (the plan FORK) must keep (or, if async, deliberately change) the Protocol.

**Independent Test**: the Postgres backend passes the SAME contract assertions as the SQLite backend
(a shared/parametrized contract test).

**Acceptance Scenarios**:

1. **Given** the Postgres backend, **When** exercised against the `CheckpointStore` contract, **Then**
   it matches the SQLite backend's behavior (round-trip, ordering, corrupt-row skip).
2. **Given** the chosen model, **When** the Protocol + call sites are inspected, **Then** the
   recommended sync thread-bridge keeps them unchanged (or, if async is chosen, the ADR records the
   contract change).

---

### Edge Cases

- **no Postgres configured (default)**: File/SQLite, byte-identical.
- **base install without the extra**: the package imports; the Postgres backend errors clearly only
  when constructed without `psycopg`.
- **corrupt/garbage row**: skipped (mirroring the SQLite backend's tolerance), reported in the
  problems list.
- **concurrent appends to one session**: serialized (mirroring the SQLite per-session lock posture)
  / relies on the PK `(session_id, sequence)`.
- **no live DB in CI**: tests skip or use a faithful stub — the suite never requires a running
  Postgres.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide a `PostgresCheckpointStore` that satisfies the EXISTING `CheckpointStore`
  Protocol (`append`/`load`/`list_sessions`/`set_title`/`delete_session`), reusing `records.py`
  (`serialize_record`/`deserialize_record`) over the same `(session_id, sequence, recorded_at,
  data)` record shape (PK `(session_id, sequence)`), mirroring the SQLite backend.
- **FR-002**: The backend MUST be **host-selected** + behind a NEW **import-guarded
  `loopplane[postgres]` extra** (`psycopg[binary]>=3`); the **default backend stays File/SQLite**
  (byte-identical when Postgres is not configured); the base install is unaffected.
- **FR-003**: The backend MUST match the SQLite backend's **contract behavior** — round-trip +
  ordering by `sequence` + corrupt-row tolerance (skipped + reported) + per-session append
  serialization.
- **FR-004**: The implementation MUST follow the **maintainer FORK decided at plan**: (A) sync
  thread-bridge (psycopg via `anyio.to_thread`; the existing sync `CheckpointStore` Protocol + all
  call sites UNCHANGED — recommended/byte-identical), or (B) an async-Protocol rewrite (the ADR
  records the contract change). An **ADR** records the decision.
- **FR-005**: The feature MUST be **additive** — no runtime/loop/gateway/event-schema/content change;
  no change to the File/SQLite backends beyond what the chosen model requires.
- **FR-006**: Tests MUST be **offline-safe** — they skip when no Postgres is available, or use a
  faithful stub/fake; the suite MUST NOT require a running database.

### Key Entities *(include if feature involves data)*

- **PostgresCheckpointStore**: the 3rd `CheckpointStore` backend; a `records` table
  `(session_id, sequence, recorded_at, data, PK(session_id, sequence))`; psycopg connection.
- **`loopplane[postgres]` extra**: `psycopg[binary]>=3` (import-guarded).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Postgres backend round-trips records (append→load ordered + content-preserved),
  lists/titles/deletes, and tolerates corrupt rows — matching the SQLite backend in 100% of the
  shared contract scenarios.
- **SC-002**: With no Postgres configured, behavior is byte-identical to today (File/SQLite); the
  base install + the existing checkpoint suite pass unchanged; the new dependency is import-guarded.
- **SC-003**: The chosen model is recorded in an ADR; the recommended sync thread-bridge leaves the
  `CheckpointStore` Protocol + call sites unchanged. No runtime/event change.

## Assumptions

- Mirrors `SqliteCheckpointStore` (same Protocol, same `records.py`, same table shape, same
  corrupt-row tolerance + per-session serialization). The **recommended FORK = sync thread-bridge**:
  psycopg (sync) wrapped in `anyio.to_thread.run_sync` for the async Protocol methods
  (`append`/`set_title`); the sync methods (`load`/`list_sessions`/`delete_session`) call psycopg
  directly — the Protocol + all call sites stay unchanged/byte-identical.
- The host wires the Postgres backend (a DSN/connection) where it selects File/SQLite today; default
  unchanged.
- **Out of scope / DEFERRED**: G22 Phase C (the per-user-monthly USD ledger — a separate durable
  store); connection pooling/migrations tooling beyond table creation; multi-tenant concurrency
  (G20, unit 061) — this is purely the storage backend.
- Additive; default-unchanged byte-identical; offline-testable; public-safe (a DSN/credential is
  host config, never echoed). The plan authors the ADR. Per Constitution IX the concept is borrowed
  but re-derived against this Protocol.
