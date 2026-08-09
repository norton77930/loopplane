# Platform & deployment

**Covered units:** 011, 022, 056, 057, 058, 059, 060, 061, 067, 071, 072.

Running LoopPlane as a service: the web/API host, who the caller is, how streams survive
reconnects, where state lives, and how tenants are kept apart. This guide is navigational:
[`../capabilities.md`](../capabilities.md) and [`../api-reference.md`](../api-reference.md)
are the authorities — where they disagree with this page, they win.

## The deployment shape

`loopplane.webapi` (unit 011, install extra `web`) exposes the runtime over HTTP with
`create_app(...)`. It offers REST for control, Server-Sent Events for streaming, and — since
unit 074 — a WebSocket live channel beside them. It is a **thin adapter over the host
facade**: the same `LoopPlaneHost` an embedder uses. The desktop sidecar is a second
adapter over that same facade, which is why the two surfaces cannot drift apart in
behavior.

For the route-level contract see [Web / API host](../web-api-host.md).

## Who the caller is

### Principals and token auth (022)

Authentication is **default-deny**: a request without an accepted credential gets nothing,
and every session is scoped to its owning `Principal`. The seam is a small `Authenticator`
protocol; `token_authenticator` covers the simple deployment.

### OAuth / JWT verification (056, 067)

`jwt_authenticator` (install extra `oauth`) drops into the same seam and verifies JWTs
against a JWKS endpoint. Unit 067 hardened the refresh path against an unknown-`kid` spray:
a bounded negative-`kid` cache, a cross-request refresh throttle
(`jwt_authenticator(refresh_min_interval=…)`), and single-flight refresh, so a hostile
client cannot amplify requests against your identity provider.

Authentication is a boundary, not a feature toggle: everything downstream — session
ownership, monthly budget caps, fairness quotas — keys off the principal.

## Streaming that survives reality

### Resumable SSE (058)

A dropped connection resumes with `Last-Event-ID`: the host replays the events the client
missed from an in-memory ring buffer (ADR 0006). That is enough for a single long-lived
process.

### Durable replay (071)

An in-memory ring dies with the process and is not shared between workers. Unit 071 adds an
opt-in `EventReplayStore` keyed by `(session_id, sequence)` with `FileEventReplayStore`,
`SqliteEventReplayStore`, and `PostgresEventReplayStore` backends (ADR 0012), so reconnects
survive restarts and multi-worker deployments. The 058 in-memory ring remains the default —
turning this on is a deployment decision, not an upgrade.

## Where state lives

Checkpointing is append-only and owned by the controller; `CheckpointStore` has three
backends:

| Backend | Use it for | Unit |
| --- | --- | --- |
| `FileCheckpointStore` | development, single process | 021 |
| `SqliteCheckpointStore` | single-host deployments | 021 |
| `PostgresCheckpointStore` | shared/multi-process deployments (extra `postgres`) | 060 |

Postgres bridges sync and async carefully (ADR 0008). The USD ledger has the same triad
and the same reasoning — see [Cost governance](cost-governance.md).

## MCP: tools and resources from outside

`loopplane.adapters.mcp` speaks all four transports — `stdio`, `http`, `sse`, and
`websocket` (unit 057) — behind one `MCPServerConfig`, so an MCP server is a configuration
entry rather than a code path. Unit 059 surfaces **MCP resources** as gateway-routed
synthetic tools (ADR 0007), which keeps the Constitution V invariant intact: a resource
read is still a gateway call, subject to the same permission decisions as any other tool.

Interactive OAuth flows for MCP servers are not in scope
([`../gap-analysis.md`](../gap-analysis.md)).

## Keeping tenants apart

### Per-principal host pool (061)

`TenantHostPool` gives each principal its own host instance with in-flight caps, so one
principal's load cannot starve another's (ADR 0009). The pool sits **above** the host, so
the host itself stays single-tenant and simple.

### Fairness and quota (072)

Unit 072 adds per-tenant quota and fair in-process scheduling of model-call capacity above
the pool (ADR 0013). An over-quota request receives a public-safe 429 (or an SSE
rejection) rather than a stall. Default-off; the slice is in-process.

Both are honest about their limit: execution is still **in-process, single-worker**.
Cross-process pooling and distributed scheduling are roadmap items, not shipped behavior
([`../capabilities.md`](../capabilities.md#scope-boundaries-out-of-scope--deferred)).

## A deployment checklist

- [ ] Install with the extras you actually need: `web`, plus `oauth` / `postgres` /
      `mcp` / `net` as applicable (see the extras matrix in the project README).
- [ ] Choose an `Authenticator` — never run with authentication disabled outside local
      development.
- [ ] Choose a `CheckpointStore` backend that matches your process topology.
- [ ] If you run more than one worker, turn on a durable `EventReplayStore`.
- [ ] Decide on `TenantHostPool` and fairness quotas before, not after, the second tenant.
- [ ] Wire budget caps and the ledger — see [Cost governance](cost-governance.md).
- [ ] Keep provider credentials in the host process; the browser never receives them.

## Where to go next

- [Web / API host](../web-api-host.md) — the transport and its routes (unit 011).
- [Web frontend](../web-frontend.md) and [Web UI product](web-ui-product.md) — what sits
  on top.
- [Host interface](../embedding-host.md) — the facade both adapters use.
- [`../api-reference.md`](../api-reference.md) — the exact public names and signatures.
