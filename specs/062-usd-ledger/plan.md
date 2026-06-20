# Implementation Plan: Durable USD Ledger

**Branch**: `062-usd-ledger` (main-only autopilot) | **Date**: 2026-06-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/062-usd-ledger/spec.md`

**Boundary**: settled by **[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md)** (authored
at this plan step; covers 062 + 063; the four design forks are settled — separate package · three
backends · Postgres-only cross-process atomicity · exact Decimal). 062 is the durable STORE only —
additive, no loop/budget/event change (enforcement is 063).

## Summary

A NEW `loopplane.ledger` package: a `UsdLedger` Protocol keyed by `(principal_id, month)` —
`async add(principal_id, month, usd: Decimal) -> Decimal` (an atomic read-modify-write per key,
returning the new post-increment total) + `def get(principal_id, month) -> Decimal` (sync; unseen →
`Decimal(0)`). `month` is an opaque caller-derived `YYYY-MM` string (no clock in the ledger). Three
backends mirror `loopplane.checkpoint` (060): `FileUsdLedger`, `SqliteUsdLedger`, `PostgresUsdLedger`
— a `ledger(principal_id, month, usd_total, PK(principal_id, month))` store, exact `Decimal` money
(TEXT for SQLite/File, NUMERIC for Postgres; never float), atomic per-key increment (Postgres
`INSERT … ON CONFLICT … DO UPDATE … RETURNING` cross-process-safe via ADR 0008's sync thread-bridge;
SQLite/File single-process-honest via a per-`(principal,month)` `anyio.Lock`). `psycopg` is
import-guarded behind the EXISTING `loopplane[postgres]` extra (no new dependency). Pure storage; no
runtime/loop/budget/event change; default-unused.

## Technical Context

**Language/Version**: Python 3.11+; stdlib `decimal`, `sqlite3`, `json`, `anyio`.

**Primary Dependencies**: none new — reuses `anyio`, the EXISTING `loopplane[postgres]`
(`psycopg[binary]>=3`) extra, and the checkpoint backend pattern.

**Storage**: a `ledger` table/file keyed by `(principal_id, month)` → `usd_total` (exact Decimal).

**Testing**: pytest, **offline-safe** — File/SQLite in-process; Postgres against a faithful in-memory
stub (mirroring `tests/pg_stub.py`; `pytest.importorskip`); NO running DB. A shared parametrized
contract: round-trip, `add` returns the new total, `get` unseen = `Decimal(0)`, exact-Decimal
no-float-drift, and the load-bearing **concurrent same-key adds never lose an increment**.

**Target Platform**: cross-platform library (Postgres optional).

**Constraints**: additive; pure storage (no loop/budget/event change); exact Decimal (never float);
atomic per-key increment (Postgres cross-process; SQLite/File single-process-honest); import-guarded;
no new dependency; default-unused. ADR 0010.

## Constitution Check

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-007 + ADR 0010. ✅
- **III. Bounded cost-safety primitive (durable half)**: the store underpinning the per-user-monthly
  cap; opt-in. ✅
- **IV. Boundary**: A new durable seam (`loopplane.ledger`); the runtime/loop/gateway untouched. ✅
- **V. Tool Gateway**: N/A — no tool/execution path. ✅
- **VI. Event Bus / content**: No event-schema/SCHEMA_VERSION/content change (062 is storage only). ✅
- **VII. Public-safe**: opaque `principal_id` + USD + `YYYY-MM`; a DSN is host config, never echoed. ✅
- **IX. Reference-not-clone**: Mirrors the 060 checkpoint backend pattern + reuses ADR 0008. ✅
- **X. Testable Evolution**: Additive; default-unused; reversible; offline-tested. ✅

**Result**: PASS — additive, a NEW package behind ADR 0010; no breaking 002/001 change; no event
change. Complexity Tracking n/a (atomicity is covered by the concurrent test, not new architecture).

## Project Structure

### Documentation (this feature)

```text
specs/062-usd-ledger/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/usd-ledger.md
└── checklists/requirements.md
docs/adr/0010-usd-ledger-monthly-budget.md   # the Phase C boundary decision (062+063)
```

### Source Code (repository root)

```text
src/loopplane/ledger/__init__.py    # NEW package: the UsdLedger Protocol + the 3 backends + __all__
src/loopplane/ledger/base.py        # NEW: UsdLedger Protocol (async add -> Decimal; sync get)
src/loopplane/ledger/file.py        # NEW: FileUsdLedger (per-key JSON; per-(principal,month) lock)
src/loopplane/ledger/sqlite.py      # NEW: SqliteUsdLedger (UPSERT in a tx; exact-Decimal sum)
src/loopplane/ledger/postgres.py    # NEW: PostgresUsdLedger (ON CONFLICT…RETURNING; ADR 0008 bridge;
                                    #   import-guarded behind loopplane[postgres])
docs/api-reference.md               # MODIFIED: + a `loopplane.ledger` package section
tests/usd_ledger_stub.py            # NEW: a faithful offline psycopg stub for the Postgres ledger
tests/<ledger contract test>        # NEW: the shared File/SQLite/Postgres contract (offline)
```

**Structure Decision**: `loopplane.ledger` mirrors `loopplane.checkpoint`'s shape: a Protocol
(`base.py`) + three backends, each `_connect()`-creates-the-table + holds a per-key `anyio.Lock` dict
(re-keyed to `(principal_id, month)`). `add` is the atomic increment: Postgres a single
`ON CONFLICT … RETURNING` (cross-process), SQLite an UPSERT under the lock + transaction (the
exact-Decimal sum done in Python, stored as TEXT), File a read-add-write-flush under the lock (JSON,
Decimal-as-string). `get` is a sync point read (→ `Decimal(0)` for an unseen key). The Postgres
backend reuses ADR 0008's sync thread-bridge (async `add` via `anyio.to_thread`, sync `get` direct)
+ the import-guard (so `loopplane.ledger` imports without `psycopg`). Pure storage — nothing wires it
into the runtime (that is 063).

## Complexity Tracking

> A new durable store mirroring the 060 checkpoint backend, behind ADR 0010. The one hard property —
> atomic per-key increment with no lost update — is a well-understood UPSERT/lock pattern proven by a
> concurrent test, not new architecture. Additive, default-unused, exact-Decimal. Not a Constitution
> violation.
