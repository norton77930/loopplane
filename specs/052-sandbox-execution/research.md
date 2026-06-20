# Research: Sandboxed run_command Execution

The boundary question (the execution-isolation model) is settled by
**[ADR 0004](../../docs/adr/0004-command-execution-isolation.md)** (maintainer-approved). Decisions
below record the resulting design; no open `NEEDS CLARIFICATION`.

## Decision 1 — An injectable CommandExecutor seam (ADR 0004 D1)

**Decision**: Define `CommandResult(returncode: int, stdout: bytes, stderr: bytes)` + a
`CommandExecutor` Protocol (`async run(command: str, *, cwd: Path) -> CommandResult`) in a new
`loopplane.tools.execution` module. `_run_command` calls `self._executor.run(command,
cwd=context.working_scope)` and keeps its exact output shaping (stdout `TextBlock`; non-zero exit →
`ErrorOutput`; `OSError` → "cannot run command").

**Rationale**: A seam is the minimal additive change; it makes the default byte-identical AND makes
the jail offline-testable (a fake executor).

**Alternatives considered**: inlining sandbox logic into `_run_command` (rejected — not testable,
not swappable, couples the adapter to one isolation strategy).

## Decision 2 — HostCommandExecutor = the current call verbatim (ADR 0004 D1/D2)

**Decision**: `HostCommandExecutor.run` is `completed = await anyio.run_process(command, cwd=cwd,
check=False); return CommandResult(completed.returncode, completed.stdout, completed.stderr)`. It
is the **default** when no executor is injected → unconfigured runs are byte-identical. The
`OSError` propagates and is caught by `_run_command` exactly as today.

**Rationale**: Byte-identity (Constitution X) — the existing `run_command` tests + behavior hold
unchanged.

## Decision 3 — Caller-injected ctor param (not a RuntimeConfig knob) (ADR 0004 D2)

**Decision**: `InternalToolAdapter.__init__(..., command_executor: CommandExecutor | None = None)`
(default → `HostCommandExecutor()`), the `memory_store` / `max_file_snapshots` injection shape. The
caller (who builds the adapter + passes it via `RuntimeConfig.tool_adapters`) supplies the jail
executor to opt in.

**Rationale**: `InternalToolAdapter` is caller-built (assembly registers it as-is); a RuntimeConfig
field would be a dead knob. Consistent with units 044/054.

## Decision 4 — LocalJailCommandExecutor (POSIX) (ADR 0004 D3/D4)

**Decision**: On POSIX, run the command in a subprocess with: `resource.setrlimit` (CPU seconds /
address space / file size / max processes) applied in a `preexec_fn`, a **scrubbed environment**
(a minimal configurable allowlist — e.g. PATH/HOME/LANG; host secrets dropped), and `setsid` +
`cwd=working_scope` for process-group + cwd confinement. A limit violation terminates the process
(killed) and is surfaced as a contained, public-safe failure. On a platform without these
primitives (Windows), `__init__` raises `ConfigError` (ADR 0004 D4) — no mislabelled weak path.

**Rationale**: The strongest stdlib-only POSIX isolation; honest on Windows. The dev/CI host is
Windows, so the real jail is POSIX/WSL-validated; Windows unit-tests use a fake executor.

**Open implementation detail (for tasks/implement)**: whether to drive the preexec via
`anyio.run_process` kwargs, `anyio.open_process`, or `anyio.to_thread.run_sync(subprocess.run,
preexec_fn=…)`; whichever cleanly applies `setrlimit`/`setsid` + captures output. The seam keeps
this internal.

## Decision 5 — Gateway-owned; no contract change (ADR 0004 D5/D6)

**Decision**: The executor lives in the tools layer and is reached only inside the Gateway-owned
`InternalToolAdapter`; the controller/loop do not import it. No event-schema / `SCHEMA_VERSION` /
content-model change; no new dependency (stdlib only); docker DEFERRED.

**Rationale**: Keeps Constitution V (single execution chokepoint — the audit stays green) + VI + X.

## Decision 6 — Public surface

**Decision**: Export `CommandExecutor`, `CommandResult`, `HostCommandExecutor`,
`LocalJailCommandExecutor` from `loopplane.tools` (so a host can construct the jail) + document them
in `docs/api-reference.md` (the unit-014 bijection).

**Rationale**: The host needs the executor types to opt in; the api-reference bijection must stay
exact.
