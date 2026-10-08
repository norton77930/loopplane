# Implementation Plan: Subagent Fan-out Cap

**Branch**: `090-subagent-fanout-cap` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/090-subagent-fanout-cap/spec.md`

## Summary

Add `RuntimeConfig.max_subagent_fanout`. `None` counts nothing. A non-negative
integer is how many `spawn_subagent` children one root run may start. `drive`
creates one in-memory counter for that run and stamps it on `RunContext`.
Child hosts, including background, schedule, and swarm children, reuse that
object. The next root run starts another. The depth check stays first. No
event, checkpoint, HTTP route, extra, or existing default.

## Technical Context

**Language/Version**: Python 3.12 (repository baseline)
**Primary Dependencies**: none added
**Storage**: none. The counter is not checkpointed.
**Testing**: pytest with `ScriptedModel` and a direct adapter. No network.
**Target Platform**: the existing host assembly path
**Project Type**: library, opt-in host knob
**Performance Goals**: the check-and-increment does not await
**Constraints**: unset stays the current depth-only behavior; the denial sentence is fixed; other autonomy caps stay separate
**Scale/Scope**: one config field, one counter class, captured when work is admitted and passed into the child host

## Constitution Check

Pre-research and post-design: PASS.

- I: the maintainer selected this tail and the spec precedes the recorded tasks.
- II/IX: the count is the public gap sentence about tree size. No private reference material.
- III/IV: the tool stays a gateway adapter. Assembly only threads the counter.
- V: `spawn_subagent` is still registered and invoked only through the gateway.
- VI: no event or checkpoint change.
- VII: the denial is one fixed sentence and does not echo the task.
- VIII: no new dependency or extra.
- X: one focused RED test before the counter existed. Unset stays depth-only.

§E assessment: no existing default, event schema, checkpoint schema, gateway
SPI, or HTTP contract changes. The new field defaults to unset.

## Project Structure

### Documentation (this feature)

`spec.md`, `checklists/requirements.md`, `plan.md`, `research.md`,
`data-model.md`, `contracts/fanout-cap.md`, `quickstart.md`, `tasks.md`,
`implementation-evidence.md`.

### Source Code (repository root)

- `src/loopplane/host/config.py`: the field, mapping coercion, and validation.
- `src/loopplane/context.py`: `SubagentFanout` and `RunContext.subagent_fanout`.
- `src/loopplane/controller/controller.py`: create the counter in `drive` for a root run, or reuse the parent's object. Stamp it on that run's context.
- `src/loopplane/tools/subagent.py`: read the counter from `RunContext` after the depth check and pass that object into the child host.
- `src/loopplane/host/host.py`: forward a parent counter into `assemble`.
- `src/loopplane/host/assembly.py`: child-host builders take the captured counter as an argument. Do not create the counter there.
- `src/loopplane/tools/background.py`, `scheduling.py`, and `messaging.py`: capture the context counter when admitting work and pass it into the child host at build time.
- `tests/unit/test_subagent_spawn.py`: unset, cap, zero, depth-first, mapping, per-run reset, shared-counter checks, and a schedule child built after `drive` returns.

**Structure Decision**: the counter cannot live on frozen `RuntimeConfig`.
`drive` creates it for each root run. A child host receives the same object.
Default `None` keeps existing callers unchanged. `SubagentFanout` is not added
to `loopplane.tools.__all__`. The controller does not import `loopplane.tools`.

## Post-design Constitution Check

PASS. The implementation uses the structure above. No new gate fired.
