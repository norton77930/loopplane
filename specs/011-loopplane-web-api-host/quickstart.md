# Quickstart: Web / API Host

Validate that `loopplane.webapi` exposes the embedded host over a network API — run, stream,
interactive session, inspection, and auth — **in-process, offline**, with no real socket bound.

## Prerequisites

- The repo installed editable with the dev group (provides `fastapi` + `httpx`) and the `web` extra:
  the implement step adds `fastapi>=0.115` to the `web` extra and `fastapi` + `httpx>=0.27` to the
  `dev` group (mirroring the `mcp` / `otel` pattern). Until then, `pip install fastapi httpx`.
- A public-safe **fake model** (as in prior units' examples) so runs are deterministic and offline.

## What it provides

See [contracts/web-api.md](./contracts/web-api.md) for the full surface. Core entry point:

```text
from loopplane.webapi import create_app
app = create_app(host, authenticator=my_verifier)   # host: a LoopPlaneHost
```

`create_app` returns an ASGI app; drive it with Starlette's in-process `TestClient` — no network.

## Validation scenarios

Each maps to a user story and its success criteria; all run via `TestClient` (no real socket).

### US1 — Start a run (SC-001)
1. Build a host with a fake model; `create_app(host, authenticator=allow_all)`.
2. `client.post("/v1/runs", json={"prompt": "..."}, headers=auth)`.
3. **Expect** `200` with a `RunResult`: a `session_id`, a public-safe `termination_reason`, an integer
   `turns_taken`, a metadata-only `history` (entries are `{role, block_count}` — **no** block text),
   and `consumer_failures`.
4. A second concurrent run before the first returns ⇒ **expect** `409`. A malformed body ⇒ `422/400`
   with `ErrorResponse(detail="invalid request")`.

### US2 — Stream events (SC-002, SC-005)
1. `with client.stream("POST", "/v1/runs/events", json={...}, headers=auth) as r:` read SSE frames.
2. **Expect** each `data:` frame to equal `serialize_event(event)` for the run's events, in the
   **recorded order**, followed by an `event: outcome` frame.
3. Repeat ⇒ identical frame order (determinism). Drop the client mid-stream ⇒ the run still
   terminates and any consumer failure is recorded — **no crash/hang**.

### US3 — Interactive session
1. `POST /v1/sessions` ⇒ `OpenedSession{session_id}`.
2. Open `GET /v1/sessions/{id}/events` (SSE) in a portal thread; `POST .../submit` a prompt that
   triggers an approval.
3. On the `approval-requested` frame, `POST .../approvals/{request_id}` with `{allow: true}` ⇒
   `Resolved{resolved: true}`; the run proceeds. `POST .../cancel` ⇒ never hangs.
4. An unknown `request_id` ⇒ `Resolved{resolved: false}` (no crash); an unknown session ⇒ `404`.

### US4 — Inspect (SC-003)
1. `GET /v1/sessions` ⇒ public-safe `SessionSummaryView`s.
2. `GET /v1/sessions/{id}/history` ⇒ `HistoryEntryView`s — assert **no** block text in the body.
3. `POST /v1/sessions/{id}/resume` ⇒ `200`. `GET /v1/sessions/{id}/artifacts/{ref}` ⇒ content on a
   hit, `404` `not found` when no backend is configured or the reference is unknown.

### US5 — Auth boundary (SC-004)
1. Request with **no** credential ⇒ `401`. With a credential the verifier rejects ⇒ `401`. With a
   verifier that **raises** ⇒ `401` (not `500`).
2. With a valid credential ⇒ admitted (the US1–US4 calls above succeed).
3. An app built with **no** `authenticator` denies every request (default-deny). No response echoes
   the credential.

## Boundary & public-safety (SC-006)

- `tests/contract/test_webapi_boundary.py`: `loopplane.webapi` imports only `loopplane.host` /
  `loopplane.events` / `fastapi` / stdlib; executes no tool; re-emits no live bus; responses are
  metadata-only; default-deny holds; SSE order is deterministic.
- `tests/contract/test_public_safety.py` (`PHASE11_TARGETS`): committed sources, the example, and the
  doc carry no secret / private path / internal name / IP.

## Example

[`examples/webapi_quickstart.py`](../../examples/webapi_quickstart.py) builds a host with a fake
model, calls `create_app`, and drives a run + a stream + an auth check through the in-process
`TestClient`, printing public-safe outcomes only.

## Expected outcome

All US1–US5 scenarios pass in-process with no real network; responses are metadata-only; the SSE
stream is deterministic and fail-safe; the auth boundary defaults to deny. The full suite stays green
and ruff + mypy(strict) clean.
