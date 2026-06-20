# ADR 0004: run_command execution-isolation model

- **Status**: Accepted (2026-06-20)
- **Deciders**: LoopPlane maintainer (approved during the Tier-3 plan boundary review);
  spec 052 (sandbox-execution).
- **Supersedes / superseded by**: none. Fourth ADR in the repository (after 0001, 0002, 0003).
- **Related**: Constitution **IV** (Runtime Boundary Clarity — this introduces a new *runtime
  execution-isolation pattern* for an existing tool, recorded here), **V** (Tool Gateway
  ownership — the executor is an implementation detail INSIDE the tools-layer adapter; the
  Gateway stays the single execution chokepoint), **VII** (public-safe / contained failures),
  **X** (additive, default-off, byte-identical when unconfigured; reversible), **IX**
  (reference-not-clone). **Un-reserves spec 009 FR-090** (which named OS-level sandboxing as
  *not-built*). Reuses the unit-044/054 caller-injected-ctor pattern.

## Context

`run_command` (the Tool Gateway's shell tool, `InternalToolAdapter._run_command`,
`internal.py:656`) spawns an **unconfined host shell** —
`anyio.run_process(command, cwd=context.working_scope, check=False)`. The cwd is the working
scope, but nothing enforces it: a command can `cd ..`/use absolute paths, read/write anywhere the
host user can, inherit the **full host environment** (secrets), spawn unbounded CPU/memory/
processes, and reach the network. This is asymmetric with the file tools, which confine paths via
`_resolve`. The decision layer (spec 009) gates allow/deny *before* execution but OS-sandboxes
nothing — **009 FR-090 explicitly RESERVED** "actual OS-level process/filesystem sandboxing or
containerization" as *named-not-built*. Gap G11 (vs the reference harnesses, which sandbox
command execution) is to build it.

Building it changes **how an existing tool's work is executed** (host shell → a resource-limited,
env-scrubbed, filesystem-confined subprocess) — a runtime execution-isolation model (Constitution
IV), and it un-reserves a documented reservation. By repo precedent (ADR 0002 background, ADR 0003
messaging both STOPPED for maintainer approval before introducing a new execution pattern), this
is ADR-gated even though the mechanism is mechanically additive.

## Decision

- **D1 — An injectable `CommandExecutor` seam.** `run_command` dispatches shell execution through
  a `CommandExecutor` interface (`async run(command, *, cwd) -> CommandResult`) instead of
  inlining the subprocess spawn. The default `HostCommandExecutor` reproduces the **current**
  call verbatim (`anyio.run_process(command, cwd=cwd, check=False)`), so the default path is
  **byte-identical**; `_run_command`'s output shaping (stdout `TextBlock`; non-zero exit →
  `ErrorOutput`; `OSError` → "cannot run command") is unchanged.
- **D2 — Default-off, caller-injected.** The executor is injected into `InternalToolAdapter` via
  an optional ctor param (the `memory_store` / `max_file_snapshots` pattern — the adapter is
  caller-built and passed via `RuntimeConfig.tool_adapters`). The default is the host executor;
  the local-jail is **opt-in**. Unconfigured runs are byte-identical.
- **D3 — `LocalJailCommandExecutor` (POSIX).** Runs the command in a subprocess with: configurable
  **resource limits** (CPU time / address space / output / max processes via `resource.setrlimit`
  in a `preexec`), **environment scrubbing** to a minimal configurable allowlist (e.g. PATH/HOME/
  LANG; host secrets dropped), and **cwd + process-group confinement** (`setsid`) to the working
  scope. A violation is **terminated** and surfaced as a contained, public-safe failure (never a
  hang or host crash).
- **D4 — Cross-platform honesty.** The strong primitives are POSIX-only. On a platform lacking
  them (Windows), constructing `LocalJailCommandExecutor` raises a clear **`ConfigError`** — the
  runtime MUST NOT silently run a weakened path presented as a sandbox. The dev/CI host is Windows
  11, so the real jail is validated on POSIX / WSL; Windows unit tests target the seam with a
  **fake executor**.
- **D5 — The Gateway stays the single execution chokepoint (V).** The executor is an
  implementation detail **inside** the tools-layer adapter (`loopplane.tools`). The
  controller/loop do not import the tools layer and no tool execution path exists outside the
  Gateway — the `test_no_execution_path_outside_the_gateway` audit is **untouched**.
- **D6 — docker DEFERRED; v1 stdlib-only.** v1 is the local-subprocess jail using stdlib
  `resource`/`os` — **no new runtime dependency**. A docker/container executor (a future
  `CommandExecutor` behind an optional extra + a daemon prerequisite) is deferred. No event-schema
  / `SCHEMA_VERSION` / content-model change (run_command output stays `TextBlock`/`ErrorOutput`).

## Consequences

- **Closes G11**: opt-in OS-level isolation for `run_command` (resource limits + env-scrub +
  filesystem/process confinement), while staying contained, Gateway-owned, and default-off.
- **A new, documented execution-isolation pattern** (IV): an injectable per-adapter command
  executor. Additive + reversible (default-off → revert by removing the seam + the jail executor +
  the optional ctor param). Un-reserves 009 FR-090 deliberately, recorded here.
- **Honest cross-platform posture**: POSIX-real isolation; Windows `local-jail` → `ConfigError`
  (no over-claimed sandbox). The seam keeps the default + the jail offline-testable (a fake
  executor); the real jail is POSIX/WSL-validated.
- **Deferred (documented follow-ups)**: docker/container execution, network-namespace isolation,
  seccomp/BPF syscall filtering, and sandboxing of tools other than `run_command`. These remain
  out of scope unless a future unit + ADR revisits them.
