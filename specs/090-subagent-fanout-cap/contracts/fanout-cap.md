# Contract: Subagent Fan-out Cap

## Config

`RuntimeConfig.max_subagent_fanout: int | None = None`

`from_mapping` uses the existing non-negative optional integer coercion.
Omitted and JSON `null` stay `None`. `true`, `false`, a non-integer, and a
negative number raise `ConfigError`:

`max_subagent_fanout must be a non-negative integer`

## Tool

`spawn_subagent` stays registered only when `max_subagent_depth >= 1`.
The count does not register or unregister the tool.

Order inside the adapter:

1. If `context.subagent_depth >= max_subagent_depth`, return the existing
   depth denial. Do not take a slot.
2. If a counter is present and `try_take()` is false, return one
   `ErrorOutput` with category `POLICY_DENIAL` and message
   `subagent fan-out cap reached (N); refusing to spawn a subagent`.
   Do not build a child host. Do not include the task text.
3. Otherwise build the child and pass it that same counter. The count stays taken.

## Sharing

`drive` creates one counter per root run when the limit is set, or reuses the
parent's object, and stamps it on `RunContext.subagent_fanout`. The spawn
adapter reads that field and passes the same object into the child host.
Background, schedule, and swarm capture it when they admit work and pass that
object into the child host when the host is built, including after `drive`
returns. A child does not create a second one. A non-counter incoming object
raises `ConfigError`. `None` counts nothing.

`SubagentFanout` lives in `loopplane.context`. It is not a `loopplane.tools`
export.

## Out of scope

No event name, checkpoint key, HTTP route, phrase on an existing route, or
package extra.
