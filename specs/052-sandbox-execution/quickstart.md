# Quickstart / Validation: Sandboxed run_command Execution

See [contracts/command-executor.md](contracts/command-executor.md),
[data-model.md](data-model.md), and [ADR 0004](../../docs/adr/0004-command-execution-isolation.md).
The hardest Tier-3 unit — POSIX subprocess mechanics behind an injectable seam; the real jail is
POSIX/WSL-validated, the seam + default + Windows path are unit-tested here.

## Run the unit tests

```powershell
pytest tests/unit/test_sandbox_execution.py -q
```

## Run the full suite (additive proof)

```powershell
pytest -q
```

Expected: green; the only count change is the new sandbox tests. With no executor configured (the
default), `run_command` behavior is byte-identical (the host executor).

## Validation scenarios (mirror the acceptance scenarios)

1. **Default byte-identity** — `InternalToolAdapter()` (no executor) → `_run_command` uses
   `HostCommandExecutor`; output identical to pre-052. (FR-002/004, SC-002)
2. **Seam honored** — inject a fake `CommandExecutor`; `run_command` dispatches through it. (FR-001, SC-002)
3. **Windows ConfigError** — constructing `LocalJailCommandExecutor` on Windows raises
   `ConfigError` (clear message). (FR-005, SC-003)
4. **Env-scrub** — the jail's scrubbed environment keeps only the allowlist (assert the env dict
   construction, no subprocess needed). (FR-003)
5. **Real jail (POSIX-gated)** — `@skipif(not POSIX)`: a normal command returns identical output;
   an over-limit command (CPU/output/processes) is terminated + surfaced as a contained failure.
   (FR-003, SC-001)
6. **Gateway-owned audit** — `test_no_execution_path_outside_the_gateway` stays green (the executor
   is inside the tools-layer adapter; controller/loop do not import it). (FR-006, SC-003)
7. **Contained spawn failure** — a fake executor raising `OSError` → the existing "cannot run
   command" `ErrorOutput`. (FR-007)

## Manual gate checks (autopilot, board §10)

```powershell
ruff check .; ruff format --check src tests; mypy src; pytest
```

Plus the structural audits (`test_no_execution_path_outside_the_gateway`, `test_public_safety`).
On a POSIX box / WSL, additionally run the `skipif`-gated real-jail test for the actual isolation.
