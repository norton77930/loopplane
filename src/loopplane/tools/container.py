"""Opt-in container command executor (spec 089; ADR 0022).

The default command path stays ``HostCommandExecutor``. This module imports the
container SDK only when an operator constructs ``DockerCommandExecutor`` without
injecting an engine.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import anyio

from loopplane.tools.execution import CommandResult, ResourceLimits, _ConfigError

_IMAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}")
_TIMEOUT_NOTE = b"\n[command timed out and was terminated]"
_UNAVAILABLE = "container runtime is unavailable"


class ContainerExecutorError(_ConfigError):  # type: ignore[misc]
    """A container executor was requested but cannot be used. A ``ConfigError``."""


@dataclass(frozen=True)
class ContainerLaunch:
    """What the caller is allowed to vary. Confinement is not a field."""

    image: str
    command: tuple[str, ...]
    limits: ResourceLimits
    volume_host_path: str


class ContainerHandle(Protocol):
    def wait(self, timeout: float) -> int: ...

    def kill(self) -> None: ...

    def logs(self) -> tuple[bytes, bytes]: ...

    def remove(self) -> None: ...


class ContainerEngine(Protocol):
    def start(self, launch: ContainerLaunch) -> ContainerHandle: ...


def _require_image(image: str) -> str:
    if (
        not isinstance(image, str)
        or _IMAGE_RE.fullmatch(image) is None
        or ".." in image
        or "//" in image
    ):
        raise ContainerExecutorError("container image name is not usable")
    return image


def _run_kwargs(
    launch: ContainerLaunch, ulimit: Callable[..., object]
) -> dict[str, object]:
    """The SDK call, built once. ``ulimit`` is the SDK's own constructor."""

    limits = launch.limits
    return {
        "image": launch.image,
        "command": list(launch.command),
        "detach": True,
        "network_mode": "none",
        "read_only": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "privileged": False,
        "user": "65534:65534",
        "mem_limit": limits.address_space_bytes,
        "pids_limit": limits.max_processes,
        "volumes": {
            launch.volume_host_path: {"bind": "/workspace", "mode": "rw"},
        },
        "working_dir": "/workspace",
        "environment": {},
        "tmpfs": {"/tmp": f"rw,noexec,nosuid,size={limits.file_size_bytes}"},
        "ulimits": [
            ulimit(name="cpu", soft=limits.cpu_seconds, hard=limits.cpu_seconds),
            ulimit(
                name="fsize",
                soft=limits.file_size_bytes,
                hard=limits.file_size_bytes,
            ),
        ],
    }


def _as_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return b""


def _is_sdk_wait_timeout(exc: BaseException) -> bool:
    """docker-py documents ``requests.exceptions.ReadTimeout`` for ``wait``."""

    try:
        from requests.exceptions import ReadTimeout
    except ImportError:
        return False
    return isinstance(exc, ReadTimeout)


def _status_code(result: object) -> int:
    if not isinstance(result, Mapping):
        raise OSError(_UNAVAILABLE)
    code = result.get("StatusCode")
    if isinstance(code, bool) or not isinstance(code, int):
        raise OSError(_UNAVAILABLE)
    return code


class _SdkHandle:
    def __init__(self, container: Any) -> None:
        self._container = container

    def wait(self, timeout: float) -> int:
        try:
            result = self._container.wait(timeout=timeout)
        except TimeoutError:
            raise
        except Exception as exc:
            if _is_sdk_wait_timeout(exc):
                raise TimeoutError from None
            raise OSError(_UNAVAILABLE) from None
        return _status_code(result)

    def kill(self) -> None:
        self._container.kill()

    def logs(self) -> tuple[bytes, bytes]:
        stdout = self._container.logs(stdout=True, stderr=False)
        stderr = self._container.logs(stdout=False, stderr=True)
        return _as_bytes(stdout), _as_bytes(stderr)

    def remove(self) -> None:
        self._container.remove(force=True)


class DockerSdkEngine:
    """The production engine. Tests inject a different ``ContainerEngine``."""

    def __init__(self, client: Any, sdk: Any) -> None:
        self._client = client
        self._sdk = sdk

    def start(self, launch: ContainerLaunch) -> _SdkHandle:
        try:
            container = self._client.containers.run(
                **_run_kwargs(launch, self._sdk.types.Ulimit)
            )
        except Exception:
            raise OSError(_UNAVAILABLE) from None
        return _SdkHandle(container)


def _connect_docker(image: str) -> DockerSdkEngine:
    try:
        import docker
    except ImportError:
        raise ContainerExecutorError(
            "container execution requires loopplane[docker]"
        ) from None
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        raise ContainerExecutorError(_UNAVAILABLE) from None
    try:
        client.images.get(image)
    except Exception:
        raise ContainerExecutorError(
            "container image is not available locally"
        ) from None
    return DockerSdkEngine(client, docker)


class DockerCommandExecutor:
    """Run one command in a local container. Never falls back to the host shell."""

    def __init__(
        self,
        image: str,
        *,
        engine: ContainerEngine | None = None,
        limits: ResourceLimits | None = None,
    ) -> None:
        self._image = _require_image(image)
        self._limits = limits if limits is not None else ResourceLimits()
        self._engine = engine if engine is not None else _connect_docker(self._image)

    def __repr__(self) -> str:
        return "DockerCommandExecutor()"

    def __str__(self) -> str:
        return "DockerCommandExecutor()"

    async def run(self, command: str, *, cwd: Path) -> CommandResult:
        launch = ContainerLaunch(
            image=self._image,
            command=("sh", "-c", command),
            limits=self._limits,
            volume_host_path=str(cwd),
        )
        return await anyio.to_thread.run_sync(self._run_sync, launch)

    def _run_sync(self, launch: ContainerLaunch) -> CommandResult:
        try:
            handle = self._engine.start(launch)
        except Exception:
            raise OSError(_UNAVAILABLE) from None
        try:
            try:
                code = handle.wait(timeout=float(launch.limits.wall_seconds))
            except TimeoutError:
                self._stop(handle)
                stdout, stderr = self._logs(handle)
                return CommandResult(124, stdout, stderr + _TIMEOUT_NOTE)
            return CommandResult(code, *self._logs(handle))
        finally:
            with suppress(Exception):
                handle.remove()

    def _stop(self, handle: ContainerHandle) -> None:
        with suppress(Exception):
            handle.kill()

    def _logs(self, handle: ContainerHandle) -> tuple[bytes, bytes]:
        try:
            return handle.logs()
        except Exception:
            return b"", b""
