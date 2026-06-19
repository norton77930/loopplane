# Contract: the `spawn_subagent` Tool Gateway tool

`spawn_subagent` is an **additive Tool-Gateway tool** that composes the **public** Phase-3 loop surface
(`loopplane.engineering.run_loop`) to run one bounded child agent. This contract states the behavior it
must hold and the audit that enforces it (`tests/unit/test_subagent_spawn.py`).

## Where it lives & allowed dependencies

- The tool is implemented in **`loopplane.tools.subagent`** (the `tools` layer), **not** in
  `loopplane.orchestration` (whose import allow-list forbids the gateway/context/model imports a tool
  needs; its boundary audit must stay green and unchanged).
- The tool MAY import: `loopplane.gateway.spi` (`ToolAdapter`, `ErrorOutput`), `loopplane.errors`,
  `loopplane.context` (`RunContext`), `loopplane.model` (`ToolDescriptor`, `TextBlock`),
  `loopplane.engineering` (the public loop surface), `loopplane.orchestration` (`aggregate_events` —
  reused metadata-only view), and (under `TYPE_CHECKING` only) `loopplane.host` (`LoopPlaneHost`).

## Behavioral contract

| Rule | Enforcement | Requirement |
|---|---|---|
| Reachable only through the Tool Gateway | Registered as a `ToolAdapter`; the model calls it like any tool | V, FR-004 |
| Drives the child **only** through `run_loop` | The adapter builds a one-shot `LoopDefinition` and calls `run_loop`; it re-implements no loop | IV, NFR-001, FR-002 |
| Returns the child's **final assistant text** on success | Recovered from the child host's `history_snapshot(session_id)` (last assistant entry's `TextBlock`s) | FR-003 |
| **Hard depth cap, fail-safe** | `context.subagent_depth >= max_subagent_depth` → `ErrorOutput`, **no** child run created | III, FR-011, SC-002 |
| Child runs at parent depth + 1 | The child host is built at `subagent_depth = context.subagent_depth + 1` | FR-010 |
| Disabled when cap = 0 | `assemble` registers the tool only when `max_subagent_depth >= 1` | FR-012 |
| Failure contained | `run_loop` wrapped in try/except; non-natural/paused/empty/raise → normalized `ErrorOutput`; parent continues | FR-020, NFR-005 |
| No raw exception/secret leaks | Fixed public-safe markers; the Gateway also normalizes any escaped exception | V, VII, FR-020 |
| **Child events captured, never re-emitted** | No live sink to `run_loop`; events surfaced only via `aggregate_events` (metadata-only) | VI, FR-030, SC-005 |
| Restricted toolset | `allowed_tools` → the child's tools are the parent∩allowlist; omitted → inherit parent | FR-040 |
| Over-run bounded | One-iteration child loop + the Gateway per-call time limit | Spec §Edge Cases |

## Input / output

**Input** (validated by the Gateway against the descriptor schema before any run):

```json
{ "task": "summarize the README", "allowed_tools": ["read_file"] }
```

- `task` — required string; empty/missing → a normalized validation error (no run).
- `allowed_tools` — optional `string[]`.

**Output**:

- Success → a `TextBlock` (the child's final assistant message, optionally + a metadata-only event-count
  line). Gateway → `ToolResultBlock(outcome="success")`.
- Denied / failure → an `ErrorOutput`. Gateway → `ToolResultBlock(outcome="failure", error=…)`.

## The one-shot child `LoopDefinition` (built by the adapter)

Mirrors `tests/orchestration_helpers.py::scripted_subagent_definition`:

```python
LoopDefinition(
    loop_id=f"subagent-{...}",
    trigger=ManualTrigger(),
    input_source=StaticInput(task),
    host_profile=HostRuntimeProfile(selector=<builds the depth+1 child host>),
    validation_policy=ValidationPolicy(validator=<always pass>),
    stop_condition=stop_on_pass(),            # + max_iterations(1) → one-shot
    observation_policy=ObservationPolicy(emit_loop_events=True),
)
```

The selector calls the injected `build_child_host(context.subagent_depth + 1, allowed_tools)` and stores
the host so the adapter can read its history snapshot after `run_loop` returns.

## Depth-guard invariant (the safety contract)

For every invocation: **if `context.subagent_depth >= max_subagent_depth`, the adapter returns an
`ErrorOutput` and constructs no `LoopDefinition` and calls no `run_loop`** — i.e. zero child runs. A child
run always carries `subagent_depth = parent + 1`, so a chain of spawns terminates at the cap. With a cap
of `1`: a top-level run (depth 0) may spawn one child (depth 1); the child (depth 1) is denied (no
grandchild). This is proven by a counting child-host factory asserting **0** child builds at the cap.

## Audit (`tests/unit/test_subagent_spawn.py`)

Deterministic, offline, in-process (ScriptedModel parent + child):

1. **Spawn round-trip** — a scripted parent calls `spawn_subagent`; a scripted child returns known text;
   the parent's tool result carries the child's known text; the parent run completes naturally.
2. **Depth cap denies (no unbounded nesting)** — at `subagent_depth == max_subagent_depth` the result is
   a normalized error and the counting factory built **0** child hosts; the parent run continues.
3. **Child depth = parent + 1** — a child spawned from depth 0 runs at depth 1 (asserted via the factory
   call / a depth-echoing child).
4. **Failure contained** — a child whose model raises (a `ScriptedFailure`) → a normalized error to the
   parent; the parent does not crash and can take another turn.
5. **Empty answer** — a child producing no assistant text → a clear normalized result, never a crash.
6. **Restricted toolset** — `allowed_tools=["read_file"]` → the child host registers only the allowlisted
   tool(s); a non-allowlisted tool is absent.
7. **Events not on the parent bus** — the parent's collected events contain no child loop events; the
   child events are only the metadata-only aggregation.
8. **Assembly gating** — `assemble`/`LoopPlaneHost` registers `spawn_subagent` iff `max_subagent_depth >=
   1`; absent at `0`.

## Public-safety

Committed sources + the doc contain no secret, private path, internal name, or IP (Principle VII). The
spawn result and all failure markers are public-safe English; raw exceptions never cross the boundary.
