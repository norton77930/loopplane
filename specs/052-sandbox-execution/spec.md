# Feature Specification: Sandboxed run_command Execution

**Feature Branch**: `052-sandbox-execution`

**Created**: 2026-06-20

**Status**: Draft — **plan authors the maintainer-approved [ADR 0004](../../docs/adr/0004-command-execution-isolation.md)**

**Input**: User description: "Sandboxed execution for the run_command tool: an injectable command-executor seam (default = the current host execution, byte-identical) plus a local-subprocess-jail backend (resource limits, environment scrubbing, working-scope confinement). Unit 052, Tier-3 (execution-safety & cost); closes gap G11. Maintainer-approved ADR 0004; v1 local-jail POSIX-real, docker deferred, Windows local-jail -> ConfigError."

## ⚠️ Boundary note (read first)

`run_command` today spawns an **unconfined host shell** (`anyio.run_process(cwd=working_scope)`)
— spec 009 FR-090 explicitly **reserved** "actual OS-level process/filesystem sandboxing or
containerization" as *named-not-built*. This unit un-reserves it, introducing a **runtime
execution-isolation model** (Constitution IV). The mechanism is recorded in the
**maintainer-approved ADR 0004**, authored at the plan step (no re-consult). Implementation is
**additive + default-off**: an injectable executor seam whose default is the current host
execution (byte-identical); the local-jail backend is opt-in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a command in a local sandbox (Priority: P1)

A host enables sandboxed execution so that when the agent runs a shell command, the command runs
in a **resource-limited, environment-scrubbed, working-scope-confined subprocess** instead of an
unconfined host shell — so a runaway or hostile command cannot exhaust the machine, read host
secrets from the environment, or trivially roam the filesystem.

**Why this priority**: This is gap G11 and the unit's core value — the reference harnesses
sandbox command execution; LoopPlane has decision-layer governance + working-scope path
confinement but `run_command` still executes unconfined on the host.

**Independent Test** (POSIX): with the local-jail executor, a command that tries to exceed a
resource limit (CPU / memory / output size / process count) is terminated and reported as a
contained failure; the command's environment does not contain scrubbed host secrets; the cwd is
the working scope. (On Windows the unit tests target the seam with a fake executor; the real jail
is validated on POSIX / WSL.)

**Acceptance Scenarios**:

1. **Given** the local-jail executor is enabled (POSIX), **When** the agent runs a normal command,
   **Then** it runs in the jailed subprocess (cwd = working scope, scrubbed env) and returns its
   output exactly as `run_command` does today.
2. **Given** the local-jail executor (POSIX), **When** a command exceeds a configured resource
   limit, **Then** it is terminated and surfaced as a normalized, public-safe failure (not a
   hang, not a host crash).

---

### User Story 2 - Default is unchanged; the seam is injectable (Priority: P2)

When sandboxing is not configured, `run_command` behaves **exactly as today** (the host
executor), byte-identical. The executor is an **injectable seam** so a host (or a test) can supply
the host executor, the local-jail executor, or a fake.

**Why this priority**: The change must impose nothing on hosts that did not ask for it, and must
keep the existing behavior + tests intact; the seam is also what makes the jail testable offline.

**Independent Test**: with no executor configured, `run_command` output + behavior are identical to
pre-052; a fake executor injected via the seam is used by `run_command` (proving the seam).

**Acceptance Scenarios**:

1. **Given** no sandbox configured (the default), **When** the agent runs a command, **Then** the
   behavior is byte-identical to today (the host executor).
2. **Given** a fake executor injected, **When** `run_command` runs, **Then** it dispatches through
   the injected executor (the seam is honored).

---

### User Story 3 - Honest cross-platform behavior; Gateway-owned (Priority: P3)

The local-jail's strong isolation primitives are POSIX-only. On Windows, requesting the
`local-jail` mode raises a **clear configuration error** rather than silently running a weak path
mislabelled as a sandbox. Execution stays owned by the Tool Gateway (the executor is an internal
detail of the tools-layer adapter, not a new execution path outside the Gateway).

**Why this priority**: Over-claiming isolation is a safety/honesty failure; and the runtime's
"single execution chokepoint" invariant (Constitution V) must hold.

**Independent Test**: on Windows, constructing the local-jail executor raises a `ConfigError` with
a clear message; the structural audit (`test_no_execution_path_outside_the_gateway`) stays green;
the default host path is unaffected on all platforms.

**Acceptance Scenarios**:

1. **Given** Windows, **When** the `local-jail` executor is requested, **Then** a clear
   `ConfigError` is raised (no weak/mislabelled sandbox).
