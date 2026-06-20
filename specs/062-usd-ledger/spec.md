# Feature Specification: Durable USD Ledger

**Feature Branch**: `062-usd-ledger`

**Created**: 2026-06-21

**Status**: Draft — **plan authors ADR 0010 (covers 062+063; all forks settled at design)**

**Input**: User description: "G22 Phase C (1/2): a NEW `loopplane.ledger` package — a durable per-user-monthly USD ledger. A `UsdLedger` Protocol keyed by `(principal_id, month)` with an ATOMIC cross-session increment that returns the new running total, plus File/SQLite/Postgres backends mirroring the 060 checkpoint store. The store ALONE (no enforcement — that is unit 063). Settled forks: separate package (not CheckpointStore); File+SQLite+Postgres; Postgres-only cross-process atomicity; exact Decimal."

## ⚠️ Boundary note (read first)

This is the durable **store half** of G22 Phase C (the per-user-monthly USD ledger deferred by ADR
0005 D7). It is a **NEW `loopplane.ledger` package** — a sibling to `loopplane.checkpoint` /
`loopplane.budget`, **not** new methods on `CheckpointStore` (which is append-only + session-keyed —
the wrong shape for an atomic `(principal_id, month)` counter). It mirrors 060's three-backend
pattern (File/SQLite/Postgres) + reuses ADR 0008's sync thread-bridge + the existing
`loopplane[postgres]` extra (no new dependency). It is **pure storage — no enforcement, no loop /
budget / event change** (enforcement is unit 063). The plan authors **ADR 0010** (covering 062+063;
the four forks are settled at design). **Atomicity is uneven by design**: cross-PROCESS safety holds
only on Postgres; SQLite/File are single-process-honest — the spec states this plainly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accumulate a principal's monthly USD durably (Priority: P1)

A host records each run's USD cost against `(principal_id, month)` in a durable ledger and reads back
the running monthly total — the durable, cross-session counterpart of 055's in-memory per-session
spend, on which a per-user-monthly cap (unit 063) will be enforced.

