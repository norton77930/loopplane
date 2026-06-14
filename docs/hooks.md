# Lifecycle hooks

`loopplane.hooks` (unit 015) lets host and plugin code observe — and, at two
contracted points, gate or modify — the agent at well-defined lifecycle moments,
without forking the runtime. Hooks are additive and **inert by default**: with no
registry configured, every component runs its existing path with no added latency.

## The eleven lifecycle points

Nine are observational; two are **gating**.

| Point | When | Kind |
|---|---|---|
| `before_tool_use` | after approval, before a tool runs | gating |
| `after_tool_use` | after a tool succeeds | observe |
| `after_tool_failure` | after a tool raises or times out | observe |
| `file_changed` | after a successful non-read-only tool that names a path | observe |
| `user_prompt_submit` | before a prompt reaches the model | gating |
| `session_start` | a session's first drive | observe |
| `session_end` | on terminate / detach | observe |
| `process_setup` | once per runtime | observe |
| `subagent_start` / `subagent_stop` | around a delegated subagent run | observe |
| `model_stop` | when the model naturally stops | observe |

## Registering hooks

```python
from loopplane.hooks import HookRegistry, LifecyclePoint, ToolGateAllow, ToolGateDeny

registry = HookRegistry()

# Observe every successful tool call (sync or async callbacks both work).
registry.register(LifecyclePoint.after_tool_use, lambda p: print("ran", p.tool_name))

# Gate a tool call: allow, deny (with a public-safe reason), or modify the inputs.
def guard(payload):
    if payload.tool_name == "danger":
        return ToolGateDeny(reason="blocked by policy")
    return ToolGateAllow()
registry.register(LifecyclePoint.before_tool_use, guard)
```

## Wiring it into the runtime

Build one `HookDispatcher` from the registry and share it with the Tool Gateway,
the Runtime Controller, and (for subagent points) the orchestration Coordinator:

```python
from loopplane.hooks.dispatcher import HookDispatcher

dispatcher = HookDispatcher(registry)
gateway = ToolGateway(hooks=dispatcher)
controller = RuntimeController(model=model, gateway=gateway, event_sink=sink, hooks=dispatcher)
```

See [`examples/hooks_quickstart.py`](../examples/hooks_quickstart.py) for a complete
credential-free run.

## Semantics

- **Order & isolation** — hooks fire in registration order; a raising or slow hook
  is isolated (the run is never affected) and reported as a public-safe,
  metadata-only signal — never the raw exception, inputs, or paths.
- **Gating resolution** — across several gating hooks, any deny/block wins, and
  modifications/annotations compose in registration order. A raising or malformed
  gating hook **abstains** (the run proceeds as if it were absent); it never fails
  open and never aborts.
- **Boundaries** — tool hooks fire **inside** the Tool Gateway; a hook never
  resolves, authorizes, or executes a tool, and never re-emits the event bus.
  Hooks are distinct from the normalized Runtime Event Bus.

## Hooks vs. events

Events are the fire-and-forget normalized stream that consumers read on their own
side of the bus. Hooks are synchronous interception points that run inside the
agent's control flow and may, at the gating points, change what happens next.
