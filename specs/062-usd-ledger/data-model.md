# Data Model: Durable USD Ledger

Additive; a NEW `loopplane.ledger` package. No runtime/loop/budget/event change (storage only). Per
[ADR 0010](../../docs/adr/0010-usd-ledger-monthly-budget.md).

## UsdLedger (new — Protocol)

| Method | Sync/async | Notes |
| ------ | ---------- | ----- |
| `add(principal_id, month, usd: Decimal) -> Decimal` | async | Atomic read-modify-write per `(principal_id, month)`; returns the NEW post-increment total. Commits durably before returning. |
| `get(principal_id, month) -> Decimal` | sync | The accumulated USD for the key; an unseen key → `Decimal(0)`. |

`month` = an opaque caller-derived `YYYY-MM` string (the ledger holds no clock). USD = exact
`Decimal` throughout.

## Backends (new — mirror loopplane.checkpoint)

| Backend | Atomic increment | Money column | Cross-process? |
| ------- | ---------------- | ------------ | -------------- |
| `PostgresUsdLedger` | `INSERT … ON CONFLICT(principal_id,month) DO UPDATE SET usd_total = ledger.usd_total + EXCLUDED.usd_total RETURNING usd_total` (single statement; ADR 0008 sync thread-bridge) | `NUMERIC` | **YES** (the only cross-process-safe path) |
| `SqliteUsdLedger` | UPSERT in one transaction; exact-Decimal sum in Python under a per-`(principal,month)` `anyio.Lock` | `TEXT` | single-process-honest |
| `FileUsdLedger` | per-key JSON read-add-write-flush under the per-key `anyio.Lock` | TEXT (Decimal-as-string in JSON) | single-process-honest |

Backing store (SQLite/Postgres): `ledger(principal_id TEXT, month TEXT, usd_total TEXT|NUMERIC,
PRIMARY KEY (principal_id, month))`, created on connect. `psycopg` import-guarded (the EXISTING
`loopplane[postgres]` extra).

## Rules (from FRs + ADR 0010)

| Rule | Source |
| ---- | ------ |
| NEW loopplane.ledger package; UsdLedger Protocol (async add → new total; sync get) | FR-001, D1/D2 |
| add is atomic per (principal_id, month); no lost concurrent increment | FR-002, D2 |
| File/SQLite/Postgres backends; Postgres ON CONFLICT…RETURNING cross-process; SQLite/File single-process-honest | FR-003, D3 |
| exact Decimal (TEXT/NUMERIC), never float | FR-004, D4 |
| additive; pure storage; no loop/budget/event change; import-guarded; no new dep | FR-005 |
| offline-safe tests (faithful Postgres stub); concurrent-no-lost-update is load-bearing | FR-006 |
| ADR 0010 (covers 062+063) | FR-007 |
