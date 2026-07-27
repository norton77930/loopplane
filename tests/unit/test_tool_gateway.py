"""076 owner-scoped managed adapter coverage for the Tool Gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import pytest

from loopplane.context import RunContext
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.gateway.spi import AdapterOutput
from loopplane.model import TextBlock, ToolCallRequest, ToolDescriptor

pytestmark = pytest.mark.anyio


async def _discard(_event: RuntimeEvent) -> None:
    return None


def _descriptor(name: str, *, concurrency_safe: bool = False) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=f"{name} description",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        concurrency_safe=concurrency_safe,
    )


class _RecordingAdapter:
    def __init__(
        self,
        name: str,
        *,
        label: str,
        concurrency_safe: bool = False,
        started: anyio.Event | None = None,
        release: anyio.Event | None = None,
    ) -> None:
        self._descriptor = _descriptor(name, concurrency_safe=concurrency_safe)
        self._label = label
        self._started = started
        self._release = release
        self.invocations: list[str | None] = []
        self.shutdown_calls = 0

    def describe(self) -> list[ToolDescriptor]:
        return [self._descriptor]

    async def invoke(
        self,
        name: str,
        call_input: dict[str, object],
        context: RunContext,
    ) -> AsyncIterator[AdapterOutput]:
        self.invocations.append(context.principal_id)
        if self._started is not None:
            self._started.set()
        if self._release is not None:
            await self._release.wait()
        yield TextBlock(text=self._label)

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


class _DuplicateDescriptorAdapter(_RecordingAdapter):
    def describe(self) -> list[ToolDescriptor]:
        descriptor = super().describe()[0]
        return [descriptor, descriptor]


def _context(tmp_path: Path, principal_id: str | None) -> RunContext:
    return RunContext(
        session_id="session-1",
        working_scope=tmp_path,
        principal_id=principal_id,
    )


async def _execute(
    gateway: ToolGateway,
    tmp_path: Path,
    *,
    principal_id: str | None,
    tool_name: str = "managed",
):
    [result] = await gateway.execute_batch(
        [ToolCallRequest(call_id="call-1", tool_name=tool_name, input={})],
        parallel=False,
        context=_context(tmp_path, principal_id),
        emitter=EventEmitter(
            session_id="session-1",
            sequencer=EventSequencer(),
            sink=_discard,
        ),
    )
    return result


async def test_scoped_descriptors_filter_principal_and_allow_cross_owner_names(
    tmp_path: Path,
) -> None:
    gateway = ToolGateway()
    alice = _RecordingAdapter("managed", label="alice", concurrency_safe=True)
    bob = _RecordingAdapter("managed", label="bob")

    await gateway.replace_scoped_adapter("alice", "docs", alice)
    await gateway.replace_scoped_adapter("bob", "docs", bob)

    assert gateway.descriptors() == []
    assert {item.name for item in gateway.descriptors("alice")} == {"managed"}
    assert {item.name for item in gateway.descriptors("bob")} == {"managed"}
    assert gateway.is_concurrency_safe("managed", "alice") is True
    assert gateway.is_concurrency_safe("managed", "bob") is False
    assert gateway.is_concurrency_safe("managed", "other") is False

    gateway.register(_descriptor("shared"), lambda *_args: None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="shared"):
        await gateway.replace_scoped_adapter(
            "alice",
            "collision",
            _RecordingAdapter("shared", label="collision"),
        )


async def test_scoped_execution_fails_closed_for_non_owner(
    tmp_path: Path,
) -> None:
    gateway = ToolGateway()
    adapter = _RecordingAdapter("managed", label="alice")
    await gateway.replace_scoped_adapter("alice", "docs", adapter)

    owner = await _execute(gateway, tmp_path, principal_id="alice")
    other = await _execute(gateway, tmp_path, principal_id="bob")
    anonymous = await _execute(gateway, tmp_path, principal_id=None)

    assert owner.outcome == "success"
    assert adapter.invocations == ["alice"]
    for denied in (other, anonymous):
        assert denied.outcome == "failure"
        assert denied.error is not None
        assert denied.error.category == "unknown-tool"


async def test_scoped_replacement_leases_in_flight_adapter(
    tmp_path: Path,
) -> None:
    gateway = ToolGateway()
    started = anyio.Event()
    release = anyio.Event()
    old = _RecordingAdapter("managed", label="old", started=started, release=release)
    candidate = _RecordingAdapter("managed", label="candidate")
    await gateway.replace_scoped_adapter("alice", "docs", old)
    old_results: list[object] = []

    async def execute_old() -> None:
        old_results.append(await _execute(gateway, tmp_path, principal_id="alice"))

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(execute_old)
        await started.wait()
        with anyio.fail_after(1):
            await gateway.replace_scoped_adapter("alice", "docs", candidate)
        assert old.shutdown_calls == 0

        current = await _execute(gateway, tmp_path, principal_id="alice")
        assert current.outcome == "success"
        assert candidate.invocations == ["alice"]
        release.set()

    assert len(old_results) == 1
    assert old.shutdown_calls == 1


async def test_invalid_candidate_does_not_replace_healthy_adapter(
    tmp_path: Path,
) -> None:
    gateway = ToolGateway()
    healthy = _RecordingAdapter("managed", label="healthy")
    await gateway.replace_scoped_adapter("alice", "docs", healthy)

    with pytest.raises(ValueError, match="duplicate"):
        await gateway.replace_scoped_adapter(
            "alice",
            "docs",
            _DuplicateDescriptorAdapter("managed", label="invalid"),
        )

    current = await _execute(gateway, tmp_path, principal_id="alice")
    assert current.outcome == "success"
    assert healthy.invocations == ["alice"]
    assert healthy.shutdown_calls == 0


async def test_scoped_remove_and_shutdown_are_idempotent() -> None:
    gateway = ToolGateway()
    adapter = _RecordingAdapter("managed", label="alice")
    await gateway.replace_scoped_adapter("alice", "docs", adapter)

    await gateway.remove_scoped_adapter("alice", "docs")
    await gateway.remove_scoped_adapter("alice", "docs")
    await gateway.shutdown_scoped_adapters()
    await gateway.shutdown_scoped_adapters()

    assert gateway.descriptors("alice") == []
    assert adapter.shutdown_calls == 1
