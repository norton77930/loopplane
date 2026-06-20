# Phase 1 Data Model: Dynamic Subagents (043)

All additions are additive. No existing type's behavior changes; no event-schema or content-model change.

## New / modified runtime state

### `RunContext.subagent_depth: int` (MODIFIED — additive field)

`src/loopplane/context.py`. The per-run recursion depth.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `subagent_depth` | `int` | `0` | The nesting depth of this run. `0` = a top-level (host-driven) run. A child run spawned by `spawn_subagent` has `parent.subagent_depth + 1`. |

Constructed only in `RuntimeController.drive()` (the single `RunContext` construction site), from the
controller's `subagent_depth` (default `0`). Per-run, never process-global.

### `RuntimeConfig.max_subagent_depth: int` (MODIFIED — additive field)

`src/loopplane/host/config.py`. The hard recursion cap.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `max_subagent_depth` | `int` | `0` | The maximum `subagent_depth` at which `spawn_subagent` is permitted. A spawn is **denied** when `context.subagent_depth >= max_subagent_depth`. **`0` (the default) → the tool is NOT registered** (feature off, byte-identical to today). `1` → exactly one level of nesting (a top-level run may spawn; the child may not). |

- `from_mapping` coerces it (`int(data.get("max_subagent_depth", 1))`).
- `validate_config` requires `max_subagent_depth >= 0` (a negative cap is a `ConfigError`).
- Carries no secret (a bare integer).

### `RuntimeController(subagent_depth: int = 0)` (MODIFIED — additive kwarg)

`src/loopplane/controller/controller.py`. The controller's current depth, stamped onto each run's
`RunContext` in `drive()`. Default `0` keeps every existing controller byte-identical.

## New tool

### `spawn_subagent` (tool descriptor)

Registered by `SpawnSubagentAdapter` (`src/loopplane/tools/subagent.py`), through the Tool Gateway.

| Descriptor field | Value |
|---|---|
| `name` | `"spawn_subagent"` |
| `description` | Runs one focused child agent to completion and returns its final answer. Use for a self-contained sub-task; the child runs once and cannot run indefinitely or spawn without bound. |
| `input_schema` | object with required `task: string`; optional `allowed_tools: string[]`; `additionalProperties: false` |
| `read_only` | `False` (it runs an agent that may use non-read-only tools) |
| `network` | `False` |
| `concurrency_safe` | `False` |

**Input**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `task` | `string` | yes | The natural-language sub-task the child agent should perform. |
| `allowed_tools` | `string[]` | no | Restrict the child's tools to this allowlist (intersected with the parent's tools). Omitted → the child inherits the parent's tools. |

**Output (the gateway result)**

- **Success**: a `TextBlock` whose text is the child's **final assistant message** (optionally followed
  by a short metadata-only line, e.g. the captured child loop-event count). The Gateway wraps it as a
  `ToolResultBlock(outcome="success")`.
- **Denied (depth cap)** / **failure**: an `ErrorOutput` (normalized by the Gateway into a
  `ToolResultBlock(outcome="failure")` with a `NormalizedError`). Public-safe message; no raw exception.

## Adapter internal types (not public API)

### `SpawnSubagentAdapter` (a `gateway.spi.ToolAdapter`)

| Constructor parameter | Type | Meaning |
|---|---|---|
| `build_child_host` | `Callable[[int, tuple[str, ...] | None], LoopPlaneHost]` | Builds a fresh child `LoopPlaneHost` for a given child depth + optional tool allowlist (injected by `assemble`; typed under `TYPE_CHECKING` to avoid a `tools → host` cycle). |
| `max_subagent_depth` | `int` | The cap (from `RuntimeConfig.max_subagent_depth`). |

Implements `describe()` (the single descriptor), `invoke(name, call_input, context)` (the depth check →
build a one-shot `LoopDefinition` → `run_loop` → recover final text / normalize failure), and
`shutdown()`.

## Reused (unchanged) types

- `loopplane.engineering`: `run_loop`, `LoopDefinition`, `HostRuntimeProfile`, `StaticInput`,
  `ManualTrigger`, `ValidationPolicy`, `ObservationPolicy`, `stop_on_pass`, `max_iterations`,
  `LoopOutcome`, `RunReference`, `ValidationResult`.
- `loopplane.orchestration`: `aggregate_events`, `SubagentResult` (to wrap the child outcome for the
  metadata-only event view — reused, not modified).
- `loopplane.gateway.spi`: `ToolAdapter`, `AdapterOutput`, `ErrorOutput`; `loopplane.errors
  .ErrorCategory`.
- `loopplane.model`: `ToolDescriptor`, `TextBlock`; `loopplane.host`: `LoopPlaneHost`, `RuntimeConfig`
  (the child host); `loopplane.loop.history.HistoryEntry` (final-text recovery).

## State transitions (depth)

```text
top-level run            subagent_depth = 0
  └─ spawn_subagent ──► allowed iff 0 < max_subagent_depth
        child run        subagent_depth = 1
          └─ spawn_subagent ──► allowed iff 1 < max_subagent_depth
               (with max = 1 ⇒ DENIED, no grandchild run created)
```
