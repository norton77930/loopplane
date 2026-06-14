# Data Model: Multi-Agent Orchestration

All structures are **public-safe** and, for aggregated views, **metadata-only**. They are the layer's
own value types; they wrap — never replace — the public Phase-3 types. Plain frozen dataclasses (the
layer is pure value transforms over `run_loop` outcomes).

## Registry — `registry.py`

### `Subagent`
| Field | Type | Notes |
|---|---|---|
| `name` | `str` | The public subagent name. |
| `definition` | `LoopDefinition` | The Phase-3 loop definition this subagent runs. |

### `AgentRegistry`
A registry of named subagents.
- `register(name, definition) -> Subagent` — register; a duplicate name raises `DuplicateSubagentError`
  (FR-001).
- `get(name) -> Subagent | None` — lookup (None if unknown).
- `names() -> tuple[str, ...]` — names in **registration order** (the deterministic order).
- `__contains__(name)` — membership.

### `DuplicateSubagentError`
Raised by `register` on a duplicate name (a public-safe `ValueError`).

## Coordinator — `coordinator.py`

### `ChildRunReference`
| Field | Type | Source | Notes |
|---|---|---|---|
| `subagent` | `str` | the registered name | Public id. |
| `loop_id` | `str` | `LoopOutcome.loop_id` | The loop run's id. |
| `run_refs` | `tuple[RunReference, ...]` | `LoopOutcome.state.run_refs` | The agent-run references (session id + terminal reason); metadata only. |

### `SubagentResult`
| Field | Type | Notes |
|---|---|---|
| `subagent` | `str` | The selected name. |
| `reference` | `ChildRunReference \| None` | Present on a successful run. |
| `outcome` | `LoopOutcome \| None` | The captured Phase-3 outcome (carries events + state); `None` on failure / not-found. |
| `failure` | `str \| None` | A public-safe failure marker (`"not found"`, a captured run failure); `None` on success. |

### `DelegationPolicy`
A selection of which registered subagents to run:
```text
DelegationPolicy = Callable[[AgentRegistry], Sequence[str]]
```
A raising policy is contained (an empty selection).

### `Coordinator`
- `Coordinator(registry)`.
- `async run(selection: Sequence[str]) -> tuple[SubagentResult, ...]` — run exactly the selected
  subagents (each once), in registration order; an unknown name → a not-found result; a failing run →
  a captured failure result (FR-010, FR-011, FR-041).
- `async delegate(policy: DelegationPolicy) -> tuple[SubagentResult, ...]` — resolve the policy
  (fail-safe) to a selection, then `run` it (FR-040, FR-041).

## Aggregation — `aggregate.py` (metadata-only)

### `AggregatedEvent`
| Field | Type | Source |
|---|---|---|
| `subagent` | `str` | the result's name |
| `type` | `str` | `LoopEvent.type` |
| `sequence` | `int` | `LoopEvent.sequence` |

### `AggregatedArtifact`
| Field | Type | Source |
|---|---|---|
| `subagent` | `str` | the result's name |
| `session_id` | `str` | `ArtifactRef.session_id` |
| `reference` | `str` | `ArtifactRef.reference` |

### Builders
- `aggregate_events(results) -> tuple[AggregatedEvent, ...]` — for each result (registration order), for
  each event in `result.outcome.events` (if any), emit `AggregatedEvent(name, event.type,
  event.sequence)`. Events are already sequence-ordered (FR-020, FR-021).
- `aggregate_artifacts(results) -> tuple[AggregatedArtifact, ...]` — for each result, for each
  `ArtifactRef` in `result.outcome.state.artifacts`, emit `AggregatedArtifact(name, ref.session_id,
  ref.reference)` (FR-030, FR-031).

A result with no outcome (failure / not-found) contributes nothing — an empty group.

## Determinism & safety invariants

- **Metadata-only views**: no aggregated record carries a `LoopEvent.payload`, conversation content,
  tool I/O, or secret — only `type` / `sequence` / session id + artifact reference (FR-021, FR-031,
  NFR-006, SC-003).
- **Deterministic**: ordering is by **registration order** then by the events' monotonic `sequence` —
  never wall-clock / completion time; the same registry + selection yields the same views (NFR-004,
  SC-002).
- **Fail-safe**: a failing subagent / raising policy / unknown name / empty selection → an explicit,
  safe result; never a crash or hang (NFR-005, SC-004).
