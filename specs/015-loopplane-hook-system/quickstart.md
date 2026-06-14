# Quickstart: Lifecycle Hooks

A credential-free walkthrough (scripted model) showing observation and gating.
The runnable form ships as `examples/hooks_quickstart.py`.

## 1. Build a registry and register hooks

```python
from loopplane.hooks import HookRegistry, LifecyclePoint
from loopplane.hooks import ToolGateDeny, ToolGateAllow

registry = HookRegistry()

# Observe every successful tool call (audit) — User Story 1.
audit: list[str] = []
def on_tool(payload):
    audit.append(payload.tool_name)
registry.register(LifecyclePoint.after_tool_use, on_tool)

# Gate: deny one tool by name — User Story 2.
def guard(payload):
    if payload.tool_name == "danger":
        return ToolGateDeny(reason="blocked by policy")
    return ToolGateAllow()
registry.register(LifecyclePoint.before_tool_use, guard)
```

## 2. Hand the registry to the runtime

```python
from loopplane.controller.controller import RuntimeController

controller = RuntimeController(
    model=scripted_model,        # the runtime's deterministic scripted model
    gateway=gateway,
    event_sink=sink,
    hooks=registry,              # the new optional seam — default is no hooks
)
```

## 3. Drive a session and observe

- Successful tool calls append to `audit` (observation, no behavior change).
- A call to `"danger"` never executes; it surfaces as a normalized denial with the
  hook's public-safe reason — exactly like an approval denial.
- A hook that raises never aborts the run; the failure appears once as a
  metadata-only `diagnostic` warning.

## 4. Default-inert

Omit `hooks=` entirely and the runtime behaves identically to before this feature
— no dispatch, no added latency (SC-003).

## What this is not

Hooks are not events: events are the fire-and-forget normalized stream consumers
read; hooks are synchronous interception points that may gate or modify. See
[contracts/integration-boundary.md](./contracts/integration-boundary.md).
