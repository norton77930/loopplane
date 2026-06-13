# Quickstart & Validation: Observability & Debug-Console Layer (Phase-10)

A validation guide for `loopplane.inspect`. It proves the layer turns recorded event streams into
deterministic, metadata-only inspection structures — diagnostics, a trace, a timeline, and replay — with no
run driven and no live-bus re-emission. Implementation detail lives in [data-model.md](./data-model.md) and
[contracts/](./contracts); these are runnable scenarios.

## Prerequisites

- The repo installed editable with dev tools: `python -m pip install -e .` and `pytest` + `anyio`.
- Phases 1 and 3 are Verified (the public `loopplane.events` Runtime Event and `loopplane.engineering` Loop
  Event/State surfaces this layer composes).

## What the example shows

`examples/inspect_quickstart.py` (public-safe, credential-free):

1. Builds a scripted Loop Event stream and a per-session Runtime Event stream.
2. `loop_diagnostics(...)` and `run_diagnostics(...)` → prints the metadata summaries.
3. `build_trace(...)` → prints the loop → iteration → run → tool/turn span tree.
4. `build_timeline(...)` → prints the sequence-ordered timeline with open/paired spans.
5. `replay(stream, sink)` → re-feeds the stream through a recording sink and prints the delivered count.

Run:

```bash
python examples/inspect_quickstart.py
```

Expected: deterministic, metadata-only output (counts, ids, types, sequences, the terminal status / reason),
with no conversation content, tool arguments, or secrets, and no run started.

## Validation scenarios (map to user stories & success criteria)

| Scenario | How to validate | Proves |
|---|---|---|
| US1 — loop diagnostics | `loop_diagnostics(loop_events)` reports iterations/runs/retries/repairs/reviews + latest outcomes + terminal status | SC-001, FR-010 |
| Reuses reconstruction | the latest-state fields match `reconstruct_state(loop_events)` | SC-008, FR-062 |
| Determinism | each transform run twice over the same stream ⇒ identical result | SC-002, NFR-001 |
| US2 — run diagnostics | `run_diagnostics(runtime_events)` reports tool-call/turn/error counts + termination reason; an unknown type is skipped | SC-003, SC-004, FR-020/FR-021 |
| US3 — trace | `build_trace(...)` nests loop→iteration→run→tool/turn; metadata only; a session with no run stream ⇒ childless span | SC-003, FR-030-FR-032 |
| US4 — timeline | `build_timeline(...)` orders by sequence, pairs started/completed, marks an unpaired start open | SC-007, FR-040/FR-041 |
| US5 — replay | `replay(stream, sink)` delivers every event in recorded order; starts no run | SC-009, FR-050/FR-051 |
| Metadata-only | no produced artifact carries content/arguments/outputs | SC-003, FR-001/FR-060 |
| Read-only / boundary | import + no-run audit: imports only engineering/events; no `run_loop`/`.run(`/host | SC-005, FR-061 |
| Public-safety | scan committed files + `PHASE10_TARGETS` | SC-006, NFR-002 |

## Test commands

```bash
python -m pytest tests/unit/test_inspect_core.py tests/integration -k inspect --basetemp=".pytmp" -q
python -m pytest tests/contract/test_inspect_boundary.py --basetemp=".pytmp" -q

# Full gates (run before any commit touching source/tests)
python -m ruff format && python -m ruff check && python -m mypy
python -m pytest --basetemp=".pytmp" -q
```

Expected: all inspect suites green; ruff + mypy(strict) clean; public-safety scan green.

## What this layer does NOT do

No frontend, web, or live UI; no driving/mutating a run or loop; no re-emitting the live buses; no remote
export; no persistent storage; no cross-run correlation; no wall-clock timing or flame graphs (reserved —
FR-090-FR-094). It only transforms recorded streams into metadata-only inspection structures.
