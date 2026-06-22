# ADR 0013: Platform fairness

- **Status**: Accepted (2026-06-22)
- **Deciders**: LoopPlane maintainer (pre-settled on the roadmap board); spec
  072 (`platform-fairness`).
- **Supersedes / superseded by**: Extends ADR 0009. Does not supersede ADR
  0009.
- **Related**: Constitution **IV** (runtime boundary clarity), **V** (Tool
  Gateway ownership), **VI** (Runtime Event Bus ownership), **VII**
  (public-safe documentation and failures), **X** (default-off, testable,
  reversible). Builds on unit 061 (`tenant-host-pool`).

## Context

ADR 0009 added the G20 isolation slice: a per-principal host pool above the
host. Each tenant gets its own `LoopPlaneHost`, so tenants can run concurrently
while each host keeps its sequential `_active` invariant. ADR 0009 explicitly
deferred the platform tail: resource fairness, fair model-call scheduling,
per-tenant quota beyond in-flight counts, many-writer durability, and
cross-process or distributed pooling.

The roadmap board pre-settled unit 072 as the next narrow slice of that tail:
in-process platform fairness only. The system needs to prevent one bursty tenant
from monopolizing local model-call capacity and give operators a local
per-tenant outstanding-work bound, without changing the host isolation model or
runtime contracts.

## Decision

- **D1 - Keep pool-above-host and per-host sequential execution.** The tenant
  host pool remains the isolation boundary. This ADR does not relax
  `LoopPlaneHost._active` and does not allow concurrent runs inside one host.
- **D2 - Add a shared in-process fairness collaborator.** Hosts created for
  tenants in the same process share a host-supplied fairness object. The object
  owns local tenant quota counts and model-turn scheduling state.
- **D3 - Split quota admission from model-turn scheduling.** Per-tenant
  outstanding-work quota is checked before work is admitted. Fair model-turn
  permits are checked after request assembly and before
  `ModelBoundary.stream_turn`.
- **D4 - Use existing principal identity.** Tenant identity is the authenticated
  principal id already used by the web/API host and checkpoint metadata. There
  is no second tenant identity system.
- **D5 - Default-off and byte-identical.** With no fairness configuration, the
  tenant host pool, single-host behavior, host session semantics, loop behavior,
  and tests remain unchanged.
- **D6 - Preserve Tool Gateway and Event Bus ownership.** Fairness does not
  resolve, authorize, execute, wrap, or observe tools. It does not add runtime
  events, change event payloads, change content blocks, change termination
  reasons, or bump schema version.
- **D7 - Public-safe rejection.** Quota excess is rejected before the run starts
  where possible and maps to a generic public-safe response such as HTTP 429
  `capacity exceeded`. Responses must not expose tenant ids, prompts, queue
  sizes, model ids, paths, provider errors, or secrets.
- **D8 - In-process only.** Distributed fairness, cross-process scheduling,
  external queues, database-backed reservations, many-writer durable ordering,
  and weighted tenant tiers remain deferred.

## Consequences

- A noisy tenant can be bounded locally and cannot monopolize in-process
  model-call starts while another within-quota tenant is ready.
- The existing host pool remains reversible: removing the fairness object
  restores pre-072 behavior.
- The design is testable with deterministic offline scheduler and quota tests.
- Quota and scheduling state is lost on process restart by design; durable and
  distributed fairness need a separate future ADR.
- Operator-visible diagnostics are intentionally generic in this unit to keep
  the shared serving path public-safe.
