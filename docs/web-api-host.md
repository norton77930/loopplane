# Web / API Host (`loopplane.webapi`)

Expose the public **Host Application Interface** ([`loopplane.host`](./embedding-host.md)) over a
network API: start a run, stream its normalized events, drive an interactive session, inspect
sessions/history/artifacts, and guard all of it behind an authentication boundary.

It is an **additive transport**. It embeds a `LoopPlaneHost`; it drives no runtime internals, executes
no tool itself (Constitution V), and consumes the normalized event stream as a host consumer — it
never re-emits the live bus (Constitution VI). It requires the `web` extra
(`pip install loopplane[web]`).

## Mount it

```python
from loopplane.webapi import create_app

app = create_app(host, authenticator=my_verifier, api_prefix="/v1")
```

`create_app(host, *, authenticator=None, api_prefix="/v1") -> FastAPI` returns an ASGI app. Serve it
with any ASGI server, or drive it in-process with a test client (no socket). See
[`examples/webapi_quickstart.py`](../examples/webapi_quickstart.py).

## The surface

All paths omit the configurable `api_prefix` (default `/v1`). Every route is behind the auth boundary.

| Method & path | Does |
|---|---|
| `POST /runs` | Start one run; returns a metadata-only `RunResult` (terminal reason, turns, history view, consumer failures). A sequential-run conflict → `409`. |
| `POST /runs/events` | Start one run and stream its normalized events as **SSE** in recorded order, then an `outcome` frame. |
| `POST /sessions` | Open an interactive session → `{session_id}`. |
| `GET /sessions/{id}/events` | The session's live **SSE** event stream. |
| `POST /sessions/{id}/submit` | Drive the session to its outcome (a pending approval/question is answered out-of-band). |
| `POST /sessions/{id}/approvals/{request_id}` | Answer a pending approval → `{resolved}`. |
| `POST /sessions/{id}/questions/{request_id}` | Answer a pending question → `{resolved}`. |
| `POST /sessions/{id}/cancel` | Cancel + close the session (never hangs). |
| `GET /sessions` | List known sessions (public-safe summaries). |
| `GET /sessions/{id}/history` | A metadata-only history snapshot. |
| `POST /sessions/{id}/resume` | Resume a session from durable records. |
| `GET /sessions/{id}/artifacts/{ref}` | Retrieve an offloaded artifact, or `404`. |

See [contracts/web-api.md](../specs/011-loopplane-web-api-host/contracts/web-api.md) for the full
request/response shapes and status codes.

## The event stream (Constitution VI)

The SSE stream forwards each normalized event verbatim as `data: <serialize_event(event)>\n\n`, in the
events' **recorded order** (monotonic `sequence`, never wall-clock). The host is a *consumer* of the
recorded stream — it adds nothing and re-emits nothing. The run is driven on an unbounded channel so a
slow, failing, or disconnecting client can never crash or hang it; an unread/closed stream is dropped
and the run still terminates.

## Metadata-only responses vs. the stream

A sharp line:

- **JSON response bodies** (run result, history, session summaries, errors) are **metadata-only**:
  ids, counts, public-safe reasons. History is projected to `{role, block_count}` — never the raw
  `ContentBlock` text or tool I/O.
- **The event stream** carries the run's own normalized content (assistant output, etc.) to the
  authenticated client, because that is what a streaming consumer needs (Constitution VI). That is the
  client receiving the run's output by design — not a committed-artifact leak (Principle VII governs
  what ships in the repo, which uses only public-safe fixtures).

## The authentication boundary

Authentication is a **pluggable, default-deny** boundary: an embedder-injected verifier
`Authenticator = (credential: str | None) -> Awaitable[Principal | None]`, read from the request's
`Authorization` header and enforced before any route reaches the host. The verifier maps the credential to
a `Principal` identity (which admits and scopes session ownership, 022), or returns `None` to deny; a
missing or **raising** verdict also denies, with a fixed `401 {"detail": "unauthorized"}` that never echoes
the credential. A reference `token_authenticator` (maps `Bearer <token>` → `Principal`) ships for dev/tests. With **no** authenticator
injected the default denies every request, so an unconfigured host is safe. The host ships no credential
store, token issuer, or login flow — that is out of scope (a reserved extension point).

## Boundary

`loopplane.webapi` imports only `loopplane.host` and `loopplane.events` (plus the FastAPI/Starlette
transport and stdlib). It never imports the controller, gateway, dispatcher, or a sibling layer; it
executes no tool and re-emits no live bus. An import-boundary audit enforces it
([contracts/web-boundary.md](../specs/011-loopplane-web-api-host/contracts/web-boundary.md)).

## Reserved extension points (named, not built)

A web UI / dashboard (unit 012); real cloud deployment, TLS termination, and worker scaling; multi-tenant
user management, a persistent credential/identity store, and OAuth / SSO; rate limiting and quotas beyond
the auth boundary (governance is unit 009); bidirectional realtime collaboration and distributed session
sharing.
