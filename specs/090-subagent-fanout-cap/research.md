# Research: Subagent Fan-out Cap

## Decision: one in-memory object, not a config field that mutates

`RuntimeConfig` is frozen. A mutable count cannot be stored on it, and
`dataclasses.replace` for a child would copy a number rather than share a
counter. `drive` creates one `SubagentFanout` at the start of each root run
when the field is a non-negative integer, and stamps it on that run's
`RunContext`. The next root run on the same host starts another. A child host
receives that same object and does not create a second one.

Unset (`None`) creates no object. Those runs do not count.

## Decision: depth stays first

The existing depth refusal returns before `try_take`. A spawn that is already
too deep does not consume a slot, so a later in-depth spawn can still use it.

## Decision: background, schedule, and swarm share the object

Those features keep `max_background_tasks`, `max_schedules`, and
`max_swarm_members`. They are not spawn-count increments. Their child hosts
can still call `spawn_subagent`. Giving each of them a new counter would let
the run exceed N. The tool that admits them captures
`RunContext.subagent_fanout` at that moment and passes that object into the
child host when the host is built, including after `drive` has returned.

## Decision: no checkpoint and no event

The count is process-local. Resume does not restore it. Nothing is added to
the event envelope or the checkpoint schema.

## Decision: the denial is one sentence

`subagent fan-out cap reached (N); refusing to spawn a subagent`

The task is read only after the count is taken. A refusal cannot echo it.

## Alternatives rejected

- Store the count on the checkpoint. That is a schema change, which this unit
  does not have approval to make.
- Decrement when a child finishes. The operator's number is how many children
  the tree may start, not how many may be alive at once.
- Fold background, schedule, and swarm admits into the same number. Their caps
  already exist and were not part of this approval.
- Create the counter once in `assemble`. That object would survive every later
  run on the same host, including a host reused from the tenant pool. The
  count is per root run.
- Leave the counter in a slot that `drive` clears before it returns. Background,
  schedule, and swarm build the child host later, so a cleared slot makes that
  child mint a second counter. The next root run can also overwrite the slot,
  and a late child of the first run then joins the second count.
