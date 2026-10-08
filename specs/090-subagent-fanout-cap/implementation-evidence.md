# Implementation Evidence: Subagent Fan-out Cap

**Date**: 2026-10-08
**Branch**: `090-subagent-fanout-cap` (parent `942f53a`)
**Status**: Implemented. Not Verified. Not committed. Not published.

## Behavior in this tree

- `RuntimeConfig.max_subagent_fanout` defaults to `None`.
- `None` does not count. Integer `N >= 0` is how many `spawn_subagent` children one root run may start, including descendants. The next root run starts a new count.
- `drive` creates a fresh `SubagentFanout` when the limit is set and no parent counter was passed. A child reuses that object. The spawn adapter reads `RunContext.subagent_fanout` and does not keep its own counter.
- Depth denial returns before `try_take`.
- Count denial is `POLICY_DENIAL` with
  `subagent fan-out cap reached (N); refusing to spawn a subagent`.
- Spawn, background, schedule, and swarm capture `RunContext.subagent_fanout` when they admit work and pass that object into the child host. A scheduled child built after `drive` returns still uses it. A child does not create another. A foreign object raises `ConfigError`. There is no `FanoutSlot`.

## Checks run

- RED, before any counter existed: the tree-cap test failed with
  `RuntimeConfig.__init__() got an unexpected keyword argument 'max_subagent_fanout'`,
  and the direct denial test failed with `cannot import name 'SubagentFanout'`.
- RED, after the counter was created once in `assemble`: `test_fanout_resets_on_the_next_run` failed with `assert 'failure' == 'success'` on the second `host.run`.
- After the per-run wiring, and before this admit-time capture: the same three files were **43 passed** in 5.47s. That run did not cover a child built after `drive` returned.
- RED for the cleared slot: `test_late_schedule_child_keeps_the_run_counter` failed with `assert 'scheduled task failed' == 'child finished'`.
- After capturing the counter at admit time: `uv run pytest -q --tb=line tests/unit/test_subagent_spawn.py tests/unit/test_agent_messaging.py tests/unit/test_agent_scheduling.py tests/unit/test_background_tasks.py tests/contract/test_tools_boundary.py` → **70 passed** in 13.41s.
- `uv run mypy src` → no issues in 231 source files.
- `uv run ruff check` and `ruff format --check` passed on the touched Python files after an import sort in the spawn test and a format of `background.py`.
- The full pytest suite was not re-run. Do not treat the 089 figure
  (2422 passed / 33 skipped) as coverage for this unit.

## Line counts

`controller.py` and `host.py` were already over 1000 before this unit. This
fix removes `FanoutSlot` and does not split those files.

## Agent context

`.specify/feature.json` points at `specs/090-subagent-fanout-cap`. The
PowerShell agent-context updater was not re-run. `AGENTS.md` and `CLAUDE.md`
name `specs/090-subagent-fanout-cap/plan.md` by the same one-line edit used for
089.
