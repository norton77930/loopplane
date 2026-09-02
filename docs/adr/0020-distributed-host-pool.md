# ADR 0020: Cross-process principal admission (G20 remaining tail)

- **Status**: **Accepted** (2026-09-02) — authored at the unit 085 plan step and
  accepted by the maintainer before implementation began, as spec 085 FR-020
  requires for the R2 cross-process concurrency trigger.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. **Extends ADR 0009** (pool-above-host)
  and **ADR 0013** (in-process fairness). Discharges the 0009 D5 / 0013 D8 deferral of
  *cross-process pooling and many-writer ownership*, and **only that**. Cluster-wide
  fair *turn* interleaving, weighted tiers, live run migration, G9 remote execution,
  and G11 Docker remain deferred.
- **Related**: Constitution **IV** (serving layer above the host; a boundary update is
  recorded here and will be mirrored into
  `docs/architecture/TARGET_ARCHITECTURE_BOUNDARIES.md` §3 webapi on implementation),
  **V** (no tool path), **VI** (no event/schema change), **VII** (public-safe rejects),
  **X** (default-off, testable, reversible). Units **061**, **072**, **060** (postgres
  extra + ADR 0008 thread-bridge reused, not session records).

## Context

ADR 0009 gave each principal an isolated `LoopPlaneHost` so two principals can run at
the same time in one process, while each host keeps `_active`. ADR 0013 added
in-process outstanding-work quota and fair model-turn permits. Both guarantees are
**process-local**: `TenantHostPool` is a dict plus an `anyio.Semaphore`;
`PlatformFairness` is in-memory.

A multi-worker web/API deployment therefore:

- lets the same principal hold an in-flight run on worker A and another on worker B
  (061's sequential invariant does not hold across the group);
- multiplies configured caps by the worker count (072's quota is per process);
- cannot recover a principal stuck on a killed worker (there is no grant to expire).

071/060/062 already made *other* records many-writer (SSE replay, checkpoints, USD
ledger). They do not coordinate who may *start a run*.

Spec 085 FR-020 names three mechanism forks. This ADR chooses one.

## Decision

- **D1 — Fork A: a host-supplied admission collaborator above the pool (and above the
  single-host path).** Before a web/API worker drives a run for a principal, it takes a
  cluster-scoped **grant**. Different principals still run concurrently. The
  per-host `_active` gate is **not** relaxed (ADR 0009 D4 stands). Sticky routing (fork
  B) is rejected as the *sole* mechanism: a mis-routed request must still be safe. A
  new queue/lock extra (fork C) is rejected; it is GATE-§E.

- **D2 — Protocol + in-memory default + optional Postgres via the existing extra.**
  The runtime declares `AdmissionStore` (take / release / heartbeat). The shipped
  default is in-memory and single-process-honest (two simulated workers in tests share
  one store object). Multi-worker production uses `PostgresAdmissionStore` behind
  `loopplane[postgres]`, import-guarded, sync psycopg off-loaded with `anyio.to_thread`
  (ADR 0008). **No File/SQLite admission backend in this unit** — those honesty bars
  would look like durability while remaining single-process, which is the failure mode
  this unit exists to close. No new extra.

- **D3 — Default-off and byte-identical.** `create_app(admission=None)` (the default)
  leaves 061/072 and the single shared host unchanged. Admission is constructor
  injection, like `host_pool`, **not** a `RuntimeConfig` knob: it is serving-layer
  coordination, not run policy.

- **D4 — One grant can reserve in-flight and, when configured, outstanding-work.**
  Cluster in-flight cap is the 061 number (per principal, not per model). Cluster
  outstanding-work cap is used only when the operator also configured 072 fairness;
  the 072 in-process fair *turn* scheduler stays local to the worker that already
  admitted the work (ADR 0013 D8's remaining deferral). Local pool semaphore and local
  fairness remain as defense in depth; they must not become looser than the cluster
  grant.

- **D5 — Fail-closed on new admits.** If the store cannot confirm a take (timeout,
  error, missing extra, unreachable DSN), the worker **rejects** the new run with a
  public-safe conflict/capacity response. It MUST NOT fall back to uncoordinated
  in-process admission. Work that already holds a grant continues.

- **D6 — Grants are ephemeral serving leases, not session state.** They are not
  checkpoint records, not ledger rows, not events, and not content. Constitution G3
  (controller-owned session persistence) is undisturbed. A grant has a liveness TTL
  and is heartbeaten by the admit context manager; expiry lets another worker take
  over after a crash without allowing a live holder to be overwritten.

- **D7 — Public-safe mapping onto existing HTTP language.** In-flight / ownership
  conflict → HTTP 409 `a run is already active` (the 061 mapping). Outstanding-work
  overage → HTTP 429 `capacity exceeded` (the 072 mapping). Details never include
  holder ids, grant ids, DSNs, queue depths, worker names, or other principals.

- **D8 — Wrap every run-start path.** Today `TenantHostPool.in_flight` is applied only
  on `POST /runs`. Cluster admission MUST also wrap `POST /runs/events` and the
  interactive `run_session` drive. Otherwise those routes bypass the invariant. This
  is 085 wiring, not a retro-edit of unit 061's Verified tasks.

- **D9 — TARGET §3 (webapi) additive sentence (implementation).** Webapi already owns
  the pool and replay stores. It additionally owns optional cross-process admission
  leases. It still MUST NOT execute tools or re-emit the bus. `loopplane.fairness`
  stays in-process; it does not import the admission store.

## Consequences

- Operators can scale web/API workers without silently doubling tenant caps or
  allowing two in-flight runs for one principal.
- Single-process and unconfigured deployments stay byte-identical.
- Postgres is the only cross-process-honest backend; that matches ledger/checkpoint
  honesty. In-memory is the test and single-worker default.
- A coordinator outage reduces *availability of new admits* (fail-closed) rather than
  correctness.
- Cluster-wide fair turn interleaving is still not provided; a noisy tenant can still
  monopolize *model-call starts on one worker* under 072's local scheduler. That is a
  later unit.
- Implementation proceeded after this ADR was Accepted.

## Rollback

Remove the `admission=` argument (and the Postgres table if it was created). No event
schema, no checkpoint migration, no default change to reverse.
