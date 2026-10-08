# Implementation Plan: Container Command Sandbox

**Branch**: `089-container-command-sandbox` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/089-container-command-sandbox/spec.md`

## Summary

Add an opt-in `DockerCommandExecutor` beside the existing command-executor seam.
The caller passes it to `InternalToolAdapter(command_executor=...)` with an image
name. Launches are built by one function that always sets the confinement flags.
The default adapter still constructs `HostCommandExecutor`. The `docker` extra
is lazy-imported and is the maintainer-approved package. No event, checkpoint,
HTTP route, or default change.

## Technical Context

**Language/Version**: Python 3.12 (repository baseline)
**Primary Dependencies**: optional `docker` extra; no base-dependency change
**Storage**: none
**Testing**: pytest with a stand-in container engine. No daemon.
**Target Platform**: a host that already runs `run_command` and has a local daemon when this executor is selected
**Project Type**: library, opt-in tool executor
**Performance Goals**: one container start per command; wall-clock kill on expiry
**Constraints**: default executor unchanged; errors are fixed sentences; image names are validated before any runtime call
**Scale/Scope**: one executor module, one extra, one ADR. Not a second gateway.

## Constitution Check

Pre-research and post-design: PASS.

- I: spec, plan, tasks, and the maintainer's selection of this P1 precede implementation.
- II/IX: behavior comes from gap G11 and ADR 0004 D6. No private reference material.
- III/IV: the executor stays inside the tools adapter. ADR 0022 records the pattern.
- V: the gateway remains the only `run_command` path. The executor is injected as it is today.
- VI: no event or checkpoint change.
- VII: `repr` is `DockerCommandExecutor()`. Failure text does not echo runtime exceptions.
- VIII: one maintainer-approved extra. The SDK is imported inside a function, with an injectable engine for tests (guard patterns ① and ②).
- X: one focused RED test before the executor exists. Unset selection stays the host executor.

§E assessment: the maintainer approved the new `docker` extra and ADR 0022 on
2026-10-08. No existing default, event schema, checkpoint schema, gateway SPI,
or HTTP contract changes.

## Project Structure

### Documentation (this feature)

`spec.md`, `checklists/requirements.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/container-executor.md`, `quickstart.md`, `tasks.md`,
`implementation-evidence.md`. ADR 0022 lives in `docs/adr/`.

### Source Code (repository root)

- `src/loopplane/tools/container.py`: the executor, the launch arguments, and the SDK engine.
- `src/loopplane/tools/__init__.py`: export the executor.
- `pyproject.toml`: the `docker` extra and the `all` extra membership.
- `tests/unit/test_container_executor.py`: confinement, timeout, and fail-closed checks.
- `tests/contract/test_packaging.py`: the pinned extra set includes `docker`.

**Structure Decision**: a new module owns the container backend. `execution.py`
keeps the host and POSIX executors, so the default path does not import an SDK.
