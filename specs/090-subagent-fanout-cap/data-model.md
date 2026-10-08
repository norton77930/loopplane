# Data Model: Subagent Fan-out Cap

## RuntimeConfig.max_subagent_fanout

- Type: `int | None`
- Default: `None`
- `None`: do not count `spawn_subagent` children.
- Integer `N >= 0`: one root run may start at most N of those children. The next root run starts a new count.
- `0`: refuse every spawn. Tool registration still follows `max_subagent_depth`.
- A boolean, a non-integer, or a negative value is a `ConfigError` with
  `max_subagent_fanout must be a non-negative integer`.
- Mapping key: `max_subagent_fanout`. Omitted means `None`.

## SubagentFanout

- Fields: `limit` (the configured N) and a private used-count starting at 0.
- `try_take()` returns false when used is already at the limit. Otherwise it
  increments and returns true. It does not await.
- One object per root run. Descendants of that run share it. The next run on the same host starts another. It is not a checkpoint field and not an event.
- A take stands after the child starts, including when that child later fails.
- Nothing decrements it.

## What does not change

- `RunContext.subagent_depth` stays the depth marker. It is not the count.
- Background, schedule, and swarm caps stay their own integers.
- No event field, checkpoint field, HTTP field, or dependency is added.
