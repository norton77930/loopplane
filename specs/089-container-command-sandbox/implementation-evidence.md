# Implementation Evidence: Container Command Sandbox

Date: 2026-10-08. Status: Verified. Not published. Committed on
`089-container-command-sandbox`. Not pushed.

## Authorization

The maintainer selected the container sandbox and approved one optional
`docker` extra and ADR 0022. The default command path stays
`HostCommandExecutor`. No event, checkpoint, termination reason, HTTP route,
or `create_app` argument. Live-turn migration and the 086 store collapse stay
deferred. No verified spec was rewritten.

## RED

`tests/unit/test_container_executor.py` failed at collection with
`ModuleNotFoundError: No module named 'loopplane.tools.container'`.

## GREEN

- `uv run pytest -q --tb=short tests/unit/test_container_executor.py tests/contract/test_tools_boundary.py`: **17 passed**.
- `uv run pytest -q --tb=line tests/contract/test_api_reference.py tests/contract/test_release_sync.py tests/contract/test_spec_task_audit.py tests/contract/test_packaging.py tests/unit/test_container_executor.py`: **58 passed**.
- `uv lock --check`: resolved 69 packages.

The agent-context script was not re-run. Its YAML fallback raises
SyntaxError, as recorded for unit 088. `.specify/feature.json`, `AGENTS.md`,
and `CLAUDE.md` point at `specs/089-container-command-sandbox/plan.md`.

## Full suite

First `uv run pytest -q --tb=line --timeout=180`: **1 failed, 2421 passed,
33 skipped**, 1478.43s. The failure was
`tests/integration/test_examples_smoke.py::test_example_runs_clean[cli_quickstart.py]`
(`subprocess.TimeoutExpired` with a negative remaining time). That test alone
then passed in 3.41s.

Second `uv run pytest -q --tb=line --timeout=180`: **2422 passed, 33 skipped**,
1 existing Starlette warning, 630.46s. This is the Verified suite. It ran
while the board row still said Implemented. After the row was set to
Verified, `tests/contract/test_release_sync.py` and
`tests/contract/test_spec_task_audit.py` passed: **32 passed**.

## Type and lint gates

- `uv run mypy src`: Success, no issues found in 231 source files.
- `uv run ruff check --no-cache .`: All checks passed.
- `uv run ruff format --check --no-cache .`: 590 files already formatted.

No publication.

## Review follow-up

The suite and lint gates above ran before two later code fixes. The first
review required one `_run_kwargs` launch path, an integer `StatusCode`, a
`requests.exceptions.ReadTimeout` wall-clock mapping, and a public
`ResourceLimits`. The second review required `DockerSdkEngine.start` and
`DockerCommandExecutor._run_sync` to turn every `Exception` into
`OSError("container runtime is unavailable")` with no driver text. A third
review approved that shape.

After the last fix: `uv run pytest -q --tb=short tests/unit/test_container_executor.py tests/unit/test_sandbox_execution.py` was **24 passed, 4 skipped**. `uv run ruff check` and `uv run ruff format --check` passed on the touched Python files. The full suite was not re-run.
