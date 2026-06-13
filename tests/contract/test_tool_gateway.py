"""Contract tests for the Tool Gateway pipeline (contracts/tool-gateway.md).

Asserts undeclared-parameter rejection (FR-022), unknown-tool handling,
per-call timeout (FR-024), the single normalized error shape (FR-025), and
that no execution path exists outside the Gateway (SC-002).
"""

from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from loopplane.approval import PolicyDeny, PolicyVerdict
from loopplane.context import RunContext
from loopplane.errors import NormalizedError
from loopplane.events import EventSequencer, RuntimeEvent
from loopplane.events.emitter import EventEmitter
from loopplane.gateway import ToolGateway
from loopplane.model import (
    OutputBlock,
    TextBlock,
    ToolCallRequest,
    ToolDescriptor,
)

pytestmark = pytest.mark.anyio

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "loopplane"


class _Collector:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    async def __call__(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]


def _emitter(sink: _Collector) -> EventEmitter:
    return EventEmitter(session_id="session-1", sequencer=EventSequencer(), sink=sink)


def _context(tmp_path: Path) -> RunContext:
    return RunContext(session_id="session-1", working_scope=tmp_path)


def _descriptor(name: str = "strict-tool") -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description="a tool with a strict schema",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    )


async def _execute_one(
    gateway: ToolGateway,
    call: ToolCallRequest,
    tmp_path: Path,
    sink: _Collector | None = None,
):
    sink = sink if sink is not None else _Collector()
    results = await gateway.execute_batch(
        [call],
        parallel=False,
        context=_context(tmp_path),
        emitter=_emitter(sink),
    )
    return results[0]


async def test_undeclared_parameter_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    executed: list[dict[str, object]] = []

    async def handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        executed.append(call_input)
        return [TextBlock(text="ran")]

    gateway = ToolGateway()
    gateway.register(_descriptor(), handler)

    result = await _execute_one(
        gateway,
        ToolCallRequest(
            call_id="c1", tool_name="strict-tool", input={"text": "ok", "sneaky": True}
        ),
        tmp_path,
    )

    assert executed == []
    assert result.outcome == "failure"
    assert result.error is not None
    assert result.error.category == "validation"
    assert "sneaky" in result.error.reason


async def test_schema_violation_is_rejected_before_execution(tmp_path: Path) -> None:
    executed: list[dict[str, object]] = []

    async def handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        executed.append(call_input)
        return [TextBlock(text="ran")]

    gateway = ToolGateway()
    gateway.register(_descriptor(), handler)

    result = await _execute_one(
        gateway,
        ToolCallRequest(call_id="c1", tool_name="strict-tool", input={"text": 42}),
        tmp_path,
    )

    assert executed == []
    assert result.outcome == "failure"
    assert result.error is not None
    assert result.error.category == "validation"


async def test_unknown_tool_yields_an_error_result_not_a_crash(tmp_path: Path) -> None:
    gateway = ToolGateway()

    result = await _execute_one(
        gateway,
        ToolCallRequest(call_id="c1", tool_name="nope", input={}),
        tmp_path,
    )

    assert result.outcome == "failure"
    assert result.error is not None
    assert result.error.category == "unknown-tool"
    assert "nope" in result.error.reason


async def test_per_call_timeout_produces_a_normalized_timeout_result(
    tmp_path: Path,
) -> None:
    async def slow_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        await anyio.sleep(30)
        return [TextBlock(text="too late")]

    async def fast_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        return [TextBlock(text="fast")]

    gateway = ToolGateway(call_timeout_seconds=0.2)
    gateway.register(_descriptor("slow"), slow_handler)
    gateway.register(_descriptor("fast"), fast_handler)

    sink = _Collector()
    with anyio.fail_after(10):
        result = await _execute_one(
            gateway,
            ToolCallRequest(call_id="c1", tool_name="slow", input={"text": "x"}),
            tmp_path,
            sink,
        )

    assert result.outcome == "failure"
    assert result.error is not None
    assert result.error.category == "timeout"
    assert "diagnostic" in sink.types

    # The runtime stays healthy: the same gateway serves the next call.
    follow_up = await _execute_one(
        gateway,
        ToolCallRequest(call_id="c2", tool_name="fast", input={"text": "x"}),
        tmp_path,
    )
    assert follow_up.outcome == "success"


async def test_policy_denial_carries_the_reason_and_its_own_category(
    tmp_path: Path,
) -> None:
    async def deny_everything(
        call: ToolCallRequest,
        descriptor: ToolDescriptor,
        context: RunContext,
        emitter: EventEmitter,
    ) -> PolicyVerdict:
        return PolicyDeny(reason="not today")

    async def handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        return [TextBlock(text="ran")]

    gateway = ToolGateway(decide=deny_everything)
    gateway.register(_descriptor(), handler)

    result = await _execute_one(
        gateway,
        ToolCallRequest(call_id="c1", tool_name="strict-tool", input={"text": "x"}),
        tmp_path,
    )

    assert result.outcome == "failure"
    assert result.error is not None
    assert result.error.category == "policy-denial"
    assert result.error.reason == "not today"


async def test_every_failure_mode_shares_one_normalized_error_shape(
    tmp_path: Path,
) -> None:
    async def broken_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        raise ValueError("internal explosion")

    gateway = ToolGateway()
    gateway.register(_descriptor("broken"), broken_handler)

    failures = [
        await _execute_one(
            gateway,
            ToolCallRequest(call_id="c1", tool_name="missing", input={}),
            tmp_path,
        ),
        await _execute_one(
            gateway,
            ToolCallRequest(
                call_id="c2", tool_name="broken", input={"text": "x", "extra": 1}
            ),
            tmp_path,
        ),
        await _execute_one(
            gateway,
            ToolCallRequest(call_id="c3", tool_name="broken", input={"text": "x"}),
            tmp_path,
        ),
    ]

    categories = [f.error.category for f in failures if f.error is not None]
    assert categories == ["unknown-tool", "validation", "execution"]
    for failure in failures:
        assert failure.outcome == "failure"
        assert isinstance(failure.error, NormalizedError)


async def test_raw_internal_errors_never_cross_the_boundary(tmp_path: Path) -> None:
    async def broken_handler(
        call_input: dict[str, object], context: RunContext
    ) -> list[OutputBlock]:
        raise ValueError("secret traceback detail")

    gateway = ToolGateway()
    gateway.register(_descriptor("broken"), broken_handler)

    result = await _execute_one(
        gateway,
        ToolCallRequest(call_id="c1", tool_name="broken", input={"text": "x"}),
        tmp_path,
    )

    assert result.outcome == "failure"
    assert isinstance(result.error, NormalizedError)


def test_no_execution_path_outside_the_gateway() -> None:
    """SC-002 structural audit: only the Gateway calls adapter/handler
    invocation, and the loop/controller never import tool sources.
    """
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        relative = path.relative_to(SRC_ROOT).as_posix()
        if relative.startswith("gateway/"):
            continue
        source = path.read_text("utf-8")
        if ".invoke(" in source or ".handler(" in source:
            offenders.append(relative)
    assert offenders == []

    for component in ("loop", "controller"):
        for path in (SRC_ROOT / component).rglob("*.py"):
            source = path.read_text("utf-8")
            assert "loopplane.tools" not in source, path
            assert "loopplane.adapters" not in source, path
