# Research: Durable USD Ledger

Settled by **[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md)** (the four Phase C forks).
No open `NEEDS CLARIFICATION`.

## Decision 1 — A NEW loopplane.ledger package (ADR 0010 D1/D2)

**Decision**: A sibling package to `loopplane.checkpoint`/`loopplane.budget` with a `UsdLedger`
Protocol keyed by `(principal_id, month)`: `async add(...) -> Decimal` (the new post-increment total)
+ `def get(...) -> Decimal` (sync; unseen → `Decimal(0)`). `month` is an opaque caller-derived
`YYYY-MM` string.

**Rationale**: `CheckpointStore` is append-only + `session_id`-keyed + replay-to-total — the wrong
shape for an atomic `(principal_id, month)` counter (its per-session lock is the wrong granularity).
A separate seam keeps both clean.

**Alternatives considered**: new `add()` methods on `CheckpointStore` (rejected — wrong shape,
forces every checkpoint backend to grow a second storage model + a wrong-granularity lock).

## Decision 2 — Three backends + per-backend atomicity (ADR 0010 D3)

**Decision**: Mirror 060's File/SQLite/Postgres. Postgres: `INSERT … ON CONFLICT(principal_id,month)
DO UPDATE SET usd_total = ledger.usd_total + EXCLUDED.usd_total RETURNING usd_total` — the only
cross-PROCESS-safe path; ADR 0008's sync thread-bridge (async `add` via `anyio.to_thread`, sync
`get` direct); import-guarded behind the EXISTING `loopplane[postgres]` extra. SQLite: an UPSERT in
one transaction with the exact-Decimal sum under a per-`(principal,month)` `anyio.Lock`. File: per-key
JSON read-add-write-flush under the lock. SQLite/File are **single-process-honest** (documented).

**Rationale**: Reuse 060's proven pattern; Postgres is the real multi-process story; File is the
offline/test default. No new dependency.

**Alternatives considered**: a subset of backends (rejected — Postgres is the reason the ledger
exists; File is the default/test).

## Decision 3 — Exact Decimal money (ADR 0010 D4)

**Decision**: Store/sum USD as exact `Decimal` — TEXT (SQLite/File), NUMERIC (Postgres). Float is
forbidden.

**Rationale**: Float silently corrupts money; pricing (053) + budget (055) are already exact Decimal.

## Decision 4 — add returns the new total; atomic per key (ADR 0010 D2)

**Decision**: `add` returns the post-increment total (so 063's cap check is one round-trip, no
separate non-atomic read). The increment is atomic per `(principal_id, month)` so concurrent adds
(real under 061's TenantHostPool) never lose an increment.

**Rationale**: Atomicity is the whole point; returning the new total serves the monthly-cap check
without a read-then-write race.

## Out of scope (unit 063 / deferred)

The per-user-monthly cap ENFORCEMENT (extend 055's BudgetChecker; the clock/month derivation; the
controller wiring; fail-open) is unit 063. Distributed/sharded ledgers + write-ahead pending-charges
are deferred (Postgres = the multi-process story; best-effort run-end accrual).
