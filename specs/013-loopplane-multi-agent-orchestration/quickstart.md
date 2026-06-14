# Quickstart: Multi-Agent Orchestration

Validate that `loopplane.orchestration` registers subagents, coordinates them, and aggregates their
events / artifacts — **deterministically, metadata-only, in-process, offline**.

## Prerequisites

- The repo installed editable. **No extra dependency** — the layer is pure Python over the Phase-3 loop
  surface.
- Public-safe **scripted loop definitions** (a `LoopDefinition` over a scripted model, as in the unit-003
  suites) so runs are deterministic and offline.

## What it provides

See [contracts/orchestration-api.md](./contracts/orchestration-api.md). Core entry points:

```python
from loopplane.orchestration import AgentRegistry, Coordinator, aggregate_events, aggregate_artifacts

registry = AgentRegistry()
registry.register("planner", planner_definition)
registry.register("worker", worker_definition)

results = await Coordinator(registry).run(["planner", "worker"])
events = aggregate_events(results)
artifacts = aggregate_artifacts(results)
```

## Validation scenarios

Each maps to a user story and its success criteria; all run in-process under `pytest.mark.anyio`.

### US1 — Register and run a subagent (SC-001)
1. `registry.register("a", definition)`; a duplicate name → `DuplicateSubagentError`.
2. `await Coordinator(registry).run(["a"])` → one `SubagentResult` with a `ChildRunReference`
   (subagent, loop_id, run_refs) and a `LoopOutcome`. `run(["ghost"])` → a `failure="not found"` result.

### US2 — Coordinate a set (SC-002, SC-006)
1. Register several subagents; `await coord.run([...])` → one result per selection, in **registration
   order**, each run once.
2. Repeat → identical order/results (deterministic).

### US3 — Aggregate child events (SC-003)
1. `aggregate_events(results)` → `(subagent, type, sequence)` records grouped by subagent (registration
   order), ordered by sequence within. **No** `LoopEvent.payload` / content in any record.
2. Repeat → identical (deterministic).

### US4 — Aggregate child artifacts (SC-003)
1. `aggregate_artifacts(results)` → `(subagent, session_id, reference)` records grouped by subagent; a
   subagent with no artifacts contributes nothing. Reference metadata only.

### US5 — Delegate & fail safe (SC-004)
1. `await coord.delegate(policy)` runs exactly the policy-selected subagents; a **raising** policy → an
   empty result.
2. A subagent whose loop run **fails** → a captured `failure` result; the coordinator still completes
   with the others. An **empty** selection → an empty result tuple.

## Boundary & public-safety (SC-005)

- `tests/contract/test_orchestration_boundary.py`: `loopplane.orchestration` imports only
  `loopplane.engineering` / stdlib; executes no tool; re-emits no live bus; aggregated views are
  metadata-only; aggregation is deterministic.
- `tests/contract/test_public_safety.py` (`PHASE13_TARGETS`): committed sources, the example, and the
  doc carry no secret / private path / internal name / IP.

## Example

[`examples/orchestration_quickstart.py`](../../examples/orchestration_quickstart.py) registers scripted
subagents, coordinates them, and prints the aggregated event / artifact views — metadata only.

## Expected outcome

All US1–US5 scenarios pass in-process; the coordinator's results and aggregated views are deterministic
(registration-ordered) and metadata-only; failing subagents / raising policies / empty selections are
fail-safe. The full suite stays green and ruff + mypy(strict) clean.
