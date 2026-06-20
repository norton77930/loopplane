# Quickstart / Validation: Resumable SSE (Reconnect)

See [contracts/sse-reconnect.md](contracts/sse-reconnect.md), [data-model.md](data-model.md), and
[ADR 0006](../../docs/adr/0006-resumable-sse.md). Resumable session SSE via `id:` +
`Last-Event-ID` replay from a bounded in-memory per-session buffer; additive + default-off.

## Run the webapi SSE tests

```powershell
pytest tests/ -k "sse or session or streaming or webapi" -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; with the buffer disabled (default) the existing webapi/streaming tests pass
unchanged (no `id:` line, no buffer); the new reconnect tests pass.

## Validation scenarios (mirror the acceptance scenarios)

1. **Reconnect resumes** — buffer enabled; capture frames + their `id:`, drop the connection, emit
   more, reconnect with `Last-Event-ID = <last id>` → the missed frames (seq > id) are replayed in
   order, then live; no duplicate. (FR-001/003, SC-001)
2. **id: line** — each frame (buffer enabled) carries `id: <event.sequence>`. (FR-001)
3. **Default-off byte-identity** — buffer disabled → no `id:` line, no buffer; byte-identical to
   today (existing webapi/streaming tests pass). (FR-004, SC-002)
4. **Bounded** — emit more than N events → only the last N retained; a reconnect past the window gets
   what remains, then live. (FR-002, SC-003)
5. **Fail-safe** — a missing/garbage/too-old `Last-Event-ID` → live stream (no crash). (FR-005, SC-003)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`) and
the events serialize/`SCHEMA_VERSION` tests (unchanged — no event-schema change).
