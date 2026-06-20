# Contract: CommandExecutor seam (run_command sandboxing)

An injectable executor seam on the `run_command` path
([ADR 0004](../../docs/adr/0004-command-execution-isolation.md)). Default = the host executor
(byte-identical); the local-jail is opt-in. Execution stays Gateway-owned (the executor is inside
the `InternalToolAdapter`).

## Interface

| Type | Shape | Notes |
| ---- | ----- | ----- |
| `CommandResult` | `(returncode: int, stdout: bytes, stderr: bytes)` | What `_run_command` shapes into output. |
| `CommandExecutor` | `async run(command: str, *, cwd: Path) -> CommandResult` | The seam; `OSError` on spawn failure (caught by `_run_command`). |
| `HostCommandExecutor` | the current `anyio.run_process` call verbatim | The default. |
| `LocalJailCommandExecutor` | POSIX rlimits + env-scrub + cwd/process-group confinement | Opt-in; `ConfigError` on Windows. |

## Behavior

| Case | Result |
| ---- | ------ |
| No executor injected (default) | `_run_command` uses `HostCommandExecutor` → byte-identical to today (same stdout `TextBlock`, same non-zero-exit `ErrorOutput`, same `OSError` → "cannot run command"). |
| A fake executor injected | `_run_command` dispatches through it (the seam is honored). |
| Local-jail (POSIX), normal command | Runs in the jailed subprocess (cwd = working scope, scrubbed env, rlimits) and returns identical output to the host executor. |
| Local-jail (POSIX), over-limit command | Terminated; surfaced as a contained, public-safe `ErrorOutput` (non-zero exit) — not a hang, not a host crash. |
| Local-jail requested on Windows | `LocalJailCommandExecutor()` raises `ConfigError` (clear message; no mislabelled weak sandbox). |
| spawn fails / shell missing | `OSError` → the existing "cannot run command" `ErrorOutput`. |

## Invariants

- Execution is Gateway-owned (V): the executor is an impl detail inside `InternalToolAdapter`; the
  `test_no_execution_path_outside_the_gateway` audit stays green (controller/loop never import the
  tools layer; no `.invoke(`/`.handler(` outside `gateway/`).
- Default (host executor) is byte-identical to pre-052 (proven by a test).
- No event-schema / `SCHEMA_VERSION` / content-model change (VI); no new runtime dependency
  (stdlib `resource`/`os`); docker DEFERRED.
- Failures contained + public-safe (VII): the existing `run_command` error shaping; no new internal
  leak.
- Honest cross-platform: POSIX-real isolation; Windows local-jail → `ConfigError`.
