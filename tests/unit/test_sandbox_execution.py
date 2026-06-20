"""Sandboxed run_command execution tests (spec 052; ADR 0004). Offline.

The seam + the default host executor + the Windows ConfigError are tested here; the real
POSIX jail (rlimit termination + env-scrub) is skipif(not POSIX)-gated for POSIX/WSL CI
(this box is Windows)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loopplane.context import RunContext
from loopplane.gateway.spi import AdapterOutput, ErrorOutput
from loopplane.model.content import TextBlock
from loopplane.tools.execution import (
    CommandResult,
    HostCommandExecutor,
    LocalJailCommandExecutor,
    UnsupportedPlatformError,
)
from loopplane.tools.internal import InternalToolAdapter

pytestmark = pytest.mark.anyio

_POSIX = os.name == "posix"


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(session_id="s", working_scope=tmp_path)


async def _invoke(
    adapter: InternalToolAdapter,
    name: str,
    call_input: dict[str, object],
    ctx: RunContext,
) -> list[AdapterOutput]:
    return [output async for output in adapter.invoke(name, call_input, ctx)]


class _FakeExecutor:
    """A canned executor: records the call, returns a fixed result (or raises)."""

    def __init__(
        self, result: CommandResult | None = None, *, raise_oserror: bool = False
    ) -> None:
        self.calls: list[tuple[str, Path]] = []
        self._result = result or CommandResult(0, b"", b"")
        self._raise = raise_oserror

    async def run(self, command: str, *, cwd: Path) -> CommandResult:
        self.calls.append((command, cwd))
        if self._raise:
            raise OSError("spawn failed")
        return self._result


# --- US2: default + seam ------------------------------------------------------


def test_default_executor_is_host() -> None:
    assert isinstance(InternalToolAdapter()._executor, HostCommandExecutor)  # noqa: SLF001


async def test_default_run_command_executes_real_command(tmp_path: Path) -> None:
    # The default (host executor) runs a real benign command, byte-identical to pre-052.
    adapter = InternalToolAdapter()
    outputs = await _invoke(
        adapter, "run_command", {"command": "echo sandbox-ok"}, _ctx(tmp_path)
    )
    text = "".join(o.text for o in outputs if isinstance(o, TextBlock))
    assert "sandbox-ok" in text


async def test_seam_honored_with_fake(tmp_path: Path) -> None:
    fake = _FakeExecutor(CommandResult(0, b"from-fake\n", b""))
    adapter = InternalToolAdapter(command_executor=fake)
    (out,) = await _invoke(adapter, "run_command", {"command": "x"}, _ctx(tmp_path))
    assert isinstance(out, TextBlock) and "from-fake" in out.text
    assert fake.calls and fake.calls[0][0] == "x"


async def test_fake_nonzero_exit_surfaces_error(tmp_path: Path) -> None:
    fake = _FakeExecutor(CommandResult(1, b"", b"boom"))
    adapter = InternalToolAdapter(command_executor=fake)
    outputs = await _invoke(adapter, "run_command", {"command": "x"}, _ctx(tmp_path))
    errors = [o for o in outputs if isinstance(o, ErrorOutput)]
    assert errors and "exit code 1" in errors[0].message and "boom" in errors[0].message


async def test_contained_oserror(tmp_path: Path) -> None:
    adapter = InternalToolAdapter(command_executor=_FakeExecutor(raise_oserror=True))
    (out,) = await _invoke(adapter, "run_command", {"command": "x"}, _ctx(tmp_path))
    assert isinstance(out, ErrorOutput) and "cannot run command" in out.message


# --- US3: honest cross-platform jail ------------------------------------------


@pytest.mark.skipif(os.name == "posix", reason="Windows-only: jail unsupported here")
def test_local_jail_raises_on_windows() -> None:
    with pytest.raises(UnsupportedPlatformError):
        LocalJailCommandExecutor()


@pytest.mark.skipif(not _POSIX, reason="POSIX local jail")
def test_local_jail_scrubs_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("SECRET_TOKEN", "do-not-leak")
    jail = LocalJailCommandExecutor(env_allowlist=("PATH",))
    scrubbed = jail._scrubbed_env()  # noqa: SLF001
    assert scrubbed == {"PATH": "/usr/bin"}
    assert "SECRET_TOKEN" not in scrubbed


@pytest.mark.skipif(not _POSIX, reason="POSIX local jail")
async def test_local_jail_runs_normal_command(tmp_path: Path) -> None:
    jail = LocalJailCommandExecutor()
    result = await jail.run("echo jailed", cwd=tmp_path)
    assert result.returncode == 0 and b"jailed" in result.stdout


@pytest.mark.skipif(not _POSIX, reason="POSIX local jail")
async def test_local_jail_contains_over_limit_command(tmp_path: Path) -> None:
    # A tiny file-size rlimit: writing a large file is terminated (SIGXFSZ) -> non-zero,
    # contained (no hang, no raise-through).
    from loopplane.tools.execution import _ResourceLimits  # noqa: PLC0415

    jail = LocalJailCommandExecutor(
        limits=_ResourceLimits(file_size_bytes=1024),
    )
    result = await jail.run("head -c 5000000 /dev/zero > big.bin", cwd=tmp_path)
    assert result.returncode != 0  # terminated / failed, never a hang


@pytest.mark.skipif(not _POSIX, reason="POSIX local jail")
async def test_local_jail_wall_clock_timeout(tmp_path: Path) -> None:
    # A sleeping command is NOT bounded by RLIMIT_CPU; the wall-clock timeout terminates
    # it -> a contained non-zero result, never a hang past the Gateway's call timeout.
    from loopplane.tools.execution import _ResourceLimits  # noqa: PLC0415

    jail = LocalJailCommandExecutor(limits=_ResourceLimits(wall_seconds=1))
    result = await jail.run("sleep 30", cwd=tmp_path)
    assert result.returncode != 0
    assert b"timed out" in result.stderr
