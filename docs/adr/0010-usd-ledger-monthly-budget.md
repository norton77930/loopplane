# ADR 0010: Durable per-user-monthly USD ledger & monthly-cap enforcement (G22 Phase C)

- **Status**: Accepted (2026-06-21)
- **Deciders**: LoopPlane maintainer (settled the four forks at the Phase C design review); specs
  062 (usd-ledger) + 063 (monthly-budget). One ADR governs both units.
- **Supersedes / extends**: completes **ADR 0005 D7** (which deferred "a durable per-user-monthly
  USD ledger ... to a later unit + ADR"). Builds on **ADR 0008** (the Postgres sync thread-bridge),
  055 (in-loop budget enforcement), 060 (the checkpoint store pattern), 053 (pricing), 056 (verified
  identity), 061 (same-principal concurrency).
- **Related**: Constitution **III** (a bounded, opt-in cost-safety primitive), **IV** (a new durable
  store + a re-touch of the in-loop enforcement point — already opened by 055/ADR 0005), **VI**
  (reuses the existing `budget-exceeded` `TerminationReason` — NO new reason, NO `SCHEMA_VERSION`
  bump), **VII** (the DSN + `principal_id` are public-safe), **X** (additive, default-off
  byte-identical, reversible). Tenth ADR.

## Context

ADR 0005 (G22 Phase B / unit 055) shipped in-loop USD enforcement with an **in-memory per-session**
spend counter, and deferred the **durable per-user-monthly** cap because it needed identity (G18/056),
durable storage (G19/060), and same-principal concurrency (G20-A/061) — all now shipped. Phase C adds
that durable ledger + a per-user-monthly cap. The design fork set (all settled by the maintainer):
separate package vs overload CheckpointStore; the enforcement seam; the backends; the fail mode.

## Decision

- **D1 — A NEW `loopplane.ledger` package (NOT overload CheckpointStore).** `CheckpointStore` is
  append-only + `session_id`-keyed + per-session-serialized (replay-to-total) — the opposite shape of
  an atomic `(principal_id, month)` counter. The ledger is a sibling package to `loopplane.checkpoint`
  / `loopplane.budget`.
- **D2 — `UsdLedger` Protocol.** `async add(principal_id, month, usd: Decimal) -> Decimal` (an ATOMIC
  read-modify-write per `(principal_id, month)`, returning the NEW post-increment total so callers
  never do a separate non-atomic read-then-write) + `def get(principal_id, month) -> Decimal` (sync;
  unseen → `Decimal(0)`). `month` is an opaque caller-derived `YYYY-MM` string (the ledger holds no
  clock — like `records.py` holds no clock). `add` is async (it commits durably, mirroring
  `CheckpointStore.append`); `get` is sync (mirroring `load`/`list_sessions`).
- **D3 — Three backends + per-backend atomicity (mirror 060).** Postgres (`PostgresUsdLedger`): a
  single `INSERT … ON CONFLICT(principal_id,month) DO UPDATE SET usd_total = ledger.usd_total +
  EXCLUDED.usd_total RETURNING usd_total` — **the only cross-PROCESS-safe path**; ADR 0008's sync
  thread-bridge (async `add` via `anyio.to_thread`, sync `get` direct), import-guarded behind the
  EXISTING `loopplane[postgres]` extra (no new dependency). SQLite (`SqliteUsdLedger`): an UPSERT in
  one transaction with the exact-Decimal sum computed under a per-`(principal,month)` `anyio.Lock`.
  File (`FileUsdLedger`): per-key JSON read-add-write-flush under the per-key lock. **SQLite + File
  are single-process-honest** (an in-process lock; no protection against a second OS process) — the
  spec/this ADR state Postgres is the multi-process story; never a silent guarantee.
- **D4 — Exact `Decimal` money.** Stored/summed as exact `Decimal` (TEXT for SQLite/File, NUMERIC for
  Postgres). **Float is forbidden** — it silently corrupts a money ledger. Mirrors 053/055.
- **D5 — Enforcement (063) reuses 055.** Extend `BudgetChecker` with an OPTIONAL monthly dimension
  (a `UsdLedger` + `principal_id` + a `YYYY-MM` month + a `per_user_monthly_usd: Decimal | None` cap).
  The monthly check rides the SAME in-loop enforcement point + the SAME existing `budget-exceeded`
  `TerminationReason` + the stop-after-overage semantic (ADR 0005 D3) — **no new reason, no
  `SCHEMA_VERSION` bump**.
- **D6 — Per-turn durable write-back inside `record_turn` (now async).** `record_turn` becomes async:
  it `await ledger.add(principal_id, month, this_turn_cost)` and folds the returned monthly total
  into `exceeded()` (the cap is checked each turn; the run's cost accrues durably as it goes). This
  ripples to the loop's `record_turn` call site (already an await point). The async-ification of
  `record_turn` is the one not-byte-identical-by-construction touch — gated entirely behind the
  optional monthly dimension (no ledger configured → the 055 path is unchanged).
- **D7 — Clock / month.** The caller derives `month` as a `YYYY-MM` UTC string from an INJECTABLE
  clock (default `lambda: datetime.now(UTC)`, matching the repo convention). UTC calendar-month
  buckets; a turn after a month boundary counts to the new month.
- **D8 — `principal_id` threading on create AND resume.** The controller builds the per-session
  `BudgetChecker` with the host-supplied `UsdLedger` + `per_user_monthly_usd` + `principal_id` on
  BOTH `create` and `resume` — `resume` currently omits it, a fail-open gap that 063 closes + tests
  (so monthly caps enforce on resumed sessions).
- **D9 — FAIL-OPEN on a ledger outage (maintainer-chosen).** A ledger read/write exception → allow
  this turn + emit a public-safe diagnostic (availability; mirrors 055's unpriced-model fail-soft) —
  never crash, never deny. (Fail-closed/deny was rejected: a ledger outage would otherwise become a
  service outage.)
- **D10 — Default-off byte-identity (X).** No `usd_ledger` AND no `per_user_monthly_usd` configured →
  no ledger built, the `BudgetChecker` path is byte-identical to 055; `record_turn` stays effectively
  sync (no ledger await). Importing `loopplane.ledger` needs no `postgres` extra (guarded).
- **D11 — Public-safe (VII).** The ledger stores only an opaque `principal_id` + accumulated USD + a
  `YYYY-MM` string — no secrets. A Postgres DSN is host config, never echoed.
- **D12 — Overage bound under 061.** N concurrent same-principal sessions each read the same pre-run
  monthly total, so worst-case overage ≈ cap + N turns (the atomic `add` keeps the LEDGER exact; only
  the read is stale). Accepted; `per_principal_in_flight = 1` mitigates. Stated in the spec.

## Consequences

- **Completes G22**: a durable per-user-monthly USD cap on top of 055's per-message/session caps;
  contained, default-off, additive.
- **A new durable seam** (`loopplane.ledger`) + **one async-ified `record_turn`** + a per-turn
  write-back — all gated behind the optional monthly dimension; no schema bump; reuses 055 /
  `budget-exceeded` / pricing / ADR 0008's bridge / the `loopplane[postgres]` extra / the already-
  plumbed `principal_id` (one missing hop on resume, closed). **Default-off byte-identical.**
- **Honest limits (documented)**: cross-process atomicity only on Postgres; best-effort run-end
  accrual (a crash mid-run loses that run's increment from the monthly total — mirrors 055's
  resume-loses-accumulation honesty); the cap + N-turns overage bound under concurrency. Distributed
  ledgers + write-ahead pending-charges remain out of scope.
