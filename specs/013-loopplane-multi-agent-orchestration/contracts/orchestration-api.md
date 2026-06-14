# Contract: Multi-Agent Orchestration API

The surface of `loopplane.orchestration`. All operations are in-process; subagent runs go through the
public Phase-3 `run_loop`, and aggregation reads each captured `LoopOutcome`.

## Registry

```python
from loopplane.orchestration import AgentRegistry

registry = AgentRegistry()
registry.register("planner", planner_definition)   # -> Subagent; duplicate name -> DuplicateSubagentError
registry.register("worker", worker_definition)
registry.names()                                    # ("planner", "worker")  -- registration order
```

| Operation | Behavior | Requirement |
|---|---|---|
| `register(name, definition)` | Register a named subagent; duplicate → `DuplicateSubagentError` | FR-001 |
| `get(name)` | `Subagent` or `None` | FR-003 |
| `names()` | names in registration order | FR-011, NFR-004 |

## Coordinator

```python
from loopplane.orchestration import Coordinator

coord = Coordinator(registry)
results = await coord.run(["planner", "worker"])     # tuple[SubagentResult, ...] in registration order
results = await coord.delegate(my_policy)             # policy selects; fail-safe
```

| Operation | Behavior | Requirement |
|---|---|---|
| `await run(selection)` | Run exactly the selected subagents, each once, in registration order, via `run_loop`; returns a `SubagentResult` per selected name | FR-010, FR-011 |
| unknown name in `selection` | a `SubagentResult(failure="not found")`; the known subagents still run | FR-003, FR-041 |
| a subagent's `run_loop` fails | a `SubagentResult(failure=...)`; the coordinator still completes | FR-041, SC-004 |
| `await delegate(policy)` | resolve the policy (a raising policy → empty selection), then `run` | FR-040, FR-041 |
| empty selection | an empty result tuple — never an error | FR-041, NFR-005 |

A `SubagentResult` is `(subagent, reference: ChildRunReference | None, outcome: LoopOutcome | None,
failure: str | None)`. A `ChildRunReference` is `(subagent, loop_id, run_refs)` — metadata only.

## Aggregation (metadata-only)

```python
from loopplane.orchestration import aggregate_events, aggregate_artifacts

events = aggregate_events(results)        # tuple[AggregatedEvent(subagent, type, sequence), ...]
artifacts = aggregate_artifacts(results)  # tuple[AggregatedArtifact(subagent, session_id, reference), ...]
```

| Operation | Behavior | Requirement |
|---|---|---|
| `aggregate_events(results)` | each subagent's loop events as `(subagent, type, sequence)`, grouped by subagent (registration order), ordered by sequence within | FR-020, FR-021 |
| `aggregate_artifacts(results)` | each subagent's artifact refs as `(subagent, session_id, reference)`, grouped by subagent | FR-030, FR-031 |
| a result with no outcome | contributes nothing (an empty group) | FR-030, NFR-005 |
| metadata only | no `LoopEvent.payload` / content / tool I/O / secret in any record | FR-021, FR-031, NFR-006, SC-003 |

## Cross-cutting guarantees

| Guarantee | Requirement |
|---|---|
| Deterministic by registration order (not wall-clock) | NFR-004, SC-002 |
| Aggregated views are metadata-only | FR-021, FR-031, NFR-006, SC-003 |
| Failing subagent / raising policy / unknown / empty → safe | FR-041, NFR-005, SC-004 |
| No tool executed by this layer; live bus never re-emitted | NFR-002, NFR-003, SC-005 |
