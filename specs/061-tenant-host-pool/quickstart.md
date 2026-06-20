# Quickstart / Validation: Per-Principal Host Pool

See [contracts/tenant-host-pool.md](contracts/tenant-host-pool.md), [data-model.md](data-model.md),
and [ADR 0009](../../docs/adr/0009-tenant-host-pool.md). A per-principal host pool above the host;
additive, default-off (single shared host) byte-identical.

## Run the webapi pool tests

```powershell
pytest tests/ -k "pool or tenant or webapi" -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; with no pool configured the web/API host behaves exactly as today (single shared
host; the existing 409 on a concurrent run); the existing webapi/host tests pass unchanged.

## Validation scenarios (mirror the acceptance scenarios)

1. **Concurrent principals** — pool enabled + a host factory; principal A and principal B run
   concurrently → both proceed (no "a run is already active"). (FR-001, SC-001)
2. **Same-principal sequential** — principal A already running → A's second concurrent run is
   rejected (the per-host `_active` invariant holds). (FR-002, SC-001)
3. **Default-off byte-identity** — no pool → single shared host; behavior + the existing webapi tests
   byte-identical to today. (FR-003, SC-002)
4. **Bounded** — a per-principal in-flight cap exceeded → rejected/bounded (no unbounded growth).
   (FR-004, SC-003)
5. **Contained** — one principal's host failure → other principals unaffected. (FR-005, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the api-reference bijection (the new `TenantHostPool` export documented). NOTE: do not run the full
pytest concurrently with the verify Workflow (the real-subprocess MCP tests flake under CPU load).
