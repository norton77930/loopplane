# Data Model: Sandboxed run_command Execution

Per [ADR 0004](../../docs/adr/0004-command-execution-isolation.md). Additive; a new tools-layer
seam + an `InternalToolAdapter` ctor param. No new content block / event / RunContext field.

## CommandResult (new)

| Field | Type | Notes |
| ----- | ---- | ----- |
| `returncode` | int | Process exit code. |
| `stdout` | bytes | Raw stdout (decoded by `_run_command` as today). |
| `stderr` | bytes | Raw stderr (decoded by `_run_command` as today). |

## CommandExecutor (new Protocol)

| Method | Signature | Notes |
| ------ | --------- | ----- |
| `run` | `async (command: str, *, cwd: Path) -> CommandResult` | Runs a shell command in a cwd; raises `OSError` on spawn failure (caught by `_run_command` as today). |

## HostCommandExecutor (new — the default)

- `run` = `anyio.run_process(command, cwd=cwd, check=False)` → `CommandResult(...)`. The current
  behavior verbatim; the default when no executor is injected → byte-identical.

## LocalJailCommandExecutor (new — POSIX)

| Member | Type | Notes |
| ------ | ---- | ----- |
| limits | resource limits | CPU seconds / address space / file size / max processes (`setrlimit` in a preexec). Configurable with safe defaults. |
| env allowlist | `tuple[str, ...]` | The env vars kept (e.g. PATH/HOME/LANG); everything else dropped. Configurable. |
| (POSIX guard) | — | `__init__` raises `ConfigError` on a platform without the primitives (Windows). |

- `run`: spawn with `cwd=cwd`, scrubbed `env`, `setsid` + the rlimit preexec; a limit violation →
  terminated → a `CommandResult` with a non-zero code (surfaced as a contained failure), never a
  hang/raise-through.

## InternalToolAdapter.command_executor (new ctor param)

- `command_executor: CommandExecutor | None = None` (default → `HostCommandExecutor()`), stored as
  `self._executor`. The `memory_store` / `max_file_snapshots` injection shape. `_run_command` calls
  `self._executor.run(...)`.

## Rules (from FRs + ADR 0004)

| Rule | Source |
| ---- | ------ |
| run_command dispatches through the injectable executor seam | FR-001, D1 |
| HostCommandExecutor reproduces the current call byte-identically; the default | FR-002, D2 |
| LocalJailCommandExecutor: POSIX rlimits + env-scrub + cwd/process-group confinement; violation → contained failure | FR-003, D3 |
| Default-off (host executor) byte-identical; caller-injected | FR-004, D2 |
| Windows local-jail → ConfigError (no mislabelled weak path) | FR-005, D4 |
| Gateway-owned; no execution path outside the Gateway (audit green) | FR-006, D5 |
| Failures contained + public-safe (the existing run_command shaping) | FR-007 |
| ADR 0004; v1 local-jail POSIX-real; docker DEFERRED; stdlib-only; no event/content change | FR-008, D6 |
