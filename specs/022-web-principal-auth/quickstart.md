# Quickstart: Web Principal Authentication (unit 022)

Validates identity-bearing auth and per-principal session scoping. Backend only; offline;
no new dependency.

## Prerequisites

- `uv sync --extra web` (FastAPI is the existing `web` extra; nothing new).

## Wire a principal-aware app

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig, StorageConfig
from loopplane.webapi import create_app, token_authenticator

host = LoopPlaneHost(RuntimeConfig(model=my_model, storage=StorageConfig(root="./data")))
auth = token_authenticator({"tok-alice": "alice", "tok-bob": "bob"})
app = create_app(host, authenticator=auth)
```

## Scenarios

1. **Default-deny**: `create_app(host)` with no authenticator → every `/v1/*` route returns
   `401`; the body never contains the credential.
2. **Identity + ownership**: with `Authorization: Bearer tok-alice`, open a session and run;
   `GET /v1/sessions` lists only Alice's sessions. With `Bearer tok-bob`, Bob's listing
   excludes Alice's session, and `GET /v1/sessions/{alice_id}/history` (and events / submit /
   resume / artifacts / cancel) returns **404** — no data, no existence signal.
3. **Durable across restart**: Alice runs a session against `StorageConfig(root="./data")`;
   build a fresh `create_app` over the same storage; Alice still lists and resumes it, Bob
   cannot.

## Gate

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

**Expected**: all green; the two-principal scoping / default-deny / restart / no-leak tests
pass; the checkpoint `principal_id` round-trips on both backends; the api-reference/`__all__`
drift test passes; no new dependency in the build.
