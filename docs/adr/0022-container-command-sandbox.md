# ADR 0022: Container command sandbox (G11 container slice)

- **Status**: **Accepted** (2026-10-08) — the maintainer selected this P1 and
  approved the optional extra and this ADR before implementation.
- **Deciders**: LoopPlane maintainer.
- **Supersedes / superseded by**: Supersedes nothing. **Discharges only** the
  docker/container sentence of ADR 0004 D6. Network-namespace work beyond no
  network, seccomp/BPF, and sandboxing tools other than `run_command` stay
  deferred, as 0004 already says.
- **Related**: Constitution **IV** (execution isolation stays inside the tools
  adapter), **V** (gateway chokepoint), **VII** (public-safe failures),
  **X** (default-off). Units **052** and **009**.

## Context

ADR 0004 shipped a POSIX local jail and deferred a container executor behind an
optional extra and a local daemon. Windows still cannot use that jail. The
default host executor remains the unconfined path when no executor is injected.

## Decision

- **D1 — Opt-in `DockerCommandExecutor` on the existing seam.**
  `InternalToolAdapter(command_executor=None)` stays `HostCommandExecutor`.
  There is no new config field and no HTTP argument.
- **D2 — One extra, lazy import, injectable engine.** The `docker` extra is
  maintainer-approved. Production imports it inside the connect function.
  Tests pass an engine and do not start a daemon.
- **D3 — Confinement is not a parameter.** The argument builder sets no
  network, a read-only root, all capabilities dropped, no privilege
  escalation, user `65534:65534`, an empty environment, and one working-directory
  mount. The executor does not pull an image.
- **D4 — Fail closed.** A missing extra, an unreachable daemon, a missing local
  image, or an unusable image name raises `ConfigError` before a command
  starts. The host executor is not a fallback. Failure text is a fixed sentence.
- **D5 — No event, checkpoint, or termination-vocabulary change.** Wall-clock
  expiry reuses the POSIX jail's exit 124 and terminated sentence.

## Consequences

- Operators on hosts without POSIX rlimits can select a container sandbox.
- The base install gains no dependency. `loopplane[all]` names the new extra.
- A daemon outage or a missing image refuses the executor. It does not run the
  command on the host.
