# ADR 0021: Cluster-wide fair model-turn permits (G20 fair-turn slice)

- **Status**: **Accepted** (2026-09-03) — authored at the unit 086 plan step and
  accepted by the maintainer before implementation began, as spec 086 FR-018
  requires for the R2 cross-process scheduling trigger.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. **Extends ADR 0013**
  (in-process fairness) and **ADR 0020** (cluster admission). Discharges the
  remaining 0013 D8 deferral of *cross-process model-turn scheduling*, and
  **only that**. Weighted tenant tiers, live run migration, G9 remote
  execution, and G11 Docker remain deferred.
- **Related**: Constitution **IV** (fairness stays a Phase-1 collaborator;
  serving-layer stores are injected, never imported), **V** (no tool path),
  **VI** (no event/schema change), **VII** (public-safe), **X** (default-off,
  testable, reversible). Units **072**, **085**, **060** (postgres extra +
  ADR 0008 thread-bridge reused if a durable backend is chosen).

## Context

ADR 0013 added in-process outstanding-work quota (`admit`) and fair model-turn
permits (`model_turn`) on a shared `PlatformFairness` object. ADR 0020 made
*who may start a run* and the outstanding-work *cap* cluster-scoped. It
explicitly left 072's turn scheduler process-local.

Two workers therefore still have two independent waiter lists. Configured
`max_active_model_calls` and `max_consecutive_starts` are multiplied by the
worker count. A noisy admitted tenant on worker A can take every local start
while a ready tenant on worker B cannot participate in that fairness view —
the bottleneck this unit cares about is **shared downstream model-call
capacity**, not 085 ownership.

`model_turn` is entered from `AgentLoop` via the fairness object. Fairness is
Phase-1. 085 stores live in `loopplane.webapi`. Phase-1 MUST NOT import webapi.

Spec 086 FR-018 names three mechanism forks. This ADR chooses one.

## Decision

- **D1 — Fork A: injectable turn-permit collaborator on `PlatformFairness`.**
  `PlatformFairness` gains an optional constructor collaborator (default
  `None`). `model_turn` still runs the in-process 072 scheduler (defense in
  depth). When the collaborator is present, a cluster permit is taken around
  the granted local turn. Fork B (count starts only in webapi) is rejected as
  the sole mechanism: the loop would still take local turns without a cluster
  view. Fork C (new queue extra) is rejected; it is GATE-§E.

- **D2 — Protocol in Phase-1; implementations injected.** The runtime declares
  a small permit Protocol next to `PlatformFairnessGate` (acquire / release /
  optional heartbeat). In-memory default is single-process-honest (tests share
  one store across two simulated `PlatformFairness` instances). Multi-worker
  production MAY use a Postgres implementation behind existing
  `loopplane[postgres]`, lazy psycopg, `anyio.to_thread` (ADR 0008). **No new
  extra. No File/SQLite permit backend** (same honesty bar as ADR 0020 D2).
  Fairness MUST NOT import `loopplane.webapi`.

- **D3 — Default-off and byte-identical.** `PlatformFairness(policy)` with no
  collaborator is today's 072 object. `create_app` gains **no** new argument.
  This is not a `RuntimeConfig` knob; the embedder passes an already-wired
  fairness object on `RuntimeConfig.platform_fairness` as today.

- **D4 — Cluster-scope 072's turn policy, not a second quota.** Cluster active
  calls follow `max_active_model_calls`. Cluster consecutive-start fairness
  follows `max_consecutive_starts`. Outstanding-work and in-flight remain 085
  admission. Local 072 numbers must not become looser than the cluster permit.

- **D5 — Degrade to local 072 if a cluster permit cannot be confirmed.**
  Timeout, error, missing extra, or unreachable store MUST NOT hang an
  already-admitted run. Local scheduling still applies. This is the opposite
  of ADR 0020 D5 (fail-closed *new admits*): a missed turn is unfairness, not
  a double-run.

- **D6 — Permits are ephemeral, not session state.** Not checkpoints, not 085
  grants, not events. Constitution G3 undisturbed. A permit has a liveness TTL
  so a dead worker cannot pin cluster active-call slots forever.

- **D7 — No new HTTP resource or public error phrase.** Waiting for a turn is
  internal. User-visible failures stay existing 072/085 language. Details never
  include holder ids, permit ids, DSNs, queue depths, or other principals.

- **D8 — Do not wrap run-start paths.** 085 already wraps `/runs`,
  `/runs/events`, and `run_session`. This unit hooks `model_turn` only.

- **D9 — TARGET: fairness remains in-process; injected stores are an
  implementation detail of the fairness object.** No new TARGET block. No
  webapi Public API expansion required unless a Postgres helper is exported
  for embedders (additive, documented in api-reference if exported).

## Consequences

- Operators who already share a model backend across workers can keep
  `max_active_model_calls` / `max_consecutive_starts` honest across the group.
- Unconfigured 072 and 085 deployments stay byte-identical.
- A permit-store outage degrades fairness to today's per-worker scheduler
  instead of wedging in-flight sessions.
- Weighted tiers and live migration remain later units.
- Implementation may proceed after this ADR was Accepted.

## Rollback

Construct `PlatformFairness` without the collaborator (today's constructor).
Drop the optional Postgres tables if they were created. No event schema, no
checkpoint migration, no default change to reverse.
