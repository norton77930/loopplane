# Contract: Container Command Executor

The executor is in-process. There is no new HTTP route.

## Selection

- `InternalToolAdapter()` still uses the host executor.
- `InternalToolAdapter(command_executor=DockerCommandExecutor(image=...))`
  uses the container executor for `run_command` only.
- `LocalJailCommandExecutor` is unchanged.

## Launch arguments

Built by one function. Callers cannot replace these values:

- no network
- read-only root filesystem
- all capabilities dropped
- privilege escalation disabled
- user `65534:65534`
- empty environment
- one read-write mount of the working directory at `/workspace`
- a bounded `/tmp` that is not executable
- the command is `sh -c` of the caller's command string

## Construction failures

Fixed sentences, with no runtime text attached:

- package missing: `container execution requires loopplane[docker]`
- daemon unreachable: `container runtime is unavailable`
- image not local: `container image is not available locally`
- image name rejected: `container image name is not usable`

`repr` and `str` are `DockerCommandExecutor()`.

## Results

- A finished command returns its exit code and both streams.
- Wall-clock expiry kills the container, returns exit 124, and appends
  `[command timed out and was terminated]`.
- A runtime failure while starting raises `OSError` with
  `container runtime is unavailable`. The tool adapter already presents that
  as a contained command error.
