"""Command-execution seam for the run_command tool (spec 052; ADR 0004).

run_command dispatches shell execution through a ``CommandExecutor`` instead of inlining
the subprocess spawn. The default ``HostCommandExecutor`` is the current call verbatim
(``anyio.run_process``), so an unconfigured runtime is byte-identical.
``LocalJailCommandExecutor`` (POSIX) adds resource limits, env scrubbing, and cwd/
process-group confinement; on a platform lacking them (Windows) it raises
``UnsupportedPlatformError`` instead of a weaker path mislabelled as a sandbox.

The executor is an internal detail of the Gateway-owned ``InternalToolAdapter`` — the
Tool Gateway stays the single execution chokepoint (V). Stdlib-only; docker deferred.
"""

from __future__ import annotations

import os
import subprocess  # noqa: S404 - the run_command tool's whole purpose is shell execution
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anyio

try:  # ``resource`` is POSIX-only; absent on Windows.
    import resource
except ModuleNotFoundError:  # pragma: no cover - exercised on Windows
    resource = None  # type: ignore[assignment]

# The local jail needs the POSIX process primitives (resource limits + setsid).
_POSIX = os.name == "posix" and resource is not None

_DEFAULT_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


class UnsupportedPlatformError(RuntimeError):
    """Raised when a sandbox backend is requested on a platform that cannot provide it
    (e.g. the POSIX local jail on Windows). A clear, public-safe configuration error —
    the runtime refuses to mislabel a weakened path as a sandbox (ADR 0004 D4)."""


@dataclass
class CommandResult:
    """The outcome of a shell command (what ``_run_command`` shapes into output)."""

    returncode: int
    stdout: bytes
    stderr: bytes


class CommandExecutor(Protocol):
    """The injectable seam for running a shell command within a working directory.

    ``run`` raises ``OSError`` on a spawn failure (caught by ``_run_command`` as today).
    """

    async def run(self, command: str, *, cwd: Path) -> CommandResult: ...


class HostCommandExecutor:
    """The default executor: the current ``run_command`` call verbatim — an unconfined
    host shell via ``anyio.run_process``. Byte-identical to pre-052."""

    async def run(self, command: str, *, cwd: Path) -> CommandResult:
        completed = await anyio.run_process(command, cwd=cwd, check=False)
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


@dataclass
class _ResourceLimits:
    cpu_seconds: int = 10
    wall_seconds: int = 30
    address_space_bytes: int = 512 * 1024 * 1024
    file_size_bytes: int = 64 * 1024 * 1024
    max_processes: int = 64


class LocalJailCommandExecutor:
    """A POSIX local-subprocess jail (ADR 0004 D3): the command runs with resource
    limits (CPU / address space / file size / process count), a scrubbed environment
    (a minimal allowlist), and cwd + process-group (``setsid``) confinement. A limit
    violation terminates the process and is surfaced as a contained, non-zero result —
    never a hang or a host crash. Construction raises ``UnsupportedPlatformError`` off
    POSIX."""

    def __init__(
        self,
        *,
        limits: _ResourceLimits | None = None,
        env_allowlist: tuple[str, ...] = _DEFAULT_ENV_ALLOWLIST,
    ) -> None:
        if not _POSIX:
            raise UnsupportedPlatformError(
                "the local-jail command executor requires POSIX resource limits, "
                "unavailable on this platform; use the default host executor or a "
                "POSIX host"
            )
        self._limits = limits or _ResourceLimits()
        self._env_allowlist = env_allowlist

    def _scrubbed_env(self) -> dict[str, str]:
        """The minimal environment passed to the child — only the allowlist, so host
        secrets in the ambient environment are not inherited."""
        return {
            key: os.environ[key] for key in self._env_allowlist if key in os.environ
        }

    def _apply_limits(self) -> None:  # pragma: no cover - runs in the POSIX child
        # Detach into a new session/process group so the whole tree can be contained,
        # then cap resources. Reached only on POSIX (guaranteed by __init__).
        assert resource is not None
        setsid = getattr(os, "setsid", None)
        if setsid is not None:
            setsid()
        # getattr so the POSIX-only `resource` attributes do not trip mypy on Windows.
        setrlimit = getattr(resource, "setrlimit", None)
        if setrlimit is None:
            return
        limits = (
            ("RLIMIT_CPU", self._limits.cpu_seconds),
            ("RLIMIT_AS", self._limits.address_space_bytes),
            ("RLIMIT_FSIZE", self._limits.file_size_bytes),
            ("RLIMIT_NPROC", self._limits.max_processes),
        )
        for name, value in limits:
            which = getattr(resource, name, None)
            if which is None:  # a limit absent on this kernel -> skip it
                continue
            try:
                setrlimit(which, (value, value))
            except (ValueError, OSError):  # a value above the hard limit -> skip it
                pass

    async def run(self, command: str, *, cwd: Path) -> CommandResult:
        env = self._scrubbed_env()

        def _spawn() -> CommandResult:
            # A wall-clock timeout IN ADDITION to RLIMIT_CPU: RLIMIT_CPU bounds only CPU
            # time, so a sleeping / IO-blocked command would not be capped — and the
            # subprocess runs in a worker thread the Gateway timeout cannot cancel.
            # So the jail bounds wall-clock itself (kills the process on expiry) and
            # surfaces a contained, non-zero result rather than hanging.
            try:
                completed = subprocess.run(  # noqa: S602 - a shell tool, jailed here
                    command,
                    shell=True,
                    cwd=cwd,
                    env=env,
                    preexec_fn=self._apply_limits,
                    capture_output=True,
                    check=False,
                    timeout=self._limits.wall_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                out = exc.stdout if isinstance(exc.stdout, bytes) else b""
                err = exc.stderr if isinstance(exc.stderr, bytes) else b""
                return CommandResult(
                    124, out, err + b"\n[command timed out and was terminated]"
                )
            return CommandResult(
                completed.returncode, completed.stdout, completed.stderr
            )

        return await anyio.to_thread.run_sync(_spawn)
