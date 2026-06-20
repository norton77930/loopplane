# Implementation Plan: Sandboxed run_command Execution

**Branch**: `052-sandbox-execution` (main-only autopilot) | **Date**: 2026-06-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/052-sandbox-execution/spec.md`

**Boundary review**: settled by **[ADR 0004](../../docs/adr/0004-command-execution-isolation.md)**
(maintainer-approved at the Tier-3 boundary review; authored at this plan step, no re-consult). A
new runtime execution-isolation pattern, implemented **additively + default-off** (an injectable
executor seam whose default is the current host execution → byte-identical).

## Summary

`run_command` dispatches shell execution through an injectable `CommandExecutor` seam
(`loopplane.tools.execution`) instead of inlining `anyio.run_process`. The default
`HostCommandExecutor` is the **current call verbatim** (byte-identical); a `LocalJailCommandExecutor`
(POSIX) adds resource limits (`resource.setrlimit` in a preexec) + environment scrubbing (a minimal
allowlist) + cwd/process-group (`setsid`) confinement. The executor is injected into
`InternalToolAdapter` via an optional ctor param (the `memory_store` / `max_file_snapshots`
pattern); the default is the host executor → unconfigured runs are byte-identical. On Windows the
`LocalJailCommandExecutor` raises `ConfigError` (no mislabelled weak sandbox). Execution stays
**Gateway-owned** (the executor is an impl detail inside the tools-layer adapter; the
no-execution-outside-gateway audit is untouched). v1 = local-jail POSIX-real, **docker DEFERRED**,
stdlib-only (no new dependency); no event-schema / content-model change.

## Technical Context

**Language/Version**: Python 3.11+; stdlib `resource` / `os` (POSIX) + `anyio` (existing).

**Primary Dependencies**: none new — reuses `anyio.run_process`, the existing `_run_command` output
shaping, and the `InternalToolAdapter` ctor-injection pattern.

**Storage**: none.

**Testing**: pytest, offline. On Windows (the dev/CI host) the seam + `HostCommandExecutor`
byte-identity + the Windows `ConfigError` + the env-scrub construction are unit-tested with a
**fake executor** through the seam; the real POSIX jail (rlimit termination, env-scrub, confinement)
is validated on POSIX / WSL (a `skipif(not POSIX)` real-jail test).

**Target Platform**: cross-platform library; the local-jail is POSIX-real, Windows → `ConfigError`.

**Constraints**: additive / reuse-first; default-off byte-identical; Gateway-owned (V); contained +
public-safe (VII); no event-schema/content-model change (VI); no new dependency; ADR 0004.

**Scale/Scope**: a new `loopplane.tools.execution` module (`CommandExecutor` Protocol +
`CommandResult` + `HostCommandExecutor` + `LocalJailCommandExecutor`) + a `_run_command` refactor
to call the injected executor + an `InternalToolAdapter(command_executor=…)` ctor param + export +
api-reference + tests. POSIX-specific subprocess mechanics — the hardest Tier-3 unit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Spec-First**: Traces to `spec.md` FR-001…FR-008 + ADR 0004. ✅
- **III. Agent Harness Before Loop Automation**: An opt-in execution-safety primitive (default-off);
  not the loop-automation layer. ✅
- **IV. Runtime Boundary Clarity**: The new execution-isolation pattern is recorded in ADR 0004; the
  seam is an internal detail of the tools-layer adapter. ✅
- **V. Tool Gateway Ownership**: The executor is inside the Gateway-owned adapter; no execution path
  outside the Gateway (the audit stays green); the controller/loop do not import the tools layer. ✅
- **VI. Event Bus Ownership**: No event-schema / `SCHEMA_VERSION` / content-model change (run_command
  output stays `TextBlock`/`ErrorOutput`). ✅
- **X. Testable Evolution**: Additive; default (host executor) byte-identical; reversible;
  offline-tested via the seam (a fake executor) + a POSIX-gated real-jail test. ✅

**Result**: PASS — the one boundary crossing (a runtime execution-isolation model) is
**maintainer-approved and recorded in ADR 0004**, implemented additively + default-off; no breaking
001/002 contract change, no event-bus change. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/052-sandbox-execution/
├── plan.md · spec.md · research.md · data-model.md · quickstart.md
├── contracts/command-executor.md
└── checklists/requirements.md
docs/adr/0004-command-execution-isolation.md   # the approved boundary decision
```

### Source Code (repository root)

```text
src/loopplane/tools/
└── execution.py        # NEW: CommandResult + CommandExecutor Protocol +
                        #      HostCommandExecutor (current call verbatim) +
                        #      LocalJailCommandExecutor (POSIX; Windows -> ConfigError)

src/loopplane/tools/internal.py     # MODIFIED: + command_executor ctor param (default
                                    #   HostCommandExecutor); _run_command calls self._executor
src/loopplane/tools/__init__.py + docs/api-reference.md   # MODIFIED: export + document the
                                    #   new public names (CommandExecutor / the executors)
tests/unit/test_sandbox_execution.py # NEW: seam + host byte-identity + Windows ConfigError +
                                     #   env-scrub + a POSIX-gated real-jail test
```

**Structure Decision**: The seam + executors live in a new `loopplane.tools.execution` module
(NOT in `governance/` — 009 is decision-only). `InternalToolAdapter` gains
`command_executor: CommandExecutor | None = None` (default → `HostCommandExecutor()`), the
`memory_store` / `max_file_snapshots` ctor-injection shape, so the caller (who builds the adapter
and passes it via `RuntimeConfig.tool_adapters`) opts into the jail. `_run_command` becomes a thin
call into the executor; its output shaping is unchanged → byte-identical default.

## Complexity Tracking

> No unjustified complexity. The single boundary crossing (a runtime execution-isolation model) is
> justified by ADR 0004 (maintainer-approved) and gated default-off; the Gateway/loop/event/content
> contracts are unchanged. Not a Constitution violation.
