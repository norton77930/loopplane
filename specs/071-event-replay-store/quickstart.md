# Quickstart: Event Replay Store Validation

## Prerequisites

- Python environment managed by `uv`
- Existing LoopPlane test dependencies installed
- Optional Postgres tests remain skip-gated unless a test database is explicitly configured

## Store Contract Validation

Run the replay-store contract suite:

```powershell
uv run pytest -q tests/contract/test_event_replay_store.py
```

Expected outcomes:

- File and SQLite replay stores append and load records in sequence order.
- Retention keeps only the configured newest records per session.
- Owner filtering prevents cross-principal replay.
- Corrupt entries are skipped with public-safe problem messages.
- Postgres import behavior is guarded when the optional dependency is absent.

## Reconnect Behavior Validation

Run the web/API reconnect integration tests:

```powershell
uv run pytest -q tests/integration/test_webapi_replay_store.py tests/unit/test_sse_reconnect.py
```

Expected outcomes:

- A reconnect with `Last-Event-ID` replays only later stored frames.
- Replay and live delivery deduplicate by sequence.
- Store polling can continue from durable records when no local live channel exists.
- Missing or malformed `Last-Event-ID` degrades safely.
- Non-owner replay attempts return the existing not-found behavior.

## Default-Unchanged Regression

Run the existing web/API SSE tests that cover unit 058 behavior:

```powershell
uv run pytest -q tests/integration/test_webapi_us3.py tests/unit/test_sse_reconnect.py
```

Expected outcomes:

- No durable store configured means current in-memory replay behavior remains unchanged.
- Disabled replay remains byte-identical.

## Full Gate

Before final review:

```powershell
uv run ruff check
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

The final board validation also requires `git diff --check`, `openspec/` scan, public-safety scan,
and local `sensitive-scan.txt` if present.
