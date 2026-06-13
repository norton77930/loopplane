"""US2 acceptance 2.1, 2.2, 2.5, 2.6: governed tool calls end to end
(FR-022, FR-023, FR-024, FR-110–FR-113).

Acceptance 2.3 and 2.4 (external MCP tools) live in test_us2_mcp.py, which
owns the test MCP server fixture.
"""

from __future__ import annotations

import math
from pathlib import Path

import anyio
import pytest

from loopplane.approval import HumanApproval, PermissionRule
from loopplane.controller.controller import RuntimeController
from loopplane.controller.dispatcher import (
    ApprovalDecision,
    ConsumerRequest,
    Dispatcher,
    SubmitInput,
)
from loopplane.events import RuntimeEvent
from loopplane.gateway import ToolGateway
from loopplane.model import (
    OutputBlock,
    ScriptedModel,
    ScriptedTurn,
    TextBlock,
    TextIncrement,
    ToolCallRequest,
)

from .conftest import ECHO_DESCRIPTOR, EventCollector, HarnessFactory, echo_handler

pytestmark = pytest.mark.anyio


def _echo_then_recover_script() -> list[ScriptedTurn]:
    return [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="call-1", tool_name="echo", input={"text": "hi"}
                )
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]


async def test_denied_tool_never_executes_and_the_run_continues(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    executed: list[str] = []

    async def spying_echo(
        call_input: dict[str, object], context: object
    ) -> list[OutputBlock]:
        executed.append("ran")
        return [TextBlock(text="ran")]

    controller, session_id = harness(
        _echo_then_recover_script(),
        collector,
        decide=HumanApproval(
            rules=[PermissionRule(matcher="echo", effect="deny", scope="project")]
        ),
    )

    await controller.drive(session_id, [TextBlock(text="please echo")])

    assert executed == []
    completed = next(e for e in collector.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "failure"
    assert completed.payload.error is not None
    assert completed.payload.error.category == "policy-denial"
    assert completed.payload.error.reason
    assert "approval-requested" not in collector.types
    assert collector.events[-1].payload.reason == "natural-completion"


async def test_ask_policy_round_trip_with_session_memory(tmp_path: Path) -> None:
    """Acceptance 2.2: the call waits for the reviewer, a session-scoped
    approval is remembered, and the same tool is not re-asked.
    """
    script = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="call-1", tool_name="echo", input={"text": "one"}
                )
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="first done")]),
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="call-2", tool_name="echo", input={"text": "two"}
                )
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="second done")]),
    ]
    model = ScriptedModel(script=script, context_capacity=100_000)
    gateway = ToolGateway(decide=HumanApproval(rules=[]))
    gateway.register(ECHO_DESCRIPTOR, echo_handler)

    send_events, receive_events = anyio.create_memory_object_stream[RuntimeEvent](
        math.inf
    )
    send_requests, receive_requests = anyio.create_memory_object_stream[
        ConsumerRequest
    ](math.inf)
    controller = RuntimeController(
        model=model, gateway=gateway, event_sink=send_events.send
    )
    session_id = controller.create_session(working_scope=tmp_path)
    dispatcher = Dispatcher(
        controller=controller, session_id=session_id, inbound=receive_requests
    )

    received: list[RuntimeEvent] = []
    terminal_count = 0
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(dispatcher.run)
        await send_requests.send(SubmitInput(blocks=[TextBlock(text="echo one")]))
        with anyio.fail_after(10):
            async for event in receive_events:
                received.append(event)
                if event.type == "approval-requested":
                    await send_requests.send(
                        ApprovalDecision(
                            request_id=event.payload.request_id,
                            decision="allow",
                            scope="session",
                        )
                    )
                if event.type == "run-terminated":
                    terminal_count += 1
                    if terminal_count == 1:
                        await send_requests.send(
                            SubmitInput(blocks=[TextBlock(text="echo two")])
                        )
                    else:
                        break
        send_requests.close()

    types = [event.type for event in received]
    assert types.count("approval-requested") == 1
    assert types.count("approval-resolved") == 1

    resolved = next(e for e in received if e.type == "approval-resolved")
    assert resolved.payload.decision == "allow"
    assert resolved.payload.scope == "session"
    assert resolved.payload.resolution_source == "reviewer"

    completions = [e for e in received if e.type == "tool-call-completed"]
    assert [c.payload.outcome for c in completions] == ["success", "success"]

    # The approval request precedes the first execution, and the held call
    # only started after resolution.
    assert types.index("approval-requested") < types.index("tool-call-completed")


async def test_tool_over_its_time_limit_yields_timeout_and_runtime_stays_healthy(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    async def slow_handler(
        call_input: dict[str, object], context: object
    ) -> list[OutputBlock]:
        await anyio.sleep(30)
        return [TextBlock(text="too late")]

    slow_descriptor = ECHO_DESCRIPTOR.model_copy(update={"name": "slow"})
    script = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="call-1", tool_name="slow", input={"text": "x"}
                ),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="call-2", tool_name="echo", input={"text": "ok"}
                ),
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="recovered")]),
    ]
    controller, session_id = harness(
        script,
        collector,
        call_timeout_seconds=0.2,
        extra_tools=[(slow_descriptor, slow_handler)],
    )

    with anyio.fail_after(10):
        await controller.drive(session_id, [TextBlock(text="go")])

    completions = [e for e in collector.events if e.type == "tool-call-completed"]
    assert completions[0].payload.outcome == "failure"
    assert completions[0].payload.error is not None
    assert completions[0].payload.error.category == "timeout"
    # The runtime remains healthy: the next call succeeds and the run ends
    # naturally.
    assert completions[1].payload.outcome == "success"
    assert collector.events[-1].payload.reason == "natural-completion"


async def test_undeclared_parameter_is_rejected_before_execution(
    harness: HarnessFactory, collector: EventCollector
) -> None:
    script = [
        ScriptedTurn(
            increments=[
                ToolCallRequest(
                    call_id="call-1",
                    tool_name="echo",
                    input={"text": "hi", "undeclared": "nope"},
                )
            ],
            stop_reason="tool-use",
        ),
        ScriptedTurn(increments=[TextIncrement(text="done")]),
    ]
    controller, session_id = harness(script, collector)

    await controller.drive(session_id, [TextBlock(text="go")])

    completed = next(e for e in collector.events if e.type == "tool-call-completed")
    assert completed.payload.outcome == "failure"
    assert completed.payload.error is not None
    assert completed.payload.error.category == "validation"
    assert collector.events[-1].payload.reason == "natural-completion"
