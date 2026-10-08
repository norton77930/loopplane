# Research: Container Command Sandbox

## Decision: injectable executor, not a new configuration field

**Rationale**: `InternalToolAdapter` already takes `command_executor`. A new
config field would be another default. Callers who want a container pass
`DockerCommandExecutor` the same way they pass `LocalJailCommandExecutor`.
**Alternatives considered**: a `RuntimeConfig` sandbox name (adds a knob and
an HTTP/config question this approval did not include).

## Decision: one argument builder owns confinement

**Rationale**: Network, read-only root, capability drop, user, environment, and
the single volume are not caller parameters. One function returns them, and
both the SDK engine and the tests use that function.
**Alternatives considered**: kwargs assembled at the call site (a later edit
can drop a flag); a policy object with overridable fields (re-opens the host).

## Decision: fail at construction, and never fall back to the host

**Rationale**: A missing package, an unreachable daemon, or a missing local
image is a configuration failure. Running the command on the host would present
an unconfined path as a sandbox, which ADR 0004 D4 already forbids for the POSIX jail.
**Alternatives considered**: catch the failure inside `run` and use
`HostCommandExecutor` (mislabelled sandbox).

## Decision: do not pull images

**Rationale**: A pull needs network and can change what runs. The operator
supplies a local image. The image name is checked as a single token before
any runtime call, and it is not copied into errors or `repr`.
**Alternatives considered**: `docker pull` on first use (supply-chain side effect).

## Decision: wall-clock kill uses the same terminated result as the POSIX jail

**Rationale**: Exit 124 and the existing terminated sentence already mean the
command was stopped. The container is killed and then removed. Removal failure
does not replace that result.
**Alternatives considered**: a new termination reason (event vocabulary, §E).
