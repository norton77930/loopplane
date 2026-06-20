# Contract: Durable USD Ledger

A NEW `loopplane.ledger` package — a durable per-`(principal_id, month)` USD accumulator. Per
[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md). Pure storage (enforcement is 063);
additive; no new dependency.

## Surface

| Name | Shape | Notes |
| ---- | ----- | ----- |
| `loopplane.ledger.UsdLedger` | Protocol: `async add(principal_id, month, usd: Decimal) -> Decimal` + `def get(principal_id, month) -> Decimal` | NEW. |
| `loopplane.ledger.FileUsdLedger` | a `UsdLedger` over per-key JSON | NEW (default/offline). |
| `loopplane.ledger.SqliteUsdLedger` | a `UsdLedger` over SQLite | NEW. |
| `loopplane.ledger.PostgresUsdLedger` | a `UsdLedger` over Postgres | NEW; import-guarded (`loopplane[postgres]`). |

## Behavior

| Case | Result |
| ---- | ------ |
| `add(p, m, x)` then `add(p, m, y)` | The second returns `x + y` (exact Decimal); `get(p, m) == x + y`. |
| `get(p, m)` for an unseen key | `Decimal(0)` (no error). |
| Concurrent `add`s to the same `(p, m)` | The total = the exact sum (no lost increment). |
| Postgres `add` | A single atomic `INSERT … ON CONFLICT … DO UPDATE … RETURNING` (cross-PROCESS-safe). |
| SQLite / File `add` | Atomic within ONE process (a per-`(principal,month)` `anyio.Lock`); NOT cross-process — documented. |
| Large / fractional money | Exact (Decimal; TEXT/NUMERIC) — no float drift. |
| Base install (no `postgres` extra) | `loopplane.ledger` imports; the Postgres backend errors clearly only when constructed without `psycopg`. |

## Invariants

- `add` is an ATOMIC read-modify-write per `(principal_id, month)` returning the new total; no
  concurrent increment is ever lost. `get` of an unseen key is `Decimal(0)`.
- Money is exact `Decimal` end-to-end (TEXT/NUMERIC); float is never used.
- Cross-PROCESS atomicity holds ONLY on Postgres; SQLite/File are single-process-honest (an
  in-process lock) — stated, not silent.
- Pure storage: no loop/budget/controller/event-schema/content change (enforcement is 063); additive;
  importing `loopplane.ledger` needs no `postgres` extra. Reuses ADR 0008's sync thread-bridge + the
  EXISTING `loopplane[postgres]` extra (no new dependency).
- Public-safe: opaque `principal_id` + USD + a `YYYY-MM` string — no secrets; a DSN is host config,
  never echoed.
- Offline-testable: File/SQLite in-process; Postgres against a faithful stub; the suite never
  requires a running database.
