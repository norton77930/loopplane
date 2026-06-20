# Tasks: Sandboxed run_command Execution

**Feature**: 052-sandbox-execution | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **ADR**: [0004](../../docs/adr/0004-command-execution-isolation.md)

**Scope**: additive — a new `src/loopplane/tools/execution.py` (the seam + executors) + a
`_run_command` refactor + an `InternalToolAdapter` ctor param + export + api-reference + tests.
Default (host executor) byte-identical. Gateway-owned (V); no event-schema/content-model change
(VI); no new dependency (stdlib `resource`/`os`); per ADR 0004. v1 local-jail POSIX-real, docker
DEFERRED, Windows local-jail → `ConfigError`.

**Tests**: requested (TDD-friendly). Windows: seam + host byte-identity + Windows-`ConfigError` +
env-scrub via a FAKE executor; the real POSIX jail via a `skipif(not POSIX)` test.

## Phase 1: Foundational — the seam (P1) 🎯 MVP

- [ ] T001 Create `src/loopplane/tools/execution.py`: `CommandResult` (dataclass: `returncode:int`,
  `stdout:bytes`, `stderr:bytes`); a `CommandExecutor` Protocol (`async run(command: str, *, cwd:
  Path) -> CommandResult`); and `HostCommandExecutor` whose `run` is the CURRENT call verbatim —
  `completed = await anyio.run_process(command, cwd=cwd, check=False); return CommandResult(
  completed.returncode, completed.stdout, completed.stderr)` (let `OSError` propagate, caught by
  `_run_command` as today).
- [ ] T002 In the same module add `LocalJailCommandExecutor` (POSIX): `__init__` raises a clear
  configuration error (a public-safe message; e.g. a local `UnsupportedPlatformError(RuntimeError)`
  or `ValueError` — do NOT invert layering by importing host.config into tools) when the POSIX
  primitives are unavailable (Windows). `run` spawns with `cwd=cwd`, a SCRUBBED env (a minimal
  configurable allowlist, e.g. PATH/HOME/LANG), and `setsid` + a `preexec` applying
  `resource.setrlimit` (CPU seconds / address space / file size / max processes; configurable safe
  defaults); a limit violation terminates the process → a `CommandResult` with a non-zero code
  (contained), never a hang/raise-through. Choose the cleanest spawn mechanism that applies the
  preexec + captures output (anyio.run_process kwargs / anyio.open_process / to_thread+subprocess).

## Phase 2: Wire run_command to the seam (P2)

- [ ] T003 In `src/loopplane/tools/internal.py`: add `command_executor: CommandExecutor | None =
  None` to `InternalToolAdapter.__init__` (default → `HostCommandExecutor()`), stored as
  `self._executor` (the `memory_store` / `max_file_snapshots` injection shape). Refactor
  `_run_command` to `result = await self._executor.run(command, cwd=context.working_scope)` inside
  the existing `try/except OSError`, then the SAME output shaping (decode stdout/stderr; stdout →
  `TextBlock`; non-zero exit → `ErrorOutput`). The default path stays byte-identical.

## Phase 3: Export + tests (P3)

- [ ] T004 Export `CommandExecutor`, `CommandResult`, `HostCommandExecutor`,
  `LocalJailCommandExecutor` from `src/loopplane/tools/__init__.py` and add them to
  `docs/api-reference.md` (the `loopplane.tools` section; the unit-014 bijection must stay exact).
- [ ] T005 Write `tests/unit/test_sandbox_execution.py` (offline): (a) default byte-identity — a
  default `InternalToolAdapter()` runs a real benign command (e.g. echo) identically to pre-052;
  (b) seam honored — a FAKE `CommandExecutor` injected is used by `run_command`; (c) contained
  spawn failure — a fake raising `OSError` → the existing "cannot run command" `ErrorOutput`;
  (d) Windows-`ConfigError` — constructing `LocalJailCommandExecutor` on Windows raises the clear
  error (use `sys.platform`/`skipif` so it asserts on Windows, skips on POSIX or vice-versa);
  (e) env-scrub — assert the scrubbed env dict keeps only the allowlist (no real subprocess
  needed); (f) `@skipif(not POSIX)` real-jail — a normal command returns identical output, and an
  over-limit command is terminated + surfaced as a contained failure.

## Phase 4: Polish & Cross-Cutting

- [ ] T006 Run the four gates green: `ruff check`, `ruff format --check`, `mypy` (src, strict),
  `pytest` (full suite — additive proof + default byte-identity). ALSO confirm the structural
  audits stay green: `test_no_execution_path_outside_the_gateway` (the executor is INSIDE the
  tools-layer adapter; controller/loop do not import `loopplane.tools`) and `test_public_safety`.

## Dependencies

- T001 → T002, T003. T003 → T005. T001 → T004. T004 → T006 (gates last).

## Implementation strategy

- **MVP = Phase 1 (T001 seam + HostCommandExecutor) + T003 wiring** → byte-identical default + the
  seam. T002 adds the POSIX jail; T005 covers it (Windows: fake + ConfigError; POSIX-gated: real).
  The implement is POSIX-specific + cross-cutting — a fork subagent MAY do it; then the four gates +
  the two structural audits + an adversarial verify workflow (default-off byte-identity, boundary/
  Gateway-owned, isolation correctness, containment, public-safety, Windows-ConfigError) run before
  commit; GO/0 blocking only.
- All additive; default (host executor) byte-identical; no new dependency; per ADR 0004.

## Cross-Artifact Analysis (gate)

_(filled at the analyze step)_
