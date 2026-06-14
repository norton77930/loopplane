# Phase 0 Research: Multi-Agent Orchestration

All decisions resolve the spec into concrete, public-safe, offline, in-process choices. The layer is an
**additive orchestration** over the public Phase-3 loop surface (unit 003); it adds no runtime behavior
and no dependency.

## D1 — No new dependency; sequential execution

**Decision**: Run subagents **sequentially** — the coordinator `await run_loop(definition)` for each
selected subagent in registration order. No third-party dependency is added (not even `anyio`).

**Rationale**: Sequential execution is fully deterministic, avoids any shared-host concurrency question
(each `run_loop` builds its own host from the definition), and satisfies every requirement — the
aggregation is deterministic by **registration order** regardless of how subagents run, so sequential
is the simplest correct choice. Concurrent fan-out is a **reserved** extension point: because the
aggregation is already ordered by registration (not completion time), adding concurrency later changes
no result.

**Alternatives considered**:
- Concurrent fan-out via an `anyio` task group now — adds concurrency complexity and a shared-host
  question for no determinism gain (aggregation is registration-ordered either way). Rejected (reserved).

## D2 — Aggregate from captured outcomes, not a live sink (Constitution VI)

**Decision**: Aggregate from each subagent's **captured `LoopOutcome`** — its `events` tuple (the
recorded, ordered loop-event stream) and its `state.run_refs` / `state.artifacts`. The coordinator
passes **no** live `on_loop_event` sink; it reads the recorded outcome after the run.

**Rationale**: `LoopOutcome` already carries the ordered event stream and the run/artifact references,
so a live sink is unnecessary. Reading the recorded outcome makes the layer a **consumer of recorded
events** — exactly as Constitution VI prescribes for trace/aggregation consumers — and it re-emits no
live bus.

## D3 — A subagent is a named loop definition

**Decision**: A **subagent is a named `LoopDefinition`** registered in the agent registry; running it
drives exactly one loop run through `run_loop`. A `ChildRunReference` is the subagent name + the loop
run's id + its `RunReference`s (the agent-run session ids + terminal reasons).

**Rationale**: The Phase-3 layer's unit of work is a loop run; orchestration composes several. The
registry maps names to definitions; the coordinator runs the selected definitions.

## D4 — Deterministic, metadata-only aggregation

**Decision**: Aggregated views are **flat, registration-ordered tuples of metadata-only records**:
- `AggregatedEvent(subagent, type, sequence)` for each loop event, ordered by subagent (registration
  order) then by the event's monotonic `sequence`.
- `AggregatedArtifact(subagent, session_id, reference)` for each `ArtifactRef`, ordered by subagent.

No `LoopEvent.payload`, conversation content, tool I/O, or secret is surfaced — only the event `type` +
`sequence` and the public-safe references.

**Rationale**: Carrying the subagent name on each record keeps the views flat (easy to assert) yet
groupable; projecting to `type`/`sequence`/references keeps them strictly metadata-only (NFR-006) — and
deterministic (the event stream is already sequence-ordered; registration order is fixed).

## D5 — Fail-safe capture

**Decision**: A `SubagentResult` is `(subagent, reference | None, outcome | None, failure | None)`. A
subagent whose `run_loop` raises is caught → `failure` set, `outcome` None. An **unknown** name in the
selection → `failure="not found"`. A **raising delegation policy** is caught → an empty selection. An
**empty** selection → an empty result tuple. The aggregation tolerates results with no outcome (an empty
contribution).

**Rationale**: Real multi-agent runs have partial failures; the coordinator must complete with the
healthy subagents' results. Capturing per-subagent failures (rather than raising) is the fail-safe
posture (NFR-005, SC-004).

## Open questions

None. All choices are informed defaults documented in the spec's Assumptions; none is scope-blocking, so
no `[NEEDS CLARIFICATION]` markers remain.
