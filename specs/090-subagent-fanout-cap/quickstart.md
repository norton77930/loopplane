# Quickstart: Subagent Fan-out Cap

Leave the field unset to keep today's depth-only behavior:

```python
RuntimeConfig(model=model, max_subagent_depth=2)
```

Allow three `spawn_subagent` children in one root run:

```python
RuntimeConfig(model=model, max_subagent_depth=2, max_subagent_fanout=3)
```

`max_subagent_fanout=0` keeps the tool registered when the depth is at least 1,
and refuses every spawn. A refusal looks like this and does not contain the
task:

```text
subagent fan-out cap reached (3); refusing to spawn a subagent
```

Background tasks, schedules, and swarm members still use
`max_background_tasks`, `max_schedules`, and `max_swarm_members`. Those numbers
are not added to the spawn count. A child they start uses the same spawn count
if it calls `spawn_subagent`. The next root run on the same host starts a new
count.
