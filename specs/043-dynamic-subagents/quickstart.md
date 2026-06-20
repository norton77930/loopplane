# Quickstart: Dynamic Subagents (043)

Let the model delegate a focused sub-task to a **one-shot** child agent, under a hard recursion cap.

## Enable it

`spawn_subagent` is registered when the runtime opts in with a non-zero `max_subagent_depth` (the
default is `0` = off; set it to `1` to enable exactly one level of nesting):

```python
from loopplane.host import LoopPlaneHost, RuntimeConfig

config = RuntimeConfig(
    model=my_model,
    # ... your tools / adapters ...
    max_subagent_depth=1,   # 0 disables the feature (the tool is not registered)
)
host = LoopPlaneHost(config)
```

Now the model has a `spawn_subagent` tool. It calls it like any other tool:

```json
{ "task": "Read CONTRIBUTING.md and summarize the PR checklist in 3 bullets.",
  "allowed_tools": ["read_file"] }
```

The runtime runs **one** bounded child agent to completion (through the existing Phase-3 `run_loop`) and
returns the child's **final answer** as the tool result. The parent uses it and continues.

## What you get / what is guaranteed

- **One-shot**: the child runs once and returns; there is no persistent handle, no peer messaging, no
  swarm (those are deferred).
- **Bounded recursion**: a child runs at `parent_depth + 1`. At/over `max_subagent_depth`, a further
  `spawn_subagent` is **denied** with a normalized error and **no** child run starts — subagents cannot
  recurse without bound. With `max_subagent_depth=1` (the default `0` leaves the feature off), the child cannot spawn a grandchild.
- **Failure-contained**: a child that errors, over-runs, fails validation, or returns nothing yields a
  **normalized** error to the parent (a public-safe marker, never a raw exception); the parent run never
  crashes.
- **Least privilege (optional)**: `allowed_tools` restricts the child to a named subset of the parent's
  tools.
- **Clean event bus**: the child's events are **captured** (consumed as metadata-only aggregation),
  never re-emitted onto the parent's live event stream (Constitution VI). The parent's `spawn_subagent`
  call is an ordinary tool-call event pair — the event schema is unchanged.

## Disable / roll back

Set `max_subagent_depth=0` (or do not opt in): the tool is not registered, the model cannot call it, and
every existing run is byte-identical to today.

## Notes

- `spawn_subagent` traverses the full Tool Gateway (resolve → validate → decide → execute-under-timeout →
  normalize), like every tool. There is no privileged bypass.
- The child is driven by the **existing** public `run_loop` — the same entry point unit-013's
  host-driven coordinator composes. This unit adds **no** agent-loop, controller, gateway, or
  event-schema behavior; it is purely additive.
