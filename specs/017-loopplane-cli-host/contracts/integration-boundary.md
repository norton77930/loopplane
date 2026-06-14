# Contract: CLI Integration Boundary

How the CLI composes the runtime **without changing any contract**. The CLI depends
only on the public `loopplane.host` interface and the public event envelope; it
reaches no runtime internal.

## Over `loopplane.host` (units 001/002)

- `run` / `chat` build a `LoopPlaneHost` from a `RuntimeConfig` and call
  `host.run(prompt, on_event=renderer)`. The host owns the controller, gateway, and
  event bus; the CLI only supplies the prompt and an `EventSink` renderer.
- `sessions` / `resume` call `host.list_sessions()` / `host.resume(id)`.
- The CLI executes **no** tool (tools run through the gateway behind the host —
  Constitution V) and re-emits **no** event bus (it is a consumer of the normalized
  stream — Constitution VI).

## Model boundary (unit 001)

`select_model` returns a `loopplane.model.ModelBoundary` — the built-in scripted demo
by default, or an imported builder. The CLI constructs the model and hands it to
`RuntimeConfig`; it implements no provider itself in this unit.

## Packaging

- The only packaging change is `[project.scripts] loopplane = "loopplane.cli:main"`.
- No new runtime dependency; a real provider is an optional extra.
- `py.typed` and every subpackage still ship (unit-014 packaging contract unchanged).

## Non-goals on this boundary

- No existing unit gains a parameter or a contract change.
- The CLI adds no runtime behavior; with the command unused, the runtime is identical.
