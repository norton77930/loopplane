"""Opt-in container command executor (spec 089; ADR 0022). No daemon."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path

import pytest

from loopplane.host.config import ConfigError
from loopplane.model.content import TextBlock
from loopplane.tools.container import (
    ContainerLaunch,
    DockerCommandExecutor,
    DockerSdkEngine,
)
from loopplane.tools.execution import (
    CommandResult,
    HostCommandExecutor,
    ResourceLimits,
)
from loopplane.tools.internal import InternalToolAdapter
from tests.unit.test_sandbox_execution import _ctx, _invoke

pytestmark = pytest.mark.anyio


class _Handle:
    def __init__(
        self,
        *,
        code: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        timeout: bool = False,
    ) -> None:
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.timeout = timeout
        self.killed = False
        self.removed = False

    def wait(self, timeout: float) -> int:
        if self.timeout:
            raise TimeoutError
        return self.code

    def kill(self) -> None:
        self.killed = True

    def logs(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr

    def remove(self) -> None:
        self.removed = True


class _Engine:
    def __init__(self, handle: _Handle) -> None:
        self.handle = handle
        self.launches: list[ContainerLaunch] = []

    def start(self, launch: ContainerLaunch) -> _Handle:
        self.launches.append(launch)
        return self.handle


def _executor(
    handle: _Handle, **kwargs: object
) -> tuple[DockerCommandExecutor, _Engine]:
    engine = _Engine(handle)
    executor = DockerCommandExecutor(
        image="python:3.12-alpine", engine=engine, **kwargs
    )  # type: ignore[arg-type]
    return executor, engine


def test_default_adapter_stays_on_the_host_executor() -> None:
    assert isinstance(InternalToolAdapter()._executor, HostCommandExecutor)  # noqa: SLF001


async def test_container_launch_is_confined(tmp_path: Path) -> None:
    handle = _Handle(stdout=b"from-container\n")
    limits = ResourceLimits(
        cpu_seconds=4,
        wall_seconds=9,
        address_space_bytes=1000,
        file_size_bytes=50,
        max_processes=3,
    )
    executor, engine = _executor(handle, limits=limits)
    result = await executor.run("echo hi", cwd=tmp_path)

    assert result == CommandResult(0, b"from-container\n", b"")
    assert handle.removed
    launch = engine.launches[0]
    assert launch.command == ("sh", "-c", "echo hi")
    assert launch.limits == limits
    assert launch.volume_host_path == str(tmp_path)
    assert "python:3.12-alpine" not in repr(executor)
    assert repr(executor) == "DockerCommandExecutor()"
    assert str(executor) == "DockerCommandExecutor()"


async def test_default_limits_match_the_posix_jail(tmp_path: Path) -> None:
    handle = _Handle()
    executor, engine = _executor(handle)
    await executor.run("true", cwd=tmp_path)
    assert engine.launches[0].limits == ResourceLimits()


async def test_wall_clock_expiry_kills_the_container(tmp_path: Path) -> None:
    handle = _Handle(timeout=True, stdout=b"partial", stderr=b"err")
    executor, _engine = _executor(handle)
    result = await executor.run("sleep 100", cwd=tmp_path)

    assert handle.killed
    assert handle.removed
    assert result.returncode == 124
    assert result.stdout == b"partial"
    assert b"[command timed out and was terminated]" in result.stderr


@pytest.mark.parametrize(
    "image",
    ["", "-privileged", "../image", "http://example/image", "image name", "a" * 300],
)
def test_unusable_image_names_are_refused(image: str) -> None:
    with pytest.raises(ConfigError, match="container image name is not usable"):
        DockerCommandExecutor(image=image, engine=_Engine(_Handle()))


def test_missing_extra_names_the_extra_and_nothing_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "docker", raising=False)
    real_import = builtins.__import__

    def hide_docker(name: str, *args: object, **kwargs: object) -> object:
        if name == "docker":
            raise ImportError("simulated absence")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", hide_docker)
    with pytest.raises(ConfigError, match=r"loopplane\[docker\]") as caught:
        DockerCommandExecutor(image="python:3.12-alpine")
    assert "simulated" not in str(caught.value)


def test_daemon_and_missing_image_use_fixed_sentences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Images:
        def get(self, name: str) -> object:
            raise RuntimeError(f"secret socket for {name}")

    class _Client:
        def ping(self) -> bool:
            return True

        images = _Images()

    docker = type(sys)("docker")
    docker.from_env = lambda: _Client()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docker", docker)

    with pytest.raises(
        ConfigError, match="container image is not available locally"
    ) as caught:
        DockerCommandExecutor(image="registry.example/team/app:1")
    assert "registry.example" not in str(caught.value)
    assert "secret socket" not in str(caught.value)

    class _Down:
        def ping(self) -> bool:
            raise RuntimeError("secret socket down")

    docker.from_env = lambda: _Down()  # type: ignore[attr-defined]
    with pytest.raises(ConfigError, match="container runtime is unavailable") as caught:
        DockerCommandExecutor(image="python:3.12-alpine")
    assert "secret socket" not in str(caught.value)


async def test_adapter_returns_container_output(tmp_path: Path) -> None:
    handle = _Handle(stdout=b"from-container\n")
    executor, _engine = _executor(handle)
    outputs = await _invoke(
        InternalToolAdapter(command_executor=executor),
        "run_command",
        {"command": "echo hi"},
        _ctx(tmp_path),
    )
    text = "".join(item.text for item in outputs if isinstance(item, TextBlock))
    assert text == "from-container\n"


def test_sdk_engine_applies_confinement_and_hides_runtime_text() -> None:
    class _Ulimit:
        def __init__(self, *, name: str, soft: int, hard: int) -> None:
            self.name = name
            self.soft = soft
            self.hard = hard

    class _Types:
        Ulimit = _Ulimit

    class _Sdk:
        types = _Types()

    seen: dict[str, object] = {}

    class _Containers:
        def run(self, **kwargs: object) -> object:
            seen.update(kwargs)
            if kwargs.get("image") == "missing":
                raise RuntimeError("secret socket")
            return object()

    engine = DockerSdkEngine(
        type("Client", (), {"containers": _Containers()})(), _Sdk()
    )
    limits = ResourceLimits(
        cpu_seconds=4,
        wall_seconds=9,
        address_space_bytes=1000,
        file_size_bytes=50,
        max_processes=3,
    )
    engine.start(
        ContainerLaunch(
            image="python:3.12-alpine",
            command=("sh", "-c", "echo hi"),
            limits=limits,
            volume_host_path="/work",
        )
    )
    assert seen["network_mode"] == "none"
    assert seen["read_only"] is True
    assert seen["cap_drop"] == ["ALL"]
    assert seen["security_opt"] == ["no-new-privileges:true"]
    assert seen["privileged"] is False
    assert seen["user"] == "65534:65534"
    assert seen["environment"] == {}
    assert seen["working_dir"] == "/workspace"
    assert seen["mem_limit"] == 1000
    assert seen["pids_limit"] == 3
    assert seen["tmpfs"] == {"/tmp": "rw,noexec,nosuid,size=50"}
    assert seen["volumes"] == {"/work": {"bind": "/workspace", "mode": "rw"}}
    built = seen["ulimits"]
    assert isinstance(built, list)
    assert isinstance(built[0], _Ulimit)
    assert built[0].name == "cpu" and built[0].soft == 4
    assert isinstance(built[1], _Ulimit)
    assert built[1].name == "fsize" and built[1].soft == 50

    launch = ContainerLaunch(
        image="missing",
        command=("sh", "-c", "echo hi"),
        limits=limits,
        volume_host_path="/work",
    )
    with pytest.raises(OSError, match="container runtime is unavailable") as caught:
        engine.start(launch)
    assert "secret socket" not in str(caught.value)


def test_sdk_wait_accepts_only_a_status_code() -> None:
    class Timeout(Exception):
        """A lookalike. Not the SDK's documented read timeout."""

    class _Ulimit:
        def __init__(self, *, name: str, soft: int, hard: int) -> None:
            self.name = name
            self.soft = soft
            self.hard = hard

    class _Box:
        def __init__(self) -> None:
            self.result: object = {"StatusCode": 4}
            self.error: BaseException | None = None

        def wait(self, timeout: float) -> object:
            if self.error is not None:
                raise self.error
            return self.result

    box = _Box()

    class _Containers:
        def run(self, **kwargs: object) -> _Box:
            return box

    engine = DockerSdkEngine(
        type("Client", (), {"containers": _Containers()})(),
        type("Sdk", (), {"types": type("Types", (), {"Ulimit": _Ulimit})})(),
    )
    handle = engine.start(
        ContainerLaunch(
            image="python:3.12-alpine",
            command=("sh", "-c", "true"),
            limits=ResourceLimits(),
            volume_host_path="/work",
        )
    )
    assert handle.wait(1) == 4

    box.result = "not-a-status"
    with pytest.raises(OSError, match="container runtime is unavailable") as caught:
        handle.wait(1)
    assert "not-a-status" not in str(caught.value)

    box.result = {"StatusCode": "secret socket"}
    with pytest.raises(OSError, match="container runtime is unavailable") as caught:
        handle.wait(1)
    assert "secret socket" not in str(caught.value)

    box.result = {"StatusCode": 0}
    box.error = Timeout("secret socket")
    with pytest.raises(OSError, match="container runtime is unavailable") as caught:
        handle.wait(1)
    assert "secret socket" not in str(caught.value)

    from requests.exceptions import ReadTimeout

    box.error = ReadTimeout("secret socket")
    with pytest.raises(TimeoutError) as caught_timeout:
        handle.wait(1)
    assert "secret socket" not in str(caught_timeout.value)