**Why this priority**: This is the durable foundation of G22 Phase C (G22's last remaining piece); a
monthly cap needs a durable cross-session accumulator that 055's in-memory per-session checker is not.

**Independent Test** (offline, no running DB): `add(p, "2026-06", Decimal("0.10"))` then
`add(p, "2026-06", Decimal("0.05"))` → the second `add` returns `Decimal("0.15")`; `get(p, "2026-06")`
== `0.15`; `get` of an unseen `(p, month)` == `Decimal(0)`.

**Acceptance Scenarios**:

1. **Given** a ledger, **When** USD is added to `(principal_id, month)` repeatedly, **Then** each
   `add` returns the exact NEW post-increment total and `get` reflects the accumulated sum.
2. **Given** a ledger, **When** `get` is called for an unseen `(principal_id, month)`, **Then** it
   returns `Decimal(0)` (no error).

---

### User Story 2 - Atomic increment, no lost updates (Priority: P1)

Concurrent `add`s to the same `(principal_id, month)` — now real because 061's TenantHostPool allows
same-principal concurrency — never lose an increment; the total is the exact sum of all adds.

**Why this priority**: Atomicity IS the point of the ledger. Without it, concurrent runs for one user
would silently under-count, defeating the monthly cap.

**Independent Test**: N concurrent `add`s of the same amount to one key → the final `get` equals N ×
the amount exactly (no lost update), on the SQLite + File backends (in-process) and asserted for the
Postgres backend's atomic-upsert SQL.

**Acceptance Scenarios**:

1. **Given** a backend, **When** many `add`s hit the same `(principal_id, month)` concurrently,
   **Then** the accumulated total equals the exact sum (no lost increment).
2. **Given** the Postgres backend, **When** it adds, **Then** it uses a single atomic
   `INSERT … ON CONFLICT … DO UPDATE … RETURNING` (the only cross-PROCESS-safe path); SQLite/File are
   single-process-honest (an in-process per-`(principal,month)` lock) — documented.

---

### User Story 3 - Exact money + three backends, byte-identical when unused (Priority: P2)

USD is exact `Decimal` end-to-end (never float, which would corrupt money); the ledger ships File
(default/offline), SQLite, and Postgres backends mirroring the checkpoint store; the package adds
nothing to the runtime until a host wires it (unit 063).

**Why this priority**: Money precision is non-negotiable; the three-backend parity matches the
existing storage seam; and the store must impose nothing on its own.

**Independent Test**: a large + fractional accumulation has no float drift (exact Decimal); each
backend passes the same shared contract; importing the base package needs no `postgres` extra.

**Acceptance Scenarios**:

1. **Given** any backend, **When** large/fractional USD is accumulated, **Then** the total is exact
   (Decimal; TEXT for SQLite/File, NUMERIC for Postgres — no float).
2. **Given** the base install (no `postgres` extra), **When** `loopplane.ledger` is imported, **Then**
   it works (the Postgres backend's `psycopg` import is guarded); File/SQLite need no extra.

---

### Edge Cases

- **unseen key**: `get` → `Decimal(0)`; `add` creates the row.
- **concurrent same-key adds**: serialized/atomic → no lost update (per-backend story).
- **cross-process**: only Postgres is atomic across OS processes; SQLite/File are
  single-process-honest (documented) — not a silent guarantee.
- **large/fractional money**: exact Decimal, no float drift.
- **base install without the `postgres` extra**: the package imports; the Postgres backend errors
  clearly only when constructed without `psycopg`.
- **corrupt/garbage stored value**: handled defensively (skip/raise clearly), mirroring the checkpoint
  backends' corrupt-row tolerance posture.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide a NEW `loopplane.ledger` package with a `UsdLedger` Protocol:
  `async add(principal_id, month, usd: Decimal) -> Decimal` (the NEW post-increment total) +
  `get(principal_id, month) -> Decimal` (sync; unseen → `Decimal(0)`). `month` is an opaque caller-
  derived `YYYY-MM` string (the ledger holds no clock).
- **FR-002**: `add` MUST be an **atomic read-modify-write per `(principal_id, month)`** that never
  loses a concurrent increment; it returns the exact new total (so callers never do a separate
  non-atomic read-then-write).
- **FR-003**: Ship **File, SQLite, and Postgres** backends mirroring 060's checkpoint store. Postgres
  uses a single atomic `INSERT … ON CONFLICT(principal_id,month) DO UPDATE … RETURNING` (the only
  cross-PROCESS-safe path) via ADR 0008's sync thread-bridge, import-guarded behind the EXISTING
  `loopplane[postgres]` extra; SQLite/File are **single-process-honest** (an in-process
  per-`(principal,month)` `anyio.Lock`) — documented, not a silent cross-process guarantee.
- **FR-004**: USD MUST be **exact `Decimal`** end-to-end (TEXT for SQLite/File, NUMERIC for Postgres);
  **float is forbidden** (it silently corrupts money).
- **FR-005**: The package MUST be **additive / no new dependency** — pure storage; no loop / budget /
  controller / event-schema / content change (enforcement is unit 063). Importing `loopplane.ledger`
  MUST NOT require the `postgres` extra (the `psycopg` import is guarded).
- **FR-006**: Tests MUST be **offline-safe** — File/SQLite in-process; the Postgres backend exercised
  against a faithful stub (`pytest.importorskip`); the suite MUST NOT require a running database. The
  concurrent-no-lost-update test is the load-bearing case.
- **FR-007**: The plan authors **ADR 0010** (covering 062 + 063; the four design forks are settled —
  separate package, three backends, Postgres-only cross-process atomicity, exact Decimal).

### Key Entities *(include if feature involves data)*

- **UsdLedger**: the Protocol (`add` async atomic → new total; `get` sync).
- **File/SQLite/Postgres UsdLedger backends**: a `ledger(principal_id, month, usd_total, PK(principal_id,
  month))` store (TEXT/NUMERIC `usd_total`); per-`(principal,month)` atomic increment.
- **`loopplane[postgres]` extra**: the EXISTING extra (`psycopg[binary]>=3`) — reused, not new.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `add`/`get` round-trip exactly; `add` returns the new total; an unseen key reads
  `Decimal(0)` — 100% of covered scenarios.
- **SC-002**: Concurrent same-key `add`s never lose an increment (the final total = the exact sum);
  Postgres uses the atomic upsert; SQLite/File the per-key lock — proven offline (no running DB).
- **SC-003**: Money is exact `Decimal` (no float drift); importing the base package needs no
  `postgres` extra; the four gates + the new contract suite pass; no runtime/event change.

## Assumptions

- Mirrors 060's `loopplane.checkpoint` (the Protocol-over-backends seam, the three backends, the
  per-key `anyio.Lock`, `_connect()` table-create-on-connect, ADR 0008's sync thread-bridge, the
  `loopplane[postgres]` extra). Exact-Decimal money from 053 pricing / 055 budget.
- **Out of scope (unit 063)**: the per-user-monthly cap ENFORCEMENT (extending 055's BudgetChecker to
  read/write this ledger + terminate `budget-exceeded`); the clock/month derivation; the controller
  wiring. This unit is the durable STORE only.
- **Out of scope / DEFERRED**: durable pending-charge / write-ahead semantics beyond best-effort;
  distributed/sharded ledgers. Postgres is the multi-process story; File/SQLite are single-process.
- Additive; default-unused; offline-testable; public-safe (opaque `principal_id` + USD + a `YYYY-MM`
  string — no secrets; a DSN is host config, never echoed). The plan authors ADR 0010. Per
  Constitution IX the concept is borrowed but re-derived against this seam.