2. **Given** any platform, **When** the code is audited, **Then** no tool execution path exists
   outside the Gateway (the executor is inside the tools-layer adapter).

---

### Edge Cases

- **command exceeds CPU / memory / output / process limits (POSIX)**: terminated + normalized
  failure (not a hang).
- **git/shell missing or spawn fails**: a normalized, public-safe error (the existing
  `run_command` failure shaping).
- **Windows + local-jail requested**: `ConfigError` at construction.
- **default (no sandbox)**: byte-identical to today.
- **scrubbed environment breaks a legitimate command**: the env allowlist is configurable +
  documented (resolved in planning) so toolchains can be permitted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `run_command` MUST dispatch shell execution through an **injectable command-executor
  seam** (a `CommandExecutor` interface) rather than inlining the subprocess spawn.
- **FR-002**: A default **host executor** MUST reproduce the current `run_command` execution
  (`anyio.run_process(cwd=working_scope)`) **byte-identically**, and MUST be the behavior when no
  sandbox is configured.
- **FR-003**: A **local-jail executor** MUST run the command in a subprocess with (POSIX):
  configurable **resource limits** (CPU time / address space / output / max processes),
  **environment scrubbing** to a minimal configurable allowlist, and **cwd + process-group
  confinement** to the working scope; a violation MUST be terminated and surfaced as a contained,
  public-safe failure (never a hang or host crash).
- **FR-004**: The feature MUST be **opt-in and default-off** (byte-identical when unconfigured):
  the executor is selected by the host; the default is the host executor.
- **FR-005**: On a platform lacking the strong isolation primitives (Windows), requesting the
  `local-jail` executor MUST raise a clear **configuration error** — it MUST NOT silently run a
  weakened path presented as a sandbox.
- **FR-006**: Execution MUST remain **owned by the Tool Gateway** (V): the executor is an internal
  detail of the tools-layer adapter; the structural audit that no execution path exists outside
  the Gateway MUST stay green (the controller/loop MUST NOT import the tools layer).
- **FR-007**: Failures MUST be **contained + public-safe** (VII): a terminated/over-limit/failed
  command yields a normalized error consistent with the existing `run_command` shaping; no raw
  internals beyond the existing convention.
- **FR-008**: The mechanism MUST be recorded in **ADR 0004** (maintainer-approved), authored at
  the plan step; v1 = local-jail (POSIX-real), **docker DEFERRED** (a future executor behind an
  optional extra). No new required runtime dependency for v1 (stdlib `resource`/`os`).

### Key Entities *(include if feature involves data)*

- **CommandExecutor**: the injectable interface for running a shell command (command + cwd + a
  per-call config → exit code / stdout / stderr).
- **HostCommandExecutor**: the default — the current `anyio.run_process` call verbatim.
- **LocalJailCommandExecutor**: the POSIX sandbox — rlimits + env-scrub + cwd/process-group
  confinement; raises `ConfigError` on a platform without the primitives.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the local-jail executor (POSIX), a normal command returns identical output to
  the host executor, and an over-limit command is terminated + reported as a contained failure in
  100% of covered scenarios.
- **SC-002**: With no sandbox configured, `run_command` behavior is byte-identical to today — the
  existing test suite passes unchanged; a fake executor injected via the seam is honored.
- **SC-003**: On Windows, requesting `local-jail` raises a clear `ConfigError`; the
  no-execution-outside-the-Gateway audit stays green on all platforms.
- **SC-004**: No new required runtime dependency; docker remains deferred; ADR 0004 records the
  model.

## Assumptions

- The executor seam lives in the tools layer (a new `loopplane.tools.execution` module) and is
  injected into the `InternalToolAdapter` via a ctor param (the `memory_store` / `max_file_snapshots`
  pattern), since `InternalToolAdapter` is caller-constructed and passed via
  `RuntimeConfig.tool_adapters`. The exact selection wiring (ctor param vs a thin `RuntimeConfig`
  helper) is settled at plan.
- v1 jail uses stdlib `resource`/`os` (POSIX `preexec_fn` → `setrlimit` + `setsid`); **no docker**,
  no new dependency. The env allowlist + limit values are configurable with safe defaults.
- The dev/CI host is Windows 11 → the real jail is validated on POSIX / WSL; Windows unit tests
  use a fake executor through the seam. Windows `local-jail` requests raise `ConfigError`.
- Out of scope: docker/container execution (deferred), network namespace isolation, seccomp/BPF
  filtering, and any non-`run_command` tool sandboxing.
- Default-off; contained; Gateway-owned (V); public-safe (VII). Per Constitution IX the concept is
  borrowed from the reference harnesses but re-derived; X keeps it additive + reversible.
