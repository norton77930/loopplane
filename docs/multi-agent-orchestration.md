# Multi-Agent Orchestration (`loopplane.orchestration`)

Run several agent loops as **subagents** and combine their results. This layer is
an additive sibling package built on the public Phase-3 loop surface
(`loopplane.engineering`): a named **registry** of loop definitions, a
**coordinator** that runs a selected set through `run_loop`, and **deterministic,
metadata-only** aggregated views over what they recorded.

It is a coordination layer, not a runtime. It **executes no tool itself**
(Constitution V) and **re-emits no live event bus** — it reads each subagent's
captured `LoopOutcome` as a consumer, passing no live sink (Constitution VI). It
composes only the public Phase-3 surface; it reaches no Phase-1/2 internal, host,
gateway, or sibling layer.

## When to use it

Use orchestration when one job is naturally several independent loops — for
example a research subagent, a drafting subagent, and a review subagent — and you
want them coordinated deterministically and their results combined into one
metadata-only view. Each subagent is an ordinary Phase-3 `LoopDefinition`; the
coordinator adds selection, ordering, fail-safe capture, and aggregation around
them.

## Concepts

### Subagent registry

A `Subagent` is a public name paired with a `LoopDefinition`. `AgentRegistry`
holds them in **registration order** — the single deterministic order the
coordinator runs and aggregates by.

```python
from loopplane.orchestration import AgentRegistry

registry = AgentRegistry()
registry.register("researcher", researcher_definition)
registry.register("writer", writer_definition)
registry.register("reviewer", reviewer_definition)
```

- `register(name, definition)` returns the `Subagent`; a duplicate name raises
  `DuplicateSubagentError` (a public-safe message).
- `get(name)` returns the `Subagent` or `None`; `name in registry` tests
  membership; `names()` returns the registered names in registration order.

### Coordinator

`Coordinator(registry)` runs a selected set of subagents and returns one
`SubagentResult` per selection.

```python
from loopplane.orchestration import Coordinator

coordinator = Coordinator(registry)
results = await coordinator.run(["reviewer", "researcher"])
```

- The selection is **deduplicated** (each subagent runs at most once) and the
  results come back in **registration order**, independent of the selection
  order — so the same selection always yields the same result sequence.
- Each known subagent is driven through the public `run_loop`. On success its
  `SubagentResult` carries a `ChildRunReference` (subagent / loop_id / run_refs)
  and the `LoopOutcome`.
- An unknown name is captured as `SubagentResult(failure="not found")` rather
  than raising. An empty selection yields an empty result tuple.

### Delegation

A `DelegationPolicy` is any `Callable[[AgentRegistry], Sequence[str]]` — it
inspects the registry and returns the names to run. `delegate` resolves the
policy, then runs the selection.

```python
results = await coordinator.delegate(lambda registry: ["writer", "reviewer"])
```

A policy that **raises** is contained: it resolves to an empty selection, so
`delegate` returns an empty result rather than propagating the error.

### Fail-safe capture

If a subagent's loop run raises, the coordinator captures it as
`SubagentResult(failure="failed")` — a fixed, public-safe marker, never the raw
exception detail — and the other selected subagents still complete. One failing
subagent never aborts the coordinated run.

### Aggregated views (metadata only)

Two projections flatten the subagents' captured outcomes into deterministic,
**metadata-only** records. Both skip a result that has no outcome (a failed or
not-found subagent contributes nothing), and both preserve registration order
across subagents.

```python
from loopplane.orchestration import aggregate_events, aggregate_artifacts

events = aggregate_events(results)        # (subagent, type, sequence)
artifacts = aggregate_artifacts(results)  # (subagent, session_id, reference)
```

- `aggregate_events` projects each subagent's recorded loop events to
  `AggregatedEvent(subagent, type, sequence)`, grouped by subagent in
  registration order and ordered by `sequence` within a subagent.
- `aggregate_artifacts` projects each subagent's artifact references to
  `AggregatedArtifact(subagent, session_id, reference)`, grouped by subagent.

Neither view ever carries a `LoopEvent.payload`, conversation content, tool
input/output, or a secret — only public ids, types, sequences, and references.

## Determinism

Given the same registry and the same selection, the coordinated results, the
event aggregation, and the artifact aggregation are **identical on every run**.
Ordering is by registration order, then by event sequence — never wall-clock.
This makes coordinated runs reproducible and safe to assert against in tests.

## Boundary

`loopplane.orchestration` imports only `loopplane.engineering` (the public
Phase-3 surface: `run_loop`, `LoopDefinition`, `LoopOutcome`, `LoopState`,
`RunReference`) and the standard library. It does not import a Phase-1/2 internal,
the host, the gateway, the runtime controller, or a sibling layer; it executes no
tool and re-emits no live bus. These rules are enforced by
`tests/contract/test_orchestration_boundary.py` and the public-safety scan.

## Reserved extension points (named, not built)

These are deliberately out of scope for this layer and are documented so the
boundary stays clear:

- **Distributed orchestration** — running subagents across processes, hosts, or
  machines. This layer is in-process only.
- **Dynamic subagents** — spawning, registering, or rewriting subagents at run
  time from a running loop. Registration is explicit and up front.
- **Inter-subagent communication** — message passing, shared mutable state, or
  feedback channels between concurrently running subagents. Subagents are
  independent; only their recorded outcomes are combined, after the fact.

## See also

- Runnable example: [`examples/orchestration_quickstart.py`](../examples/orchestration_quickstart.py)
- The Phase-3 loop surface this layer composes:
  [`docs/loop-engineering.md`](./loop-engineering.md)