_DRIVER_TEXT = "secret socket http://127.0.0.1:2375/v1.41 python:3.12-alpine"


def _assert_unavailable(caught: pytest.ExceptionInfo[OSError]) -> None:
    assert str(caught.value) == "container runtime is unavailable"
    assert caught.value.__cause__ is None
    assert "secret socket" not in str(caught.value)
    assert "127.0.0.1" not in str(caught.value)
    assert "python:3.12-alpine" not in str(caught.value)


def test_sdk_start_hides_oserror_subclass() -> None:
    class _ApiFailure(OSError):
        """Stands in for docker-py APIError, which is an OSError."""

    class _Ulimit:
        def __init__(self, *, name: str, soft: int, hard: int) -> None:
            self.name = name
            self.soft = soft
            self.hard = hard

    class _Containers:
        def run(self, **kwargs: object) -> object:
            raise _ApiFailure(_DRIVER_TEXT)

    engine = DockerSdkEngine(
        type("Client", (), {"containers": _Containers()})(),
        type("Sdk", (), {"types": type("Types", (), {"Ulimit": _Ulimit})})(),
    )
    with pytest.raises(OSError, match="container runtime is unavailable") as caught:
        engine.start(
            ContainerLaunch(
                image="python:3.12-alpine",
                command=("sh", "-c", "true"),
                limits=ResourceLimits(),
                volume_host_path="/work",
            )
        )
    _assert_unavailable(caught)


async def test_executor_hides_oserror_from_start(tmp_path: Path) -> None:
    class _Down:
        def start(self, launch: ContainerLaunch) -> object:
            raise OSError(_DRIVER_TEXT)

    executor = DockerCommandExecutor(
        "python:3.12-alpine",
        engine=_Down(),  # type: ignore[arg-type]
    )
    with pytest.raises(OSError, match="container runtime is unavailable") as caught:
        await executor.run("echo hi", cwd=tmp_path)
    _assert_unavailable(caught)
